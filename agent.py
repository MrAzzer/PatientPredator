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
from flask import Flask, abort, jsonify, request, render_template_string

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


# ── UI ───────────────────────────────────────────────────────────────────────

_UI = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PatientPredator</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#e6edf3;font-family:'Courier New',monospace;font-size:13px}
header{padding:14px 24px;border-bottom:1px solid #30363d;display:flex;align-items:center;gap:12px}
h1{font-size:15px;color:#58a6ff;letter-spacing:2px;text-transform:uppercase}
.tag{background:#21262d;border:1px solid #30363d;border-radius:4px;padding:2px 8px;font-size:11px;color:#8b949e}
#ts{font-size:10px;color:#8b949e;margin-left:auto}
main{display:grid;grid-template-columns:1fr 1fr;height:calc(100vh - 99px)}
section{padding:16px 20px;overflow-y:auto;border-right:1px solid #30363d}
section:last-child{border-right:none}
.stitle{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#8b949e;margin-bottom:10px}
.node{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:11px 13px;margin-bottom:8px}
.nh{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.on{background:#3fb950;box-shadow:0 0 5px #3fb950}
.off{background:#f85149}
.nn{font-weight:bold}
.nu{color:#8b949e;font-size:11px;margin-left:auto}
.mg{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.ml{color:#8b949e;font-size:10px;margin-bottom:2px}
.bw{display:flex;align-items:center;gap:5px}
.bb{background:#21262d;border-radius:2px;height:5px;flex:1;overflow:hidden}
.bf{height:100%;border-radius:2px;transition:width .6s}
.bg{background:#3fb950}.by{background:#d29922}.br{background:#f85149}
.bp{font-size:11px;color:#8b949e;width:38px;text-align:right}
.mt{font-size:10px;color:#8b949e;margin-top:5px}
.task{background:#161b22;border:1px solid #30363d;border-radius:5px;padding:9px 12px;margin-bottom:5px;display:flex;align-items:center;gap:8px;cursor:pointer}
.task:hover{border-color:#58a6ff}
.tid{color:#58a6ff;font-size:11px;width:70px;flex-shrink:0}
.tn{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.badge{font-size:10px;padding:2px 7px;border-radius:10px;font-weight:bold;flex-shrink:0}
.pending{background:#2d2d00;color:#d29922;border:1px solid #d29922}
.running{background:#002d4a;color:#58a6ff;border:1px solid #58a6ff;animation:pulse 1.5s infinite}
.done{background:#0d2a0d;color:#3fb950;border:1px solid #3fb950}
.failed{background:#2d0d0d;color:#f85149;border:1px solid #f85149}
.tw{color:#8b949e;font-size:11px;width:110px;text-align:right;overflow:hidden;text-overflow:ellipsis;flex-shrink:0}
.empty{color:#8b949e;font-size:12px;padding:6px 0}
.fb{padding:10px 20px;background:#161b22;border-top:1px solid #30363d;display:flex;gap:8px}
input{background:#21262d;border:1px solid #30363d;border-radius:4px;color:#e6edf3;padding:6px 10px;font-family:inherit;font-size:12px}
input:focus{outline:none;border-color:#58a6ff}
.ci{flex:1}.ni{width:150px}
btn,button{background:#238636;border:1px solid #2ea043;border-radius:4px;color:#fff;padding:6px 14px;font-family:inherit;font-size:12px;cursor:pointer}
button:hover{background:#2ea043}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.detail{font-size:11px;color:#8b949e;margin-top:6px;word-break:break-all;display:none}
.task.expanded .detail{display:block}
</style>
</head>
<body>
<header>
  <h1>PatientPredator</h1>
  <span class="tag" id="coord"></span>
  <span id="ts">—</span>
</header>
<main>
  <section>
    <div class="stitle" id="nt">NODES</div>
    <div id="nl"></div>
  </section>
  <section>
    <div class="stitle" id="tt">TASKS</div>
    <div id="tl"></div>
  </section>
</main>
<div class="fb">
  <input class="ci" id="ci" placeholder="command, e.g.  python3 ~/myjob.py  or  echo hello" />
  <input class="ni" id="ni" placeholder="name (optional)" />
  <button onclick="sub()">+ Submit task</button>
</div>
<script>
const T="{{token}}",B=location.origin;
const h={"X-Token":T,"Content-Type":"application/json"};
function bc(p){return p>80?"br":p>50?"by":"bg"}
function bar(p){return `<div class="bw"><div class="bb"><div class="bf ${bc(p)}" style="width:${Math.min(p,100).toFixed(0)}%"></div></div><span class="bp">${p.toFixed(1)}%</span></div>`}
async function gs(url){try{const r=await fetch(url+"/status",{headers:h});return r.ok?r.json():null}catch{return null}}
async function refresh(){
  document.getElementById("coord").textContent=B;
  try{
    const nr=await fetch(B+"/nodes",{headers:h});
    const nodes=await nr.json();
    const ss=await Promise.all(nodes.map(n=>gs(n.url)));
    const on=ss.filter(Boolean).length;
    document.getElementById("nt").textContent=`NODES  ${on}/${nodes.length} online`;
    document.getElementById("nl").innerHTML=nodes.length?nodes.map((n,i)=>{
      const s=ss[i];
      if(!s)return`<div class="node"><div class="nh"><div class="dot off"></div><span class="nn">${n.name}</span><span class="nu">${n.url}</span></div><span style="color:#f85149;font-size:11px">OFFLINE</span></div>`;
      return`<div class="node"><div class="nh"><div class="dot on"></div><span class="nn">${n.name}</span><span class="nu">${n.url}</span></div><div class="mg"><div><div class="ml">CPU</div>${bar(s.cpu_pct||0)}</div><div><div class="ml">RAM</div>${bar(s.ram_pct||0)}</div></div><div class="mt">${s.temp_c?`${s.temp_c}°C &nbsp;·&nbsp; `:""}net: ${s.network||"?"}</div></div>`;
    }).join(""):`<div class="empty">no nodes registered</div>`;
  }catch(e){document.getElementById("nl").innerHTML=`<div class="empty">error: ${e.message}</div>`}
  try{
    const tr=await fetch(B+"/tasks",{headers:h});
    const tasks=await tr.json();
    tasks.sort((a,b)=>b.created_at.localeCompare(a.created_at));
    const cnt={};tasks.forEach(t=>cnt[t.status]=(cnt[t.status]||0)+1);
    const sum=Object.entries(cnt).map(([k,v])=>`${v} ${k}`).join("  ");
    document.getElementById("tt").textContent=`TASKS  ${tasks.length?sum:"empty"}`;
    document.getElementById("tl").innerHTML=tasks.length?tasks.map(t=>`
      <div class="task" onclick="this.classList.toggle('expanded')">
        <span class="tid">${t.id}</span>
        <span class="tn" title="${t.command}">${t.name}</span>
        <span class="badge ${t.status}">${t.status}</span>
        <span class="tw">${t.assigned_to||"—"}</span>
        <div class="detail"><b>cmd:</b> ${t.command}${t.result?`<br><b>out:</b> ${t.result.slice(0,200)}`:""}</div>
      </div>`).join(""):`<div class="empty">no tasks yet</div>`;
  }catch(e){document.getElementById("tl").innerHTML=`<div class="empty">error: ${e.message}</div>`}
  document.getElementById("ts").textContent="updated "+new Date().toLocaleTimeString();
}
async function sub(){
  const cmd=document.getElementById("ci").value.trim();
  const name=document.getElementById("ni").value.trim();
  if(!cmd)return;
  await fetch(B+"/task",{method:"POST",headers:h,body:JSON.stringify({command:cmd,name:name||undefined})});
  document.getElementById("ci").value="";
  document.getElementById("ni").value="";
  refresh();
}
document.getElementById("ci").addEventListener("keydown",e=>{if(e.key==="Enter")sub()});
refresh();
setInterval(refresh,3000);
</script>
</body>
</html>"""


@app.route("/")
def ui():
    return render_template_string(_UI, token=PP_TOKEN)


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
