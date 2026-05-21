#!/bin/bash
cd "$(dirname "$0")"
[ -d venv ] || python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -q
echo "
  ╔═══════════════════════════════════════════════════════════╗
  ║   INNtelligence by The Gracious Collection — Pricing Engine ║
  ║   http://localhost:5001                                  ║
  ║   Ctrl-C to stop                                         ║
  ╚═══════════════════════════════════════════════════════════╝
"
python app.py
