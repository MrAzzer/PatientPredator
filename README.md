iterator kolejkujacy taski,
klasa dla workera

komunikacja zasobow

klasa dla komputera

memory swap. klastrowanie urzadzen
task distribution


floow:

na kazdym komputerze jest usluga na porcie :nie wiem np 4200


echo 'export PATH="$PATH:$HOME/patientpredator"' >> ~/.zshrc
source ~/.zshrc

(venv) spike@spikes-MacBook-Air PatientPredator % source venv/bin/activate
PP_TOKEN=test python3 agent.py


# PatientPredator

Distributed task execution over VPN. Each machine runs one agent — tasks submitted to the coordinator are automatically pulled and executed by all connected workers.

---

## Quick install

```bash
curl -fsSL https://raw.githubusercontent.com/MrAzzer/PatientPredator/main/install.sh | bash
```

The script clones the repo, creates a virtualenv, installs dependencies, and asks three questions:

| Question | Example |
|---|---|
| Token | `mysecret` (same on all nodes) |
| Node name | `rig-1` |
| Coordinator URL | blank if this is the coordinator, `http://10.8.0.1:4200` otherwise |

Then start the agent:

```bash
~/patientpredator/start.sh
```

---

## Architecture

```
                    VPN (10.8.0.x)
                         │
              ┌──────────┴──────────┐
              │     coordinator     │  ← task queue, node registry
              │  10.8.0.1:4200      │  ← also executes tasks itself
              └──────────┬──────────┘
          ┌──────────────┼──────────────┐
          │              │              │
     worker-1        worker-2       worker-3
  10.8.0.2:4200   10.8.0.3:4200  10.8.0.4:4200
```

- Every node exposes a Flask API on port **4200**
- Workers register themselves on startup and poll the coordinator for tasks
- Tasks are shell commands — result (stdout/stderr) is stored on the coordinator
- Auth via shared token in `X-Token` header

---

## Manual setup (without install script)

```bash
git clone https://github.com/MrAzzer/PatientPredator
cd PatientPredator
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Coordinator node
PP_TOKEN=mysecret python3 agent.py

# Worker nodes
PP_TOKEN=mysecret PP_COORDINATOR=http://10.8.0.1:4200 PP_NAME=rig-2 python3 agent.py
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PP_TOKEN` | `changeme` | Shared secret — set the same on all nodes |
| `PP_PORT` | `4200` | Port to listen on |
| `PP_NAME` | hostname | Name shown in the node registry |
| `PP_COORDINATOR` | *(empty)* | URL of coordinator. Empty = this node is coordinator |

---

## API reference

All endpoints require header `X-Token: <token>` (or `?token=<token>`).

### Device info

```bash
# Hardware specs
curl -H "X-Token: mysecret" http://10.8.0.1:4200/info

# Live metrics (CPU%, RAM%, temp)
curl -H "X-Token: mysecret" http://10.8.0.1:4200/status
```

### Nodes

```bash
# List all registered workers
curl -H "X-Token: mysecret" http://10.8.0.1:4200/nodes
```

### Tasks

```bash
# Submit a task (runs on next available worker)
curl -X POST http://10.8.0.1:4200/task \
     -H "X-Token: mysecret" \
     -H "Content-Type: application/json" \
     -d '{"command": "python3 ~/myjob.py", "name": "my-job"}'

# List all tasks
curl -H "X-Token: mysecret" http://10.8.0.1:4200/tasks

# Get result of a specific task
curl -H "X-Token: mysecret" http://10.8.0.1:4200/task/<id>

# Delete a task
curl -X DELETE -H "X-Token: mysecret" http://10.8.0.1:4200/task/<id>
```

### Task status values

| Status | Meaning |
|---|---|
| `pending` | waiting in queue |
| `running` | claimed by a worker |
| `done` | finished successfully |
| `failed` | non-zero exit or timeout (300s) |

---

## Example workflow

```bash
# 1. Submit 5 jobs from your laptop (or any node)
for i in 1 2 3 4 5; do
  curl -s -X POST http://10.8.0.1:4200/task \
       -H "X-Token: mysecret" \
       -H "Content-Type: application/json" \
       -d "{\"command\": \"python3 ~/train.py --shard $i\", \"name\": \"shard-$i\"}"
done

# 2. Watch progress
watch -n2 'curl -s -H "X-Token: mysecret" http://10.8.0.1:4200/tasks | python3 -m json.tool'

# 3. Fetch result
curl -s -H "X-Token: mysecret" http://10.8.0.1:4200/task/abc12345 | python3 -m json.tool
```

---

## Files

| File | Purpose |
|---|---|
| `agent.py` | Main agent — Flask API + worker loop |
| `device.py` | Hardware info & live metrics |
| `task.py` | Task model |
| `install.sh` | Bootstrap installer |
| `requirements.txt` | Python dependencies |
