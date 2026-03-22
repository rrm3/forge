#!/usr/bin/env bash
# Dev server management: start, stop, restart, status
# Usage: ./scripts/dev.sh [start|stop|restart|status]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIDFILE_BACKEND="/tmp/forge-backend.pid"
PIDFILE_FRONTEND="/tmp/forge-frontend.pid"

kill_port() {
    local port=$1
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 0.5
    fi
}

do_stop() {
    echo "Stopping dev servers..."
    # Kill by PID files first
    for pf in "$PIDFILE_BACKEND" "$PIDFILE_FRONTEND"; do
        if [ -f "$pf" ]; then
            kill -9 "$(cat "$pf")" 2>/dev/null || true
            rm -f "$pf"
        fi
    done
    # Then kill anything still on the ports
    kill_port 8000
    kill_port 5173
    echo "Stopped."
}

do_start() {
    # Ensure ports are free
    kill_port 8000
    kill_port 5173

    echo "Starting backend on :8000..."
    cd "$REPO_ROOT"
    uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/forge-backend.log 2>&1 &
    echo $! > "$PIDFILE_BACKEND"

    echo "Starting frontend on :5173..."
    cd "$REPO_ROOT/frontend"
    npm run dev > /tmp/forge-frontend.log 2>&1 &
    echo $! > "$PIDFILE_FRONTEND"

    # Wait for servers to be ready
    for i in {1..20}; do
        if lsof -ti :8000 >/dev/null 2>&1 && lsof -ti :5173 >/dev/null 2>&1; then
            echo "Both servers running."
            echo "  Backend:  http://localhost:8000  (log: /tmp/forge-backend.log)"
            echo "  Frontend: http://localhost:5173  (log: /tmp/forge-frontend.log)"
            return 0
        fi
        sleep 0.5
    done
    echo "Warning: servers may not be fully ready yet. Check logs."
}

do_status() {
    local backend_up=false frontend_up=false
    lsof -ti :8000 >/dev/null 2>&1 && backend_up=true
    lsof -ti :5173 >/dev/null 2>&1 && frontend_up=true
    echo "Backend  :8000  $([ "$backend_up" = true ] && echo "UP" || echo "DOWN")"
    echo "Frontend :5173  $([ "$frontend_up" = true ] && echo "UP" || echo "DOWN")"
}

case "${1:-start}" in
    start)   do_start ;;
    stop)    do_stop ;;
    restart) do_stop; do_start ;;
    status)  do_status ;;
    *)       echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
