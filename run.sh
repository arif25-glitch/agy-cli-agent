#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/gemini-hermes.pid"
LOG_FILE="$SCRIPT_DIR/gemini-hermes.log"

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Auto-detect virtual environment if present
if [ -d "$SCRIPT_DIR/.venv/bin" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
else
    PYTHON_BIN="python3"
fi

show_help() {
    echo "Usage: ./run.sh {config|setup|start|start-jev|background|background-jev|stop|status|logs|monitor|test|memory|jev}"
    echo ""
    echo "Commands:"
    echo "  config          Configure TypeSafe AI (Jev) API key & decision settings"
    echo "  setup           Run interactive wizard to configure Bot Token & User ID"
    echo "  start           Start Gemini-Hermes bot in the foreground (standard pure engine)"
    echo "  start-jev       Start Gemini-Hermes with Jev AI System-One Dynamic Reasoning Effort Selector"
    echo "  background      Start Gemini-Hermes bot in background daemon mode"
    echo "  background-jev  Start Gemini-Hermes daemon with Jev AI Dynamic Reasoning Effort Selector"
    echo "  stop            Stop the background Gemini-Hermes daemon"
    echo "  status          Check whether the daemon is running"
    echo "  logs            Follow the live log output"
    echo "  monitor         Launch interactive live Terminal UI Dashboard"
    echo "  test            Run system diagnostics and health checks"
    echo "  memory          Inspect or update persistent memory files"
    echo "  jev             Launch interactive Jev AI reflex playground or test a prompt"
    echo ""
}

check_jev_key() {
    local key="${TYPESAFE_API_KEY:-${JEV_API_KEY:-}}"
    if [ -z "$key" ] && [ -f "$SCRIPT_DIR/.env" ]; then
        key=$(grep -E '^(TYPESAFE_API_KEY|JEV_API_KEY)=' "$SCRIPT_DIR/.env" 2>/dev/null | cut -d '=' -f2- | tr -d '"' | tr -d "'" | tr -d ' ' | head -n1 || true)
    fi
    if [ -z "$key" ]; then
        echo "================================================================"
        echo "❌ Error: Jev AI Accelerated Mode requires a TypeSafe AI / Jev API key."
        echo "================================================================"
        echo "To configure your TypeSafe API key:"
        echo "  1. Get your API key from: https://console.typesafe.ai/keys"
        echo "  2. Run: ./run.sh config (or add TYPESAFE_API_KEY=... to .env)"
        echo ""
        echo "💡 To start Gemini-Hermes in standard mode without Jev AI, run:"
        echo "  ./run.sh start         (foreground)"
        echo "  ./run.sh background    (background daemon)"
        echo "================================================================"
        return 1
    fi
    return 0
}

case "$1" in
    monitor)
        shift
        $PYTHON_BIN -m gemini_hermes.cli monitor "$@"
        ;;
    jev)
        shift
        $PYTHON_BIN "$SCRIPT_DIR/scripts/interactive_jev_reflex.py" "$@"
        ;;
    config)
        shift
        $PYTHON_BIN -m gemini_hermes.cli config "$@"
        ;;
    memory)
        shift
        $PYTHON_BIN -m gemini_hermes.cli memory "$@"
        ;;
    setup)
        $PYTHON_BIN -m gemini_hermes.cli setup
        ;;
    test)
        $PYTHON_BIN -m gemini_hermes.cli test
        ;;
    start)
        echo "Starting Gemini-Hermes in foreground (standard engine)..."
        exec $PYTHON_BIN -m gemini_hermes.cli start
        ;;
    start-jev)
        if ! check_jev_key; then
            exit 1
        fi
        echo "Starting Gemini-Hermes with Jev AI Dynamic Model & Effort Selector..."
        export JEV_ENABLED=true
        export JEV_DYNAMIC_EFFORT=true
        export JEV_DYNAMIC_MODEL=true
        exec $PYTHON_BIN -m gemini_hermes.cli start --jev
        ;;
    background)
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "⚠️ Gemini-Hermes is already running (PID: $(cat "$PID_FILE"))"
            exit 0
        fi
        echo "Starting Gemini-Hermes in background..."
        nohup $PYTHON_BIN -m gemini_hermes.cli start >> "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        echo "✅ Gemini-Hermes started in background with PID: $(cat "$PID_FILE")"
        echo "View logs with: ./run.sh logs"
        ;;
    background-jev)
        if ! check_jev_key; then
            exit 1
        fi
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "⚠️ Gemini-Hermes is already running (PID: $(cat "$PID_FILE"))"
            exit 0
        fi
        echo "Starting Gemini-Hermes with Jev AI Dynamic Model & Effort in background..."
        export JEV_ENABLED=true
        export JEV_DYNAMIC_EFFORT=true
        export JEV_DYNAMIC_MODEL=true
        nohup $PYTHON_BIN -m gemini_hermes.cli start --jev >> "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        echo "✅ Gemini-Hermes (Jev enabled) started in background with PID: $(cat "$PID_FILE")"
        echo "View logs with: ./run.sh logs"
        ;;
    stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "Stopping Gemini-Hermes (PID: $PID)..."
                kill "$PID"
                rm -f "$PID_FILE"
                echo "✅ Gemini-Hermes stopped."
            else
                echo "⚠️ Process $PID is not running. Removing stale PID file."
                rm -f "$PID_FILE"
            fi
        else
            echo "⚠️ Gemini-Hermes is not running (no PID file found)."
        fi
        ;;
    status)
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "🟢 Gemini-Hermes is running (PID: $(cat "$PID_FILE"))"
        else
            echo "⚪ Gemini-Hermes is stopped."
        fi
        ;;
    logs)
        if [ -f "$LOG_FILE" ]; then
            tail -n 50 -f "$LOG_FILE"
        else
            echo "Log file $LOG_FILE does not exist yet."
        fi
        ;;
    *)
        show_help
        exit 1
        ;;
esac
