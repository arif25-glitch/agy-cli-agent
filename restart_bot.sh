#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

old_pids=$(pgrep -f "gemini_hermes.cli start")
if [ -n "$old_pids" ]; then
    # Wait briefly for any child process of the bot to finish
    for pid in $old_pids; do
        count=0
        while pgrep -P "$pid" > /dev/null 2>&1 && [ $count -lt 5 ]; do
            sleep 1
            count=$((count + 1))
        done
    done
    kill -9 $old_pids 2>/dev/null || true
fi
sleep 1

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

if [ -d "$SCRIPT_DIR/.venv/bin" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
else
    PYTHON_BIN="python3"
fi

nohup $PYTHON_BIN -m gemini_hermes.cli start >> "$SCRIPT_DIR/gemini-hermes.log" 2>&1 &
BOT_PID=$!
disown $BOT_PID 2>/dev/null || true
echo $BOT_PID > "$SCRIPT_DIR/gemini-hermes.pid"
echo "Gemini-Hermes started with PID $BOT_PID"
