#!/usr/bin/env bash
sleep 4
# Kill previous bot process
kill 831 2>/dev/null || true
pkill -f "python3 -m gemini_hermes.cli start" 2>/dev/null || true
sleep 1
cd /gemini-hermes
nohup python3 -m gemini_hermes.cli start >> /gemini-hermes/gemini-hermes.log 2>&1 &
echo $! > /gemini-hermes/gemini-hermes.pid
