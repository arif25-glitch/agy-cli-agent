#!/usr/bin/env bash
sleep 5
# Cleanly terminate previous bot process
pkill -9 -f "gemini_hermes.cli start" 2>/dev/null || true
sleep 1
cd /gemini-hermes
export PYTHONPATH="/gemini-hermes:$PYTHONPATH"
nohup python3 -m gemini_hermes.cli start >> /gemini-hermes/gemini-hermes.log 2>&1 &
echo $! > /gemini-hermes/gemini-hermes.pid

