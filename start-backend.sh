#!/usr/bin/env bash
# HealthOS Posture Monitor — Backend launcher
# Usage: ./start-backend.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/ai-engine/venv"

# Create venv if missing
if [ ! -d "$VENV" ]; then
  echo "📦 Creating Python virtual environment …"
  python3 -m venv "$VENV"
fi

# Activate and install deps
source "$VENV/bin/activate"
pip install -q -r "$SCRIPT_DIR/ai-engine/requirements.txt"

echo "🚀 Starting AI engine on http://127.0.0.1:5000"
python "$SCRIPT_DIR/ai-engine/app.py"
