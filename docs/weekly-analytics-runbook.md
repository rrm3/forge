# Weekly Analytics Runbook

Everything we run on a weekly cadence for Forge / AI Tuesdays. The goal of this doc is twofold:

1. Tell you exactly what to run each week, in what order, and why.
2. Make every script's data dependencies explicit so we never again ship reports built on stale upstream state. (The Week 5 incident where activity reports ran before digests existed and produced "No plan recorded" for everyone with new wrap-ups was avoidable. The dependency rules below would have caught it.)

If something here disagrees with what a script's `--help` says, the script is right and this doc is stale: update it.

## Hard rules — read before running anything

The pipeline is a directed graph, not a list. Skipping a step or running a step before its inputs exist produces silent garbage, not an error.

* **Always sync first.** Every analysis script reads `data/analytics/dynamodb/*` and `data/analytics/s3/*`. If you don't run `/forge-analytics-sync`, every downstream output reflects whatever you had last time.
* **Digests must exist before activity reports for the same week.** `scripts/generate-activity-reports.py` reads each user's `digest-week<N>.md` as the LLM's source material for `plan` / `accomplished`. If the digest is missing or empty, the activity report writes "No plan recorded" / "No activity recorded" and uploads that to S3. The script now hard-aborts if no digests are present for the target week (see preflight section), but if you bypass the preflight you will eat your own data.
* **`generate-activity-reports.py` always merges with the existing per-user JSON.** Earlier versions only merged when `--incremental` was set, which meant `--user X --week 5 --upload` would wipe weeks 1-4 from S3. Fixed in commit landing 2026-04-23 — if you see prior weeks disappearing, the fix has regressed.
* **Reduce phase always re-runs even if map outputs are cached.** The reduce step is cheap and the report templates may have changed. The map phase has a cache; the reduce phase does not.
* **Never overwrite prior-week digests.** Each week gets its own directory under `data/analytics/digests/digest-week<N>/`. Historical digests are immutable.
* **Never rename, overwrite, or delete a Google Docs tab for a prior week.** Only the current-week tab moves between `(Preliminary)` and `(Final)`.

## The weekly rhythm at a glance

AI Tuesdays are the main event, but several teams swap to other days due to meeting conflicts. That gives us three checkpoints each week:

* **Monday evening (pre-Tuesday refresh).** Make sure every user's digest is current before the next AI Tuesday so the companion has fresh context. Catches late Friday/weekend wrap-ups.
* **Wednesday or Thursday (Preliminary).** First-cut MB / Project Team / App Issues reports for the Tuesday cohort. Tag `(Preliminary)`. Internal share.
* **Friday afternoon or Saturday (Final).** Re-run with the Friday/late-week cohort included. Tag `(Final)`. These become the canonical Week N reports and replace the Preliminary Google Docs tabs.

The hash cache means each rerun only does LLM work for users whose data actually changed. "Changed" means new sessions, new ideas, new journal entries, or profile updates since the last run — not "Friday cohort only". A Tuesday-night wrap-up that landed at 11pm on Tuesday is changed; a Wednesday afternoon edit is changed; a Friday morning intake is changed.

## Canonical sequence — what to run each cycle

The same eight steps run for every cycle (Monday refresh / Wednesday Preliminary / Saturday Final). The differences are which mode flag to pass and which steps to skip.

| # | Step | Command / artifact | Mon refresh | Prelim | Final | Depends on |
|---|---|---|---|---|---|---|
| 1 | Sync prod data | `/forge-analytics-sync` | ✓ | ✓ | ✓ | fresh AWS session (`AWS_PROFILE=forge`) |
| 2 | Compute metrics | `python3 data/analytics/scripts/compute_metrics.py --week <N>` | ✓ | ✓ | ✓ | step 1 |
| 3 | Map phase (delta) | subagents launched by `/forge-analytics` (or `--digests-only`) | ✓ | ✓ | ✓ | step 2 (reads `per_user_hashes` and `batch_assignments`) + Week 2+ needs prior week's digests |
| 4 | Reduce phase | 3 subagents (MB / Project Team / App Issues) launched by `/forge-analytics` | — | ✓ | ✓ | step 3 + prior week's reports for delta orientation |
| 5 | Digest generation | `scripts/regen-digests-batch.sh <N> <users.tsv>` then `scripts/upload-digests-s3.sh <N> <users.tsv>` (or run inside `/forge-analytics`) | ✓ | ✓ | ✓ | step 3 (digest agents read transcripts and prior week's digest) |
| 6 | Pulse-responses upload | append fenced `pulse_answers` blocks from `reports/map/pulse-batch-*.md` to S3 per-user `pulse-responses.json` | — | ✓ (Week 4+) | ✓ (Week 4+) | step 3 + `config/pulse-surveys.json` for version stamping |
| 7 | Activity reports | `python3 scripts/generate-activity-reports.py --incremental --upload` | — | ✓ | ✓ | **step 5** (reads digests as LLM source) + step 1 |
| 8 | Google Docs publish | upload `week<N>-mb-report.md` and `week<N>-project-team-report.md` as new tabs | — | ✓ | ✓ | step 4 |

Mode flags:

* Monday refresh: `/forge-analytics --digests-only`
* Preliminary or Final: `/forge-analytics` (full pipeline, tagged accordingly in titles + Google Docs tabs)

The auto-detection rule for tagging: Tuesday/Wednesday/Thursday → `(Preliminary)`; Friday/Saturday/Sunday/Monday → `(Final)`. Override with `--preliminary` or `--final` if needed.

## Step-by-step commands

### Monday evening (pre-Tuesday refresh)

Goal: every user's digest is current before tomorrow morning. The companion at the start of Tuesday's session loads `digest-week<N>/<user_id>.md`.

```bash
# Step 1
/forge-analytics-sync

# Steps 2 + 3 + 5 in one skill invocation
/forge-analytics --digests-only
```

Skip 4, 6, 7, 8. Do not regenerate the executive reports on Monday evening; they're produced post-Tuesday.

### Wednesday or Thursday (Preliminary)

Goal: first-cut MB / Project Team / App Issues reports for the Tuesday cohort.

```bash
# Step 1
/forge-analytics-sync

# Steps 2-6 in one skill invocation
/forge-analytics

# Step 7 — MUST run AFTER /forge-analytics has uploaded digests
python3 scripts/generate-activity-reports.py --incremental --upload

# Step 8 — optional, ask Rob first
# Upload reports/week<N>-mb-report.md as new tab "Week <N> MB Report (Preliminary)"
# Upload reports/week<N>-project-team-report.md as new tab "Week <N> Project Team Report (Preliminary)"
```

Reports land at `data/analytics/reports/week<N>-{mb-report, project-team-report, app-issues}.md`. Their title lines are tagged `(Preliminary)`.

### Friday afternoon or Saturday (Final)

Same eight steps as Wednesday. Hash cache means most users are unchanged so map work is fast.

```bash
/forge-analytics-sync
/forge-analytics                                # tags reports (Final)
python3 scripts/generate-activity-reports.py --incremental --upload
```

For Step 8: if a `(Preliminary)` tab for this week exists in the Google Docs, REPLACE its content with the Final content and RENAME it to `(Final)`. Do not create a new tab. Prior-week tabs remain immutable.

### Ad-hoc

Run when needed, not on a fixed cadence:

* `/forge-backfill-intake` when `data/analytics/scripts/identify_backfill_targets.py` finds profiles where `onboarding_complete=true` but `intake_summary` / `ai_proficiency` / `work_summary` are missing.
* `/forge-backfill-titles` when brainstorm/chat sessions have empty or generic titles.
* `/forge-intake-smoke` before any Tuesday where we deployed changes to the intake system.

## Dependency graph

The text above gives the per-cycle commands. The diagram below makes the read/write relationships explicit. Arrows point from a producer to its consumers. Dotted arrows are runtime config dependencies.

```
                       AWS forge profile
                              │
                              ▼
                    /forge-analytics-sync ─────────────────────────┐
                              │                                    │
                              ▼                                    │
                    data/analytics/dynamodb/*                      │
                    data/analytics/s3/*                            │
                              │                                    │
              ┌───────────────┼───────────────────┐                │
              ▼               ▼                   ▼                │
       compute_metrics    map agents         pulse mapper          │
              │               │ (reads prior        │              │
              ▼               │  week digest)       ▼              │
      week<N>-metrics.json    │              pulse-batch-*.md      │
      week<N>-quantitative.md │                     │              │
              │               ▼                     ▼              │
              │          wrapup/chat/             config/          │
              │          tools/intake/            pulse-           │
              │          ideas batch md            surveys.json    │
              │               │                     │              │
              │               ▼                     ▼              │
              │           reduce agents      pulse-responses       │
              │               │              upload script         │
              │               ▼                     │              │
              │      week<N>-mb-report.md           ▼              │
              │      week<N>-project-team-          S3:            │
              │       report.md                     profiles/<u>/   │
              │      week<N>-app-issues.md          pulse-          │
              │               │                     responses.json │
              │               ▼                                    │
              │       Google Docs tabs                              │
              │       (Preliminary→Final)                           │
              │                                                    │
              ▼                                                    ▼
       digest agents (read transcripts +                  generate-activity-
       prior week's digest) ─────────────► digest-week<N>/  reports.py
                                            <u>.md (local) ──┐    │
                                                  │          │    │
                                                  ▼          ▼    │
                                             S3: profiles/        │
                                             <u>/digest-           │
                                             week<N>.md            │
                                                                   ▼
                                                          reports/activity/
                                                          <u>.json (local)
                                                                   │
                                                                   ▼
                                                          S3: reports/
                                                          activity/<u>.json
                                                                   │
                                                                   ▼
                                                       backend /team/me
                                                       backend /team/members/<u>
                                                                   │
                                                                   ▼
                                                          MyTeamView.tsx
```

The two non-obvious edges:

* **Map agents read prior week's digest** for Week 2+ continuity (`progression from prior week` analysis). If you've never run digest generation for Week N-1, Week N's map outputs lose that continuity.
* **Activity reports read this week's digest** as the LLM source for `plan` / `accomplished`. This is the dependency that bit us in Week 5 — if you run activity reports before digests for the same week exist, every user gets "No plan recorded".

## Per-script reference

Treat this as the canonical "what does this script need and produce". Source of truth is the script itself; this is a quick lookup.

### `~/.claude/skills/forge-analytics-sync/sync_forge_data.py`

* **Reads:** production DynamoDB tables (`forge-production-{profiles,sessions,journal,ideas,user-ideas,tips,tip-votes,tip-comments,collabs}`), S3 (`s3://forge-production-data/{sessions,memory,profiles,reports,orgchart}/`).
* **Writes:** `data/analytics/dynamodb/*`, `data/analytics/s3/*`, `data/analytics/reports/activity/*` (download), `data/analytics/orgchart/org-chart.db`, `data/analytics/_sync_metadata.json`.
* **Quarantines:** Holtzbrinck investor accounts to `data/analytics/quarantine/`.
* **Depends on:** AWS profile `forge` with active session.
* **Watch for:** if AWS session expired the script aborts cleanly; just `aws login --profile forge` and rerun.

### `data/analytics/scripts/compute_metrics.py`

* **Reads:** synced DynamoDB + S3 + `data/analytics/orgchart/org-chart.db`. Optionally `data/analytics/reports/week<N-1>-metrics.json` for week-over-week deltas.
* **Writes:** `data/analytics/reports/week<N>-metrics.json`, `week<N>-quantitative.md`. Updates `per_user_hashes` (used by the map phase to identify changed users).
* **Depends on:** sync (step 1).
* **Side effects:** none.

### `scripts/generate-digest.py`

* **Reads:** `data/analytics/s3/sessions/<user>/*.json`, `data/analytics/s3/profiles/<user>/intake-responses.json`. Sonnet 4.6 via Bedrock (`us.anthropic.claude-sonnet-4-6`).
* **Writes:** `data/analytics/digests/digest-week<N>/<user_id>.md`.
* **Does NOT read:** prior week's digest. Each call is an isolated single-week summary.
* **Depends on:** sync (step 1). Does NOT depend on map outputs (although the skill version does, since it uses map-agent batches).
* **Watch for:** model ID. The string `us.anthropic.claude-sonnet-4-6-20250514-v1:0` is INVALID and was the cause of the Week 5 digest-regen failures. Current correct ID is the inference profile alias `us.anthropic.claude-sonnet-4-6`. Verify with `aws bedrock list-inference-profiles --region us-east-1`.

### `scripts/regen-digests-batch.sh`

Wrapper around `generate-digest.py`. Takes a TSV `<user_id>\t<name>` and runs N parallel workers.

* **Usage:** `bash scripts/regen-digests-batch.sh <week> <users.tsv> [max_jobs]`
* **Watch for:** the trailing `grep -rl FAIL` in the script can exit non-zero when there are no failures. That's cosmetic — check the actual `OK:` count to confirm success.

### `scripts/upload-digests-s3.sh`

Uploads `data/analytics/digests/digest-week<N>/*.md` to `s3://forge-production-data/profiles/<user>/digest-week<N>.md`.

* **Usage:** `bash scripts/upload-digests-s3.sh <week> <users.tsv>`
* **Uploads everything, including carry-forward digests.** Earlier versions skipped digests containing "No new activity" on the assumption that the wrap-up agent would fall back to the user's prior-week S3 file. It does not. `backend/agent/wrapup_context.py::_load_previous_digest` reads exactly one S3 key (`digest-week<N-1>.md`) with no fallback. If a returning user has no current carry-forward in S3, the wrap-up system prompt loses its "Last week's digest" section entirely (the LLM-callable `get_previous_digest` tool does scan backwards, but it's agent-driven and not deterministic). Always upload carry-forwards. (Fix landed 2026-04-27 after a 53-user gap was found.)

### `scripts/generate-activity-reports.py`

* **Reads:** synced DynamoDB + S3 data, `data/analytics/digests/digest-week<N>/<user_id>.md` (PRIMARY LLM SOURCE), `data/analytics/reports/activity/<user_id>.json` (existing report, for merge), `data/analytics/reports/activity/_generation_meta.json` (last-run timestamps for `--incremental`). Opus 4.6 via Bedrock (`us.anthropic.claude-opus-4-6-v1`).
* **Writes:** `data/analytics/reports/activity/<user_id>.json`, optionally uploads to `s3://forge-production-data/reports/activity/<user_id>.json` if `--upload`.
* **Depends on:** **digest for the target week must exist** for that user (step 5). Without it the LLM gets "(No digest available)" and emits "No plan recorded".
* **Preflight (added 2026-04-23):** if `--week N` is passed but `data/analytics/digests/digest-week<N>/` is empty or missing, the script aborts with a hard error.
* **Always merges existing report.** The flag-gated merge logic is gone — `--week N` will only replace week N in the existing report and preserve weeks 1..N-1.
* **Watch for:** running multiple instances in parallel against `--user` flags can corrupt the shared `_generation_meta.json` because each instance reads-modifies-writes the same file. Cap concurrency with `xargs -P 8` (the script's own `--workers` is per-instance and safe), and prefer one `--incremental` invocation over many `--user` invocations.

### `data/analytics/scripts/identify_backfill_targets.py` / `identify_intake_responses_targets.py` / `identify_title_targets.py`

* **Reads:** synced DynamoDB profiles + sessions.
* **Writes:** `data/analytics/backfill/targets_*.json`.
* **Depends on:** sync.
* **Used by:** `/forge-backfill-intake`, `/forge-backfill-titles` skills.

### `data/analytics/scripts/write_enrichment.py` / `write_intake_responses.py` / `write_titles.py`

* **Reads:** local backfill results.
* **Writes:** **PRODUCTION DynamoDB and S3.** These are the only "push" scripts other than the digest/activity-report uploads.
* **Watch for:** dry-run mode is your friend. Always preview before pushing.

## Pulse-responses upload (step 6 detail)

Week 4+ only. The pulse Q1/Q2 questions are NOT re-asked to users who already answered in a prior week — only to users who missed the baseline. This means a Week 5 pulse-batch file may legitimately have zero canonical answers; that's by design, not a regression.

Sequence:

1. Read every `data/analytics/reports/map/pulse-batch-*.md`. Each ends with a fenced ` ```json pulse_answers ` block.
2. Stamp each entry with the current `version` from `config/pulse-surveys.json` by `question_id`. Skip entries whose `question_id` isn't in the config (stale).
3. Group by `user_id`.
4. For each user: download `s3://forge-production-data/profiles/<user_id>/pulse-responses.json` (404 → empty list). Build a dedup set on `(question_id, version, week)`. Append only new entries. Upload back if anything was appended.
5. Print a summary: users updated, entries appended, entries skipped as duplicates.

Idempotent: running `/forge-analytics --week N` twice with no new data appends nothing.

## When something goes wrong

* **Activity reports show "No plan recorded" for users you know have sessions.** Digests for the target week didn't exist when the activity report ran. Fix: run digest generation for the affected users, then re-run `generate-activity-reports.py --user <uid> --week <N> --upload`.
* **Activity reports show fewer weeks than they should.** Likely a regression of the "merge existing" fix. Check `scripts/generate-activity-reports.py` around the `Load existing report` block — the `if os.path.exists(report_file):` branch must NOT be gated on `args.incremental`. Recovery: S3 versioning is on for the bucket; the prior good version is restorable via `aws s3api list-object-versions` + `aws s3api copy-object` with the older `VersionId` as source.
* **`/forge-analytics` map agents return mostly empty pulse batches.** Confirm with Rob whether the canonical pulse questions are firing this week. The Q1/Q2 questions are deliberately skipped for users who already answered in a prior week, so empty pulse data may just mean "this batch was full of users already pulsed in Week 4". Check `pulse-batch-3.md` etc. for actual data — if the entire week has zero, then the wrap-up prompt has rotated and that's a real backend regression.
* **My Team view shows a row with a name but no Day ticks.** The orgchart→profile join in `backend/api/team.py` failed. The join is by email (case-insensitive), not name, so the failure mode is either (a) the orgchart has no email for that person or (b) the profile email doesn't match. Check both with `sqlite3 data/analytics/orgchart/org-chart.db "SELECT email FROM people WHERE name = '...'"` and `python3 -c "import json; print(json.load(open('data/analytics/dynamodb/profiles/<uid>.json')).get('email'))"`.
* **Bedrock `ValidationException: provided model identifier is invalid`.** The script has a model ID that doesn't match a current inference profile. List valid IDs with `AWS_PROFILE=forge aws bedrock list-inference-profiles --region us-east-1`. Sonnet 4.6 = `us.anthropic.claude-sonnet-4-6`; Opus 4.6 = `us.anthropic.claude-opus-4-6-v1`.

## Automation status

Today every step is hand-run from Rob's laptop with skills. Three candidates for automating the recurring pieces:

* **`/schedule` skill** — runs from laptop. Simplest, but requires laptop awake at trigger time and state lives in Rob's shell. Good for the Mon/Wed/Sat cadence if "runs when laptop is on" is acceptable.
* **GitHub Actions cron** — runs in the cloud, no laptop dependency. The pure-Python steps (sync, compute metrics, activity reports, pulse upload) are easy to schedule there. The LLM-heavy steps (`/forge-analytics` map and reduce, digest generation) need a Claude CLI + key inside the runner, which we haven't wired up.
* **EventBridge → Lambda or ECS** — same Claude CLI issue as GitHub Actions, plus more infra to maintain. Overkill for weekly cadence today.

Recommendation that's still open: GitHub Actions cron for steps 1, 2, 6, 7 on a Mon 18:00 / Wed 09:00 / Sat 08:00 PT schedule, with a Slack ping when sync completes so Rob can kick off the LLM steps interactively. Steps 3, 4, 5, 8 stay manual until we have a CI-friendly path for the map-reduce skill.

## Quick reference: where things live

* **Skills:** `~/.claude/skills/forge-*`, `~/.claude/skills/forge-analytics-sync/`
* **Pipeline scripts:**
  * `data/analytics/scripts/compute_metrics.py`
  * `data/analytics/scripts/compute_trends.py`
  * `data/analytics/scripts/identify_backfill_targets.py` / `identify_intake_responses_targets.py` / `identify_title_targets.py`
  * `data/analytics/scripts/write_enrichment.py` / `write_intake_responses.py` / `write_titles.py`
* **Digest scripts:** `scripts/generate-digest.py`, `scripts/regen-digests-batch.sh`, `scripts/upload-digests-s3.sh`
* **Activity report script:** `scripts/generate-activity-reports.py`
* **Synced data:** `data/analytics/dynamodb/`, `data/analytics/s3/`, `data/analytics/orgchart/org-chart.db`
* **Reports:** `data/analytics/reports/week<N>-{metrics.json, quantitative.md, mb-report.md, project-team-report.md, app-issues.md}`
* **Map outputs:** `data/analytics/reports/map/{wrapup,chat,pulse,intake,ideas,tools,stuck}-batch-*.md`
* **Digests:** `data/analytics/digests/digest-week<N>/<user_id>.md`
* **Activity JSONs:** `data/analytics/reports/activity/<user_id>.json`
* **Caches:** `data/analytics/reports/.user-hash-cache.json` (per-user input hash for change detection), `data/analytics/reports/.qual-cache.json` (batch-level cache)
* **Backend:** `backend/api/team.py` (My Team endpoints), `backend/repository/profiles.py` (profile lookups, joins by email)
* **Frontend:** `frontend/src/components/MyTeamView.tsx`
* **Google Docs (final reports):**
  * MB doc id: `1Aw9esbfe2pj5PUql5E_DTSfzW7VDGvQtYx6tuVtYorg` (tab convention `Week <N> MB Report (Preliminary|Final)`)
  * Project Team doc id: `1Zqr4I5SgqxmdhjXtxDwt8nZyhBtvYnRx9fKOIrzDIRM` (tab convention `Week <N> Project Team Report (Preliminary|Final)`)
* **Other docs:** `docs/lambda-alias-versioning.md` for Lambda deploy state.
