#!/usr/bin/env bash
# Wait for any active agy execution to complete and deliver its response
while pgrep -f "/root/.local/bin/agy" > /dev/null; do
    sleep 1
done
# Extra grace period for Telegram message delivery to complete
sleep 2

# Terminate previous bot process
old_pids=$(pgrep -f "gemini_hermes.cli start")
if [ -n "$old_pids" ]; then
    kill -9 $old_pids 2>/dev/null || true
fi
sleep 1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

if [ -d "$SCRIPT_DIR/.venv/bin" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
else
    PYTHON_BIN="python3"
fi

$PYTHON_BIN -m gemini_hermes.cli start >> "$SCRIPT_DIR/gemini-hermes.log" 2>&1 &
echo $! > "$SCRIPT_DIR/gemini-hermes.pid"

