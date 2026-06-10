"""
pyprd — PatientPredator CLI
Usage: pyprd <command> [args]
"""

import argparse
import concurrent.futures
import os
import sys
from pathlib import Path

import requests


# ── load .env ─────────────────────────────────────────────────────────────────

def _load_env():
    for candidate in [Path(__file__).parent / ".env", Path.cwd() / ".env"]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()

TOKEN       = os.environ.get("PP_TOKEN", "changeme")
PORT        = os.environ.get("PP_PORT", "4200")
_coord_env  = os.environ.get("PP_COORDINATOR", "").rstrip("/")
COORDINATOR = _coord_env or f"http://localhost:{PORT}"


# ── ANSI ──────────────────────────────────────────────────────────────────────

def _no_color():
    return not sys.stdout.isatty() or os.environ.get("NO_COLOR")

class C:
    GREEN  = "" if _no_color() else "\033[92m"
    RED    = "" if _no_color() else "\033[91m"
    YELLOW = "" if _no_color() else "\033[93m"
    CYAN   = "" if _no_color() else "\033[96m"
    BOLD   = "" if _no_color() else "\033[1m"
    DIM    = "" if _no_color() else "\033[2m"
    RESET  = "" if _no_color() else "\033[0m"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(path, base=None, timeout=5):
    url = (base or COORDINATOR) + path
    return requests.get(url, headers={"X-Token": TOKEN}, timeout=timeout)

def _post(path, data=None, base=None, timeout=5):
    url = (base or COORDINATOR) + path
    return requests.post(url, json=data or {}, headers={"X-Token": TOKEN}, timeout=timeout)

def _delete(path, base=None, timeout=5):
    url = (base or COORDINATOR) + path
    return requests.delete(url, headers={"X-Token": TOKEN}, timeout=timeout)

def _die(msg):
    print(f"{C.RED}error:{C.RESET} {msg}", file=sys.stderr)
    sys.exit(1)


# ── bar helper ────────────────────────────────────────────────────────────────

def _bar(pct, width=10):
    filled = round(pct / 100 * width)
    color = C.RED if pct > 80 else C.YELLOW if pct > 50 else C.GREEN
    return color + "█" * filled + C.DIM + "░" * (width - filled) + C.RESET


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_status(_args):
    try:
        r = _get("/nodes")
        if r.status_code == 401:
            _die(f"wrong token — check PP_TOKEN in .env (currently: '{TOKEN}')")
        nodes = r.json()
    except requests.exceptions.ConnectionError:
        _die(f"agent not running at {COORDINATOR} — start it with: python3 agent.py")
    except Exception as exc:
        _die(f"coordinator error at {COORDINATOR}: {exc}")

    if not nodes:
        print(f"{C.YELLOW}no nodes registered yet — are any agents running?{C.RESET}")
        return

    def fetch(node):
        try:
            s = requests.get(
                f"{node['url']}/status",
                headers={"X-Token": TOKEN},
                timeout=3,
            ).json()
            return node, s, True
        except Exception:
            return node, {}, False

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        results = sorted(ex.map(fetch, nodes), key=lambda r: r[0]["name"])

    online = sum(1 for _, _, ok in results if ok)
    print(f"\n{C.BOLD}NODES  {online}/{len(nodes)} online{C.RESET}   coordinator: {C.CYAN}{COORDINATOR}{C.RESET}\n")
    print(f"  {'NAME':<22} {'URL':<28} {'CPU':>14}  {'RAM':>14}  {'TEMP':>6}  {'NET':<12}")
    print("  " + "─" * 82)

    for node, s, ok in results:
        name = f"{C.BOLD}{node['name']:<22}{C.RESET}"
        url  = f"{C.DIM}{node.get('url',''):<28}{C.RESET}"
        if ok:
            cpu  = s.get("cpu_pct", 0)
            ram  = s.get("ram_pct", 0)
            temp = s.get("temp_c", 0)
            net  = s.get("network", "?")
            net_col = C.GREEN if net == "connected" else C.RED
            print(
                f"  {name} {url} "
                f"{_bar(cpu)} {cpu:5.1f}%  "
                f"{_bar(ram)} {ram:5.1f}%  "
                f"{temp:5.0f}°  "
                f"{net_col}{net}{C.RESET}"
            )
        else:
            print(f"  {name} {url} {C.RED}OFFLINE{C.RESET}")

    print()


def cmd_nodes(_args):
    try:
        nodes = _get("/nodes").json()
    except Exception as exc:
        _die(f"cannot reach coordinator at {COORDINATOR} ({exc})")

    if not nodes:
        print("no nodes registered")
        return

    for n in sorted(nodes, key=lambda x: x["name"]):
        info = n.get("info", {})
        seen = n.get("last_seen", "?")[:19]
        print(
            f"  {C.BOLD}{n['name']:<20}{C.RESET}  {n.get('url',''):<28}"
            f"  cores:{info.get('cores','?')}  ram:{info.get('ram_gb','?')}GB"
            f"  {C.DIM}seen {seen}{C.RESET}"
        )


def cmd_tasks(args):
    try:
        tasks = _get("/tasks").json()
    except Exception as exc:
        _die(f"cannot reach coordinator ({exc})")

    if not tasks:
        print("no tasks")
        return

    status_filter = getattr(args, "filter", None)
    if status_filter:
        tasks = [t for t in tasks if t["status"] == status_filter]

    STATUS_COLOR = {
        "pending": C.YELLOW,
        "running": C.CYAN,
        "done":    C.GREEN,
        "failed":  C.RED,
    }

    tasks.sort(key=lambda t: t["created_at"], reverse=True)
    print(f"\n  {'ID':<10} {'NAME':<20} {'STATUS':<10} {'WORKER':<22} {'CREATED'}")
    print("  " + "─" * 80)
    for t in tasks:
        sc = STATUS_COLOR.get(t["status"], "")
        worker = t.get("assigned_to") or "—"
        created = t["created_at"][:19]
        print(
            f"  {C.BOLD}{t['id']:<10}{C.RESET}"
            f" {t['name']:<20}"
            f" {sc}{t['status']:<10}{C.RESET}"
            f" {worker:<22}"
            f" {C.DIM}{created}{C.RESET}"
        )
    print()


def cmd_run(args):
    data = {"command": args.command}
    if args.name:
        data["name"] = args.name
    try:
        r = _post("/task", data)
        r.raise_for_status()
        t = r.json()
    except Exception as exc:
        _die(f"submit failed ({exc})")

    print(f"{C.GREEN}submitted{C.RESET}  id={C.BOLD}{t['id']}{C.RESET}  name={t['name']}")
    print(f"  check:  pyprd result {t['id']}")


def cmd_result(args):
    try:
        r = _get(f"/task/{args.id}")
        if r.status_code == 404:
            _die(f"task '{args.id}' not found")
        t = r.json()
    except Exception as exc:
        _die(f"request failed ({exc})")

    STATUS_COLOR = {"done": C.GREEN, "failed": C.RED, "running": C.CYAN, "pending": C.YELLOW}
    sc = STATUS_COLOR.get(t["status"], "")

    print(f"\n  {C.BOLD}{t['id']}{C.RESET}  {t['name']}")
    print(f"  status:   {sc}{t['status']}{C.RESET}")
    print(f"  worker:   {t.get('assigned_to') or '—'}")
    print(f"  command:  {C.DIM}{t['command']}{C.RESET}")
    if t.get("started_at"):
        dur = ""
        if t.get("finished_at"):
            from datetime import datetime
            s = datetime.fromisoformat(t["started_at"])
            f = datetime.fromisoformat(t["finished_at"])
            dur = f"  ({(f-s).total_seconds():.1f}s)"
        print(f"  time:     {t['started_at'][11:19]} → {(t.get('finished_at') or '…')[11:19]}{dur}")

    if t.get("result"):
        print(f"\n{C.BOLD}── stdout ──────────────────────────────{C.RESET}")
        print(t["result"].rstrip())

    if t.get("error"):
        print(f"\n{C.BOLD}{C.RED}── stderr ──────────────────────────────{C.RESET}")
        print(t["error"].rstrip())

    print()


def cmd_rm(args):
    try:
        r = _delete(f"/task/{args.id}")
        if r.status_code == 404:
            _die(f"task '{args.id}' not found")
        elif r.status_code != 204:
            _die(f"delete failed ({r.status_code})")
    except Exception as exc:
        _die(f"request failed ({exc})")

    print(f"{C.GREEN}deleted{C.RESET} task {C.BOLD}{args.id}{C.RESET}")

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        prog="pyprd",
        description="PatientPredator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  pyprd status\n"
               "  pyprd run 'python3 ~/train.py' -n my-job\n"
               "  pyprd tasks\n"
               "  pyprd result abc12345",
    )
    sub = p.add_subparsers(dest="cmd", metavar="command")
    sub.required = True

    sub.add_parser("status", help="live CPU/RAM/temp for all nodes")
    sub.add_parser("nodes",  help="registered nodes (no live metrics)")

    tp = sub.add_parser("tasks", help="list tasks")
    tp.add_argument("--filter", choices=["pending","running","done","failed"], metavar="STATUS")

    rp = sub.add_parser("run", help="submit a task")
    rp.add_argument("command", help="shell command to run")
    rp.add_argument("-n", "--name", default=None, help="task name")

    res = sub.add_parser("result", help="show task result")
    res.add_argument("id", help="task id")

    rm = sub.add_parser("rm", help="delete a task")
    rm.add_argument("id", help="task id")

    args = p.parse_args()
    {"status": cmd_status, "nodes": cmd_nodes, "tasks": cmd_tasks,
     "run": cmd_run, "result": cmd_result, "rm": cmd_rm}[args.cmd](args)


if __name__ == "__main__":
    main()
