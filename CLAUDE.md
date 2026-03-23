# Forge - Project Instructions

## Local Dev Servers
Use `./scripts/dev.sh` to manage backend + frontend:
* `./scripts/dev.sh start` - Kill existing processes on :8000/:5173 and start both
* `./scripts/dev.sh stop` - Stop both servers
* `./scripts/dev.sh restart` - Stop then start (use after backend changes that crash the frontend)
* `./scripts/dev.sh status` - Check if servers are running
* Logs: `/tmp/forge-backend.log`, `/tmp/forge-frontend.log`

Always use this script instead of starting servers individually. It prevents port conflicts and stale processes.

## Lambda Deployment (CRITICAL)
Read `docs/lambda-alias-versioning.md` before touching Lambda aliases, versions,
provisioned concurrency, or environment variables.

**Two independent deploy paths - understand which you need:**
* Code deploys (automatic on push): update Docker image, publish version, swing alias
* CDK deploys (manual): update function definition (env vars, memory, IAM, etc.)
* Env var changes require BOTH: `cdk deploy` first (updates $LATEST), then code push (publishes a version from it)

**Zero-downtime deploys:**
* The deploy workflow pre-warms new versions before swinging the alias
* Fail-closed: if pre-warming fails, the alias stays on the old version and the deploy aborts
* NEVER change this to fail-open - cold starts on Docker images are 5-15 seconds

**Key rules:**
* NEVER create a `lambda.Alias` with `version: fn.currentVersion` without the SSM `addPropertyOverride`
* NEVER remove the `addPropertyOverride` calls from existing aliases
* NEVER manually update `/forge/live-versions/*` SSM parameters or the `live` alias - the deploy workflow owns them
* NEVER manually call `update-function-configuration` on production Lambdas - use CDK
* Lambda env vars come from `app.ts` `ENV_CONFIG`, NOT from CDK context - add new env vars there

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.
