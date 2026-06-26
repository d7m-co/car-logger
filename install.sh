#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

echo "  🚗 Car Logger - One-Click Install"
echo "  ────────────────────────────────"

echo "  📦 Installing system dependencies..."
sudo apt update -qq
sudo apt install -y -qq python3-opencv python3-pip geoclue-2.0 > /dev/null 2>&1

echo "  📦 Installing Python packages..."
pip3 install -q -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -q -r requirements.txt

echo "  🔗 Installing command..."
sudo ln -sf "$(pwd)/carlogger" /usr/local/bin/carlogger

echo ""
echo "  ✅ All done! Launching Car Logger..."
echo ""
carlogger
