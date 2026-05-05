#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ ! -f "venv/bin/activate" ]; then
  echo "ERROR: venv not found."
  echo "  Run: python -m venv venv && venv/bin/pip install -r requirements.txt"
  exit 1
fi

source venv/bin/activate

echo ""
echo "  ╔═══════════════════════════════════════════════╗"
echo "  ║   Anchorage 1770 Inn — Pricing Dashboard      ║"
echo "  ║   http://localhost:5000                       ║"
echo "  ║   Ctrl-C to stop                              ║"
echo "  ╚═══════════════════════════════════════════════╝"
echo ""

python app.py
