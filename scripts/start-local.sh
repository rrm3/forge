#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Start backend
echo "Starting backend on :8000..."
cd "$REPO_ROOT"
uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!

# Start frontend
echo "Starting frontend on :5173..."
cd "$REPO_ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

# Clean up both on exit
cleanup() {
    echo "Stopping services..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Backend PID: $BACKEND_PID  Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop."
wait
