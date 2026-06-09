"""
PatientPredator agent — runs on every node.

Env vars:
  PP_TOKEN        shared secret (default: changeme)
  PP_PORT         port to listen on (default: 4200)
  PP_NAME         node name (default: hostname)
  PP_COORDINATOR  URL of coordinator, e.g. http://10.0.0.1:4200
                  leave empty → this node IS the coordinator
"""

import os
import subprocess
import threading
import time
from collections import deque
from datetime import datetime
from functools import wraps

import requests
from flask import Flask, abort, jsonify, request

from device import Device
from task import Task, TaskStatus

PP_TOKEN = os.environ.get("PP_TOKEN", "changeme")
PP_PORT = int(os.environ.get("PP_PORT", 4200))
PP_NAME = os.environ.get("PP_NAME", __import__("socket").gethostname())
PP_COORDINATOR = os.environ.get("PP_COORDINATOR", "").rstrip("/")

app = Flask(__name__)

device = Device(name=PP_NAME, device_type="node")
device.fetch_info()

# Coordinator state
_lock = threading.Lock()
task_queue: deque[str] = deque()
task_registry: dict[str, Task] = {}
node_registry: dict[str, dict] = {}


# ── auth ─────────────────────────────────────────────────────────────────────

def require_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get("X-Token") or request.args.get("token")
        if token != PP_TOKEN:
            abort(401, description="invalid token")
        return f(*args, **kwargs)
    return wrapper


# ── helpers ──────────────────────────────────────────────────────────────────

def _coordinator_get(path, **kw):
    return requests.get(
        f"{PP_COORDINATOR}{path}",
        headers={"X-Token": PP_TOKEN},
        timeout=5,
        **kw,
    )


def _coordinator_post(path, json=None, **kw):
    return requests.post(
        f"{PP_COORDINATOR}{path}",
        json=json or {},
        headers={"X-Token": PP_TOKEN},
        timeout=5,
        **kw,
    )


# ── common endpoints ─────────────────────────────────────────────────────────

@app.route("/info")
@require_token
def info():
    device.update_status()
    return jsonify({
        "name": device.name,
        "os": device.os,
        "cpu": device.cpu_name,
        "cores": device.cpu_cores,
        "ram_gb": device.ram_gb,
        "disk_gb": device.storage_gb,
        "ip": device.ip_address,
        "role": "worker" if PP_COORDINATOR else "coordinator",
    })


@app.route("/status")
@require_token
def status():
    device.update_status()
    return jsonify({
        "name": device.name,
        "cpu_pct": device.cpu_usage,
        "ram_pct": device.ram_usage,
        "swap_pct": device.swap_usage,
        "temp_c": device.temperature,
        "network": device.network_status,
        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
    })


# ── task submission (workers forward to coordinator) ─────────────────────────

@app.route("/task", methods=["POST"])
@require_token
def submit_task():
    if PP_COORDINATOR:
        r = _coordinator_post("/task", json=request.get_json())
        return jsonify(r.json()), r.status_code

    data = request.get_json() or {}
    if not data.get("command"):
        abort(400, description="'command' is required")

    task = Task(
        command=data["command"],
        name=data.get("name"),
        submitter=data.get("submitter", request.remote_addr),
    )
    with _lock:
        task_registry[task.id] = task
        task_queue.append(task.id)

    return jsonify(task.to_dict()), 201


@app.route("/tasks")
@require_token
def list_tasks():
    if PP_COORDINATOR:
        r = _coordinator_get("/tasks")
        return jsonify(r.json()), r.status_code
    with _lock:
        tasks = [t.to_dict() for t in task_registry.values()]
    return jsonify(tasks)


@app.route("/task/<tid>")
@require_token
def get_task(tid):
    if PP_COORDINATOR:
        r = _coordinator_get(f"/task/{tid}")
        return jsonify(r.json()), r.status_code
    with _lock:
        task = task_registry.get(tid)
    if not task:
        abort(404, description="task not found")
    return jsonify(task.to_dict())


@app.route("/task/<tid>", methods=["DELETE"])
@require_token
def delete_task(tid):
    if PP_COORDINATOR:
        r = requests.delete(
            f"{PP_COORDINATOR}/task/{tid}",
            headers={"X-Token": PP_TOKEN},
            timeout=5,
        )
        return jsonify(r.json()), r.status_code
    with _lock:
        task = task_registry.pop(tid, None)
        if tid in task_queue:
            task_queue.remove(tid)
    if not task:
        abort(404, description="task not found")
    return jsonify({"deleted": tid})


# ── internal worker ↔ coordinator protocol ───────────────────────────────────

@app.route("/task/next", methods=["POST"])
@require_token
def claim_task():
    """Worker calls this to atomically claim the next pending task."""
    worker = (request.get_json(silent=True) or {}).get("worker", request.remote_addr)
    with _lock:
        while task_queue:
            tid = task_queue.popleft()
            task = task_registry.get(tid)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.RUNNING
                task.assigned_to = worker
                task.started_at = datetime.now()
                return jsonify(task.to_dict()), 200
    return "", 204


@app.route("/task/<tid>/result", methods=["POST"])
@require_token
def report_result(tid):
    data = request.get_json() or {}
    if PP_COORDINATOR:
        r = _coordinator_post(f"/task/{tid}/result", json=data)
        return jsonify(r.json()), r.status_code

    with _lock:
        task = task_registry.get(tid)
        if not task:
            abort(404, description="task not found")
        task.result = data.get("result")
        task.error = data.get("error")
        task.status = TaskStatus.DONE if data.get("success") else TaskStatus.FAILED
        task.finished_at = datetime.now()

    return jsonify(task.to_dict())


# ── node registry (coordinator only) ─────────────────────────────────────────

@app.route("/nodes")
@require_token
def list_nodes():
    if PP_COORDINATOR:
        r = _coordinator_get("/nodes")
        return jsonify(r.json()), r.status_code
    with _lock:
        nodes = list(node_registry.values())
    return jsonify(nodes)


@app.route("/register", methods=["POST"])
@require_token
def register_node():
    data = request.get_json() or {}
    name = data.get("name")
    url = data.get("url")
    if not name or not url:
        abort(400, description="'name' and 'url' are required")
    with _lock:
        node_registry[name] = {
            "name": name,
            "url": url,
            "last_seen": datetime.now().isoformat(),
            "info": data.get("info", {}),
        }
    return jsonify({"ok": True, "name": name})


# ── worker loop (background thread on every node) ────────────────────────────

def _run_command(command: str, timeout: int = 300) -> tuple[bool, str, str]:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode == 0, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"timeout after {timeout}s"
    except Exception as exc:
        return False, "", str(exc)


def worker_loop(coordinator_url: str, is_self: bool = False):
    if is_self:
        time.sleep(2)  # wait for Flask to bind

    # Register with coordinator
    while True:
        try:
            device.update_status()
            requests.post(
                f"{coordinator_url}/register",
                json={
                    "name": PP_NAME,
                    "url": f"http://{device.ip_address}:{PP_PORT}",
                    "info": {
                        "cpu": device.cpu_name,
                        "cores": device.cpu_cores,
                        "ram_gb": device.ram_gb,
                    },
                },
                headers={"X-Token": PP_TOKEN},
                timeout=5,
            )
            print(f"[{PP_NAME}] registered with coordinator at {coordinator_url}")
            break
        except Exception as exc:
            print(f"[{PP_NAME}] registration failed ({exc}), retrying in 5s…")
            time.sleep(5)

    # Poll → execute → report
    while True:
        try:
            resp = requests.post(
                f"{coordinator_url}/task/next",
                json={"worker": PP_NAME},
                headers={"X-Token": PP_TOKEN},
                timeout=5,
            )
            if resp.status_code == 200:
                task_data = resp.json()
                tid = task_data["id"]
                cmd = task_data["command"]
                print(f"[{PP_NAME}] running task {tid}: {cmd!r}")

                success, result, error = _run_command(cmd)

                requests.post(
                    f"{coordinator_url}/task/{tid}/result",
                    json={"success": success, "result": result, "error": error or None},
                    headers={"X-Token": PP_TOKEN},
                    timeout=10,
                )
                print(f"[{PP_NAME}] task {tid} {'done' if success else 'FAILED'}")
            else:
                time.sleep(2)
        except Exception as exc:
            print(f"[{PP_NAME}] worker error: {exc}")
            time.sleep(5)


# ── entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    coordinator_url = PP_COORDINATOR or f"http://localhost:{PP_PORT}"
    is_self = not PP_COORDINATOR

    role = "coordinator + worker" if is_self else f"worker → {PP_COORDINATOR}"
    print(f"[PatientPredator] {PP_NAME}  |  role: {role}  |  port: {PP_PORT}")
    if PP_TOKEN == "changeme":
        print("[PatientPredator] WARNING: using default token — set PP_TOKEN in production")

    t = threading.Thread(target=worker_loop, args=(coordinator_url, is_self), daemon=True)
    t.start()

    app.run(host="0.0.0.0", port=PP_PORT, debug=False)
