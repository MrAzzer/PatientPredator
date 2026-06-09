#!/usr/bin/env bash
# PatientPredator — one-liner install
# Usage:  curl -fsSL https://raw.githubusercontent.com/MrAzzer/PatientPredator/main/install.sh | bash
set -euo pipefail

REPO_URL="https://github.com/MrAzzer/PatientPredator"
INSTALL_DIR="$HOME/patientpredator"

# clone or update 
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "[PP] updating existing install in $INSTALL_DIR"
    git -C "$INSTALL_DIR" pull --ff-only
else
    echo "[PP] cloning into $INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# virtualenv 
if [ ! -d venv ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# config 
ENV_FILE="$INSTALL_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo "=== PatientPredator setup ==="
    read -rp "Token (shared secret for all nodes): " TOKEN
    read -rp "This node's name (leave blank for hostname): " NAME
    read -rp "Coordinator URL — leave blank if THIS node is the coordinator (e.g. http://10.0.0.1:4200): " COORDINATOR

    cat > "$ENV_FILE" <<EOF
PP_TOKEN=${TOKEN}
PP_NAME=${NAME:-$(hostname)}
PP_PORT=4200
PP_COORDINATOR=${COORDINATOR}
EOF
    echo "[PP] config saved to $ENV_FILE"
else
    echo "[PP] existing config found at $ENV_FILE — skipping setup"
fi

# launcher script 
LAUNCHER="$INSTALL_DIR/start.sh"
cat > "$LAUNCHER" <<'LAUNCH'
#!/usr/bin/env bash
set -a
source "$(dirname "$0")/.env"
set +a
source "$(dirname "$0")/venv/bin/activate"
exec python3 "$(dirname "$0")/agent.py"
LAUNCH
chmod +x "$LAUNCHER"

# ── pyprd CLI symlink ─────────────────────────────────────────────────────────
chmod +x "$INSTALL_DIR/pyprd"
if [ -w /usr/local/bin ]; then
    ln -sf "$INSTALL_DIR/pyprd" /usr/local/bin/pyprd
    echo "[PP] pyprd linked to /usr/local/bin/pyprd"
elif sudo -n true 2>/dev/null; then
    sudo ln -sf "$INSTALL_DIR/pyprd" /usr/local/bin/pyprd
    echo "[PP] pyprd linked to /usr/local/bin/pyprd"
else
    echo "[PP] add to PATH manually:  export PATH=\"\$PATH:$INSTALL_DIR\""
fi

# done
echo ""
echo "=== PatientPredator installed ==="
echo "  Start agent:  $LAUNCHER"
echo "  Config:       $ENV_FILE"
echo ""
echo "CLI (once agent is running):"
echo "  pyprd status            — live CPU/RAM/temp for all nodes"
echo "  pyprd nodes             — registered nodes"
echo "  pyprd tasks             — task queue"
echo "  pyprd run 'cmd' -n name — submit a task"
echo "  pyprd result <id>       — fetch result"
