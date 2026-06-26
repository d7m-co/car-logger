#!/bin/bash
set -e

if [ "${1:-}" == "--dry-run" ]; then
  echo "Dry run: install steps will not be executed."
  exit 0
fi

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

echo ""
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║     🚗 Car Security Logger               ║"
echo "  ║         One-Click Install                ║"
echo "  ╚═══════════════════════════════════════════╝"
echo ""

echo "  [1/4] 📦 Installing system dependencies..."
sleep 0.5
sudo apt update -qq
echo "  ✓ Package lists updated"
sleep 0.3
sudo apt install -y -qq python3-opencv python3-pip python3-venv geoclue-2.0 > /dev/null 2>&1
echo "  ✓ python3-opencv, pip, venv, geoclue installed"
sleep 0.5

echo ""
echo "  [2/4] 📦 Setting up Python virtual environment..."
sleep 0.3
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
if [ $? -eq 0 ]; then
  echo "  ✓ All Python packages installed"
else
  echo "  ⚠ Python packages may have failed, continuing..."
fi
deactivate
sleep 0.5

echo ""
echo "  [3/4] 🔗 Installing 'carlogger' command..."
sleep 0.3
cat > "$REPO_DIR/carlogger" <<'EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
exec python3 "$SCRIPT_DIR/main.py" "$@"
EOF
chmod +x "$REPO_DIR/carlogger"
sudo ln -sf "$REPO_DIR/carlogger" /usr/local/bin/carlogger
echo "  ✓ Type 'carlogger' anywhere to launch"
sleep 0.5

echo ""
echo "  [4/4] 🚀 Launching Car Logger..."
sleep 0.5

echo ""
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║  ✅ Car Logger is ready!                  ║"
echo "  ║                                          ║"
echo "  ║  First time? Open the dashboard →        ║"
echo "  ║  Settings → paste your OpenRouter API key ║"
echo "  ║                                          ║"
echo "  ║  📱 Phone: http://<this-ip>:5000         ║"
echo "  ╚═══════════════════════════════════════════╝"
echo ""

sleep 1
carlogger
