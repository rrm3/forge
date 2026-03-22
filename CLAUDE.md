# Forge - Project Instructions

## Local Dev Servers
Use `./scripts/dev.sh` to manage backend + frontend:
* `./scripts/dev.sh start` - Kill existing processes on :8000/:5173 and start both
* `./scripts/dev.sh stop` - Stop both servers
* `./scripts/dev.sh restart` - Stop then start (use after backend changes that crash the frontend)
* `./scripts/dev.sh status` - Check if servers are running
* Logs: `/tmp/forge-backend.log`, `/tmp/forge-frontend.log`

Always use this script instead of starting servers individually. It prevents port conflicts and stale processes.

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.
