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

cd /home/arif/agy-hermes
export PYTHONPATH="/home/arif/agy-hermes:$PYTHONPATH"
python3 -m gemini_hermes.cli start >> /home/arif/agy-hermes/gemini-hermes.log 2>&1 &
echo $! > /home/arif/agy-hermes/gemini-hermes.pid
