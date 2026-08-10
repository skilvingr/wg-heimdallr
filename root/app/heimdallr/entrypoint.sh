#!/bin/bash
set -e

cat << 'EOF'
─────────────────────────────────────────────────────────────────
                     _          _               _       _ _
__      ____ _      | |__   ___(_)_ __ ___   __| | __ _| | |_ __
\ \ /\ / / _` |_____| '_ \ / _ \ | '_ ` _ \ / _` |/ _` | | | '__|
 \ V  V / (_| |_____| | | |  __/ | | | | | | (_| | (_| | | | |
  \_/\_/ \__, |     |_| |_|\___|_|_| |_| |_|\__,_|\__,_|_|_|_|
         |___/

─────────────────────────────────────────────────────────────────
EOF

echo "[heimdallr] Running init..."
/app/heimdallr/init.sh

echo "[heimdallr] Starting services..."
python3 /app/heimdallr/auth_server.py &
python3 /app/heimdallr/cleanup.py &

# Wait for all children; tini handles reaping + signals
wait
