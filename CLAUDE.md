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

## PostHog Analytics
* Use `DS_READONLY_POSTHOG_API_KEY` env var for read-only PostHog API access (Digital Science account)
* PostHog host: `https://us.i.posthog.com`
* Production project API key (write): `phc_Qn6PGsXODJxvYCMV8Vv099fYpf9oAi1OPctdvgwb828`
* Staging project API key (write): `phc_7wUFuz56pMvIhqnSalLqHakMDY2PKeT4KIM1NZHFQpB`

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

## Pulse Surveys — versioning, synthetic backfill, and analytics rules

The AI Tuesdays programme runs **three pulse surveys total** across the 12-week
arc. Each survey reuses the same two question IDs (`progress`, `impact`) with
a fresh `version` stamp:

| Survey | Week launched | Config version | Notes |
|---|---|---|---|
| 1 | Week 5 | `v1` | Baseline. Active through Week 7. |
| 2 | Week 8 | `v2` | Same question text as v1 — bump was a config-only change to suppress freelance Qs + force fresh full-cohort capture. See commit `af6d2b3`. |
| 3 | Week 12 | `v3` (planned) | Programme-close survey. Bump will trigger another full re-prompt under current dedupe logic. |

The Lambda's wrap-up agent suppresses already-answered questions via
`backend/agent/wrapup_context.py::questions_to_ask`. The dedupe key is the
tuple `(question_id, version)`, so a config version bump intentionally
re-prompts every user.

### The Week 8 → Week 9 problem and synthetic backfill (2026-05-18)

When v2 launched in Week 8, 90 users who had answered v1 (in Weeks 4/6/7) did
not respond to the v2 prompt. The intent for Week 9+ was that any prior
answer should suppress further prompts. Without a fix, those 90 users would
have been re-prompted in Week 9 — undesired.

A one-off backfill (`/tmp/backfill-pulse-v2-suppression.py` — keep this
script or its descendants in `scripts/` if rerun) was executed on
2026-05-18. For every user with a `(qid, v1)` record but no `(qid, v2)`
record, a synthetic v2 entry was appended to their
`s3://forge-production-data/profiles/<uid>/pulse-responses.json` with this
shape:

```json
{
  "user_id": "...",
  "question_id": "progress",        // or "impact"
  "version": "v2",
  "level": null,                    // intentionally null — not a real answer
  "synthetic": true,                // ← analytics filter
  "carried_from_version": "v1",
  "carried_from_week": 4,           // original v1 week (4, 6, or 7)
  "carried_from_answered_at": "2026-04-14T19:39:01Z",
  "backfilled_at": "2026-05-18T21:40:23.672794+00:00",
  "reason": "v1->v2 bump suppression"
}
```

97 users (90 fully v1-only + 7 with partial v2 coverage) were updated;
173 synthetic entries were written.

### Rules for any future analytics that reads `pulse-responses.json`

**Always filter `synthetic == true` unless you specifically want to study
the backfill itself.** Real responses have `level: int (1-5)` and no
`synthetic` field. Synthetic entries have `level: null` and `synthetic: true`.

Concrete rules per question:

* **"Did this user respond to survey N?"** — filter by
  `version == 'vN' AND synthetic != true`. Synthetic v2 entries should NOT
  count as Week 8 survey responses; the user did not respond to Week 8.
* **"Distribution of scores for Week N"** — filter by
  `week == N AND level is not None`. The `level is not None` clause
  excludes synthetics automatically. The carried-from week on synthetic
  entries is the original v1 answer's week (4/6/7), not Week 8 — so even
  if you forget the level filter, synthetics won't pollute a Week 8 mean.
* **"How many distinct users have ever participated in the pulse system?"** —
  this is ambiguous. Decide whether synthetic counts. If yes, dedupe on
  `user_id` alone. If no (recommended), filter `synthetic != true` first.
* **"Effective participation in survey N for suppression purposes"** —
  any record with `(qid, vN)` regardless of `synthetic` flag. This is what
  `wrapup_context.questions_to_ask` does, intentionally.

### Where pulse data flows in the analytics pipeline

* **Weekly MB / Project Team report pulse sections (`6a`)** — sourced from
  `pulse_answers` JSON blocks embedded in `data/analytics/reports/map/wrapup-batch-*.md`
  by map agents reading transcripts directly. **They do NOT read
  `pulse-responses.json` from S3.** Synthetic entries cannot pollute weekly
  reports.
* **`scripts/upload-pulse-responses.py`** — dedupes on
  `(question_id, version, week)` when appending new entries. Synthetic
  entries carry the original v1 week, so new Week 9+ uploads won't conflict
  with them. Safe.
* **`backend/agent/wrapup_context.py`** — the intended consumer. Sees
  `(qid, v2)` in synthetic records and correctly suppresses Week 9 prompts.
* **`compute_metrics.py`** — does not touch pulse data. Unaffected.

### Week 12 v3 launch — what to do

When v3 ships:

1. Update `config/pulse-surveys.json` to `version: "v3"` for both questions.
2. Deploy the Lambda (config is baked into the Docker image).
3. All users will be re-prompted on their next wrap-up. This includes:
   * Users with real v1 + v2 responses
   * Users with v1 + synthetic v2
   * Users with real v2 only
   * Users with no prior responses
4. After Week 12 wrap-ups complete, **decide** whether to backfill synthetic
   v3 entries for users who answered v1 OR v2 but skipped v3. The same
   suppression rule applies: prior answer → no re-prompt. There is no
   "Week 13", so a Week 12 backfill is only relevant if a v4 bump is
   anticipated (currently none planned).
5. Update the survey table in this file with the actual launch week and
   confirm the version string.

### Doc / script touch points to check before changing pulse behaviour

* `backend/agent/wrapup_context.py::questions_to_ask` — dedupe logic
* `backend/storage.py::load_pulse_config`, `load_pulse_responses` — loaders
* `config/pulse-surveys.json` — source of truth, bundled into Lambda image
* `scripts/upload-pulse-responses.py` — append-only uploader
* `skills/wrapup.md` step 3 — empty-state instruction (prevents the
  freelance-questions failure mode from Week 7)
* `data/analytics/reports/map/wrapup-batch-*.md` — `pulse_answers` JSON
  block format (canonical for weekly reports)
