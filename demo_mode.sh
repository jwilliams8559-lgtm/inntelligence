#!/usr/bin/env bash
# Launch INNtelligence in demo mode for an iPad or LAN-shared session.
# Prints the LAN-accessible URL so the iPad can connect to the same dashboard
# the Mac sees on localhost.
set -e

cd "$(dirname "$0")"

LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
LAN_IP=${LAN_IP:-localhost}

cat <<EOF

═══════════════════════════════════════════════════════════════
  INNtelligence by The Gracious Collection — Demo Mode
  Dashboard (Mac):   http://localhost:5173
  Dashboard (iPad):  http://$LAN_IP:5173
  API:               http://$LAN_IP:5001
  Login:             demo@graciouscollection.com / demo2026
  Admin:             admin@graciouscollection.com / admin2026
═══════════════════════════════════════════════════════════════

EOF

# Start Flask in the background
source venv/bin/activate
python app.py > /tmp/tgc-flask.log 2>&1 &
FLASK_PID=$!
trap "kill $FLASK_PID 2>/dev/null" EXIT

# Wait briefly for Flask
sleep 2

# Start Vite in the foreground with VITE_API_URL pointing at the LAN IP
# so iPad requests proxy back to the right place.
cd dashboard
VITE_API_URL=http://$LAN_IP:5001 npm run dev -- --host 0.0.0.0
