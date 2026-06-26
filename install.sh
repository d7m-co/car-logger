#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "  🚗 Installing Car Logger..."

sudo ln -sf "$REPO_DIR/carlogger" /usr/local/bin/carlogger
echo "  ✅ Command 'carlogger' installed (type it anywhere)"

echo ""
echo "  ──────────────────────────────────────"
echo "  Ready! Just run:"
echo "    carlogger"
echo ""
echo "  First run will open the dashboard."
echo "  Paste your OpenRouter API key in Settings."
echo "  ──────────────────────────────────────"
