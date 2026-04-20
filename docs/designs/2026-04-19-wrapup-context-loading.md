# Wrapup context loading, journal write policy, versioned pulse questions

**Date:** 2026-04-19
**Bug:** W4-01 (session continuity loss), plus W4-02 partial (journal duplicate/tag noise in wrapup)
**Status:** Design

## Problem

Week 4 wrapup sessions opened with no knowledge of what the user did earlier in the day or in prior weeks. The agent had to guess. Users felt it:

* Vee Ilmany — "broken today," AI "kept guessing plans incorrectly."
* Adrian Clark — "didn't I capture this already?" Pasted his prior transcript back in.
* Denis Sablić — "already talked about that in checkin."

Commit `817629d` (Apr 13) added weekly progress + impact pulse questions to the wrapup flow and, in the same change, removed the `read_journal` call that previously gave the wrapup agent context. The removal was motivated by LLM latency concerns at the time. Today's switch to Opus 4.6 for objective evaluation (`612043a`) and Bedrock prompt caching (same commit) make context injection cheap and stable enough to restore context — via the system prompt rather than tool calls.

## Goals

1. Wrapup agent can reference the user's plan from this morning, their captured journal entries from today, and their prior-week digest — with no LLM-visible latency.
2. The pulse questions do not re-ask users who have already answered. Ask-again support exists for future survey rounds.
3. Removes the duplicate-save and incorrect-week-tag noise that wrapup auto-save contributes to the journal.
4. Preserves the existing pulse pulse data for the metrics dashboard.

## Non-goals

* Cross-session context for session types other than wrapup (may be worth it later — not in this scope).
* Changing the pulse wording or cadence policy (once per version is the rule).
* Retroactive digest regeneration from updated transcripts.

## Design

### 1. Wrapup context injection

Executor loads three sources in parallel when `session_type == "wrapup"`, once at the top of `run_agent_session()` before the system prompt is built. The resulting dict is passed into `build_system_prompt` on every rebuild within that session — no per-turn re-reads. The prompt-caching introduced in `612043a` keeps subsequent turns cheap.

Sources:
1. **Today's intake responses.** Read `profiles/{user_id}/intake-responses.json` (existing path, already used by intake). Filter to responses whose `captured_at` falls within "today" in the user's timezone (`profile.timezone`, fall back to UTC). Format as `label: value` pairs. The `plan-day{N}` synthetic objective is the most important entry — render it first.
2. **Today's journal entries.** Read via `JournalRepository.list(user_id, date_from=today_start, date_to=today_end, limit=10)` where `today_start` and `today_end` are computed in `profile.timezone`. Truncate each entry's content to 500 chars. Newest first.
3. **Previous week's digest.** Read key `profiles/{user_id}/digest-week{N-1}.md` via `context.storage.read()` — the existing path used by `backend/tools/digest.py`. Markdown content, passed through verbatim. Falls back silently if absent (Week 1 users, missing digest).

All three reads run concurrently via `asyncio.gather`. Storage backend is whatever the executor already has (`S3Storage` in prod, `LocalStorage` in dev pointing at `/tmp/forge-storage/`).

Rendered section (appended after `skill_instructions` in `build_system_prompt`):

```
## Context for Today's Wrap-up

### This morning you set these intentions
- Plan for Day 4: <user's plan text>
- Applied learnings from last week: <user's answer>
...

### Today's journal entries
- [14:03] <truncated content>
- [11:40] <truncated content>
...

### Last week's digest
<full digest text>
```

Any of the three subsections is omitted when its source is empty. The whole "Context for Today's Wrap-up" header is omitted when all three are empty.

### 2. Journal write policy

| Session type | Writes journal? | Implementation change |
|---|---|---|
| brainstorm | yes | none |
| stuck | yes | none |
| chat | yes | none |
| tip | no | none |
| collab | no | none |
| intake | no | filter `save_journal` out of intake's tool registry (prevents the 20% accidental writes observed in Weeks 2-4) |
| wrapup | no | remove `_auto_save_journal` fallback call at `backend/agent/executor.py:513` |

Rationale: the intake plan is already captured in `intake-responses.json`; the wrapup reflection doesn't need journal storage because the wrapup is itself a synthesis of journal entries already written during the day.

### 3. Pulse questions — config-driven and versioned

**Config file: `config/pulse-surveys.json`**
```json
[
  {
    "id": "progress",
    "version": "v1",
    "text": "Do you feel like you're making progress in building your AI skills?",
    "scale": [
      "Not really",
      "A little",
      "Moderate progress",
      "Good progress",
      "Significant progress"
    ]
  },
  {
    "id": "impact",
    "version": "v1",
    "text": "To what extent has AI helped you buy back time or reduce friction in your weekly tasks?",
    "scale": [
      "No impact",
      "Minimal impact",
      "Moderate impact",
      "Significant impact",
      "Transformative impact"
    ]
  }
]
```

**Per-user state: `profiles/{user_id}/pulse-responses.json`**
Append-only log.
```json
[
  {"question_id": "progress", "version": "v1", "level": 3, "week": 4, "answered_at": "2026-04-14T18:00:00Z"},
  {"question_id": "impact",   "version": "v1", "level": 3, "week": 4, "answered_at": "2026-04-14T18:00:00Z"}
]
```

**To-ask computation (executor, at wrapup session start):**
```python
def questions_to_ask(config: list[dict], answers: list[dict]) -> list[dict]:
    answered = {(a["question_id"], a["version"]) for a in answers}
    return [q for q in config if (q["id"], q["version"]) not in answered]
```

Result injected into the system prompt as part of the Context section:

```
### Pulse questions to ask this session
- progress: <text>
  Scale: 1 <scale[0]>, 2 <scale[1]>, 3 <scale[2]>, 4 <scale[3]>, 5 <scale[4]>
- impact: ...
```

Empty list → section omitted entirely.

**Skill file delta (`skills/wrapup.md`):** the two hardcoded pulse question blocks are removed. Replaced with a single instruction: *"If pulse questions are listed in the Context section, ask them one at a time after the open-ended discussion. Present the scale as a numbered markdown list. Do not combine multiple questions into a single message."*

**Re-ask flow (future):** bump the `version` field in `config/pulse-surveys.json` (e.g., `"v1"` → `"v2"`). Next wrapup for each user will see no matching `v2` answer and ask. Previous `v1` answers stay in the log for trend analysis.

### 4. Pulse extraction in `/forge-analytics`

Extension to the existing map-reduce pipeline at `.claude/skills/forge-analytics/` that already processes wrapup transcripts.

* Map step: each mapper processing a wrapup transcript additionally outputs `pulse_answers: [{question_id, level, week, answered_at}]` when a pulse question was clearly answered with a 1-5 numeric choice. "Clearly" = the mapper LLM's confidence gate; ambiguous answers are omitted rather than guessed.
* Reduce step: stamps each answer with the `version` currently live in `config/pulse-surveys.json` at the time of the analytics run, then writes per-user append-only log to S3 at `profiles/{user_id}/pulse-responses.json`. Dedup on `(question_id, version, week)` — if the user already has an entry for that tuple, skip.
* **Version-stamping is run-time, not historical.** The mapper does not attempt to back-date versions. If you bump `v1` → `v2` between analytics runs, any transcripts extracted in the new run get stamped `v2`, even if the user answered the question before the bump. This is by design: the version bump means "I want to see a fresh answer" and stamping `v2` ensures the user is re-asked next session. The only edge is a user who answered between the bump and the next analytics run — they get stamped `v2` and won't be re-asked, which is fine; their answer is new enough. Previous `v1` entries stay in the log as trend data.
* Idempotent per user-week: the append-only log + dedup tuple means re-running `/forge-analytics --week N` is safe and a no-op for already-extracted answers.

### 5. One-time backfill

Before Week 5 (Tuesday Apr 21):
1. Deploy `config/pulse-surveys.json` with the two v1 questions.
2. Run `/forge-analytics --week 4` with the pulse extraction extension.
3. Verify: `profiles/{user_id}/pulse-responses.json` exists for users who completed Week 4 wrapup, and the entries have `version: "v1"`.
4. Spot-check: pick a user who answered both in Week 4, start a Week 5 wrapup on staging, confirm pulse questions are not asked.

## Implementation plan

| # | File | Change |
|---|---|---|
| 1 | `config/pulse-surveys.json` | New. Two entries (progress v1, impact v1) with exact wording from current skill. |
| 2 | `backend/storage.py` | Add `load_pulse_responses`, `append_pulse_response`, `load_pulse_config` helpers. |
| 3 | `backend/agent/executor.py` | Add parallel context loader for wrapup session type: intake responses (today), journal entries (today), previous digest, pulse to-ask list. Pass into `build_system_prompt` via a new `wrapup_context: dict \| None` parameter. Remove `_auto_save_journal` call at line 513. |
| 4 | `backend/agent/context.py` | Accept new `wrapup_context` param. Render "## Context for Today's Wrap-up" section when session_type == "wrapup" and any subsection is non-empty. |
| 5 | `skills/wrapup.md` | Remove hardcoded pulse blocks. Add conditional pulse instruction. |
| 6 | `backend/tools/registry.py` or intake tool filter at `backend/agent/executor.py:352` | Add `save_journal` to the excluded tools for intake sessions. |
| 7 | `skills/forge-analytics/` (or whichever location the skill source lives in) | Extend map prompt to extract pulse answers. Extend reduce step to write per-user pulse-responses logs. |
| 8 | `tests/test_wrapup_context.py` | New. Unit tests for context building, pulse to-ask computation, timezone handling. |

## Testing plan

### Local-first e2e (per prior weeks' practice)

1. Pick 2-3 random production users who completed Week 4 wrapup with clean pulse answers, plus 1-2 who skipped Week 4 entirely.
2. Hydrate local dev storage: run `/forge-analytics-sync` to pull production data into `data/analytics/`, then use `scripts/copy-user-to-staging.py --env local --email <user>` to copy each selected user's profile, intake-responses, journal entries, and digest files into `/tmp/forge-storage/` (the `LocalStorage` backend path). Verify the script supports `--env local`; if not, add the flag or do a direct copy into the local storage path.
3. Run the Week 4 backfill locally: regenerate `pulse-responses.json` for the copied users by running the pulse-extraction map step against their Week 4 transcripts (accessible under `data/analytics/`).
4. Set `program_week_override = 5` on each user's local profile.
5. Via `./scripts/dev.sh start` and the local dev server, masquerade as each user, start a wrapup session. Verify:
   * System prompt contains the "Context for Today's Wrap-up" section with the right subsections (three when full, fewer gracefully).
   * AI references today's plan specifically in the opening turns (e.g., "You said this morning you were going to try X. How did that go?").
   * For Week-4-completed users: pulse questions are not asked.
   * For Week-4-skippers: pulse questions are asked normally, one at a time.
   * No journal entry is written at session end (check the local journal store after the session closes).

### Staging pass

After local passes, copy the same users to staging with `AWS_PROFILE=forge python scripts/copy-user-to-staging.py --email <user> --week 4 --include-sessions`. This script handles the production→staging user ID mapping automatically (user IDs differ between environments because the identity system issues different IDs per env).

After copy, set `program_week_override = 5` on each staging profile, masquerade via browser console (`localStorage.setItem('forge-masquerade', 'USER_EMAIL')`, then refresh), and repeat the five verification checks above.

### Unit coverage

* `questions_to_ask()` — covered versions, mixed-answered, no answers, all answered, malformed entries in pulse-responses log (skip, don't crash).
* Context loader with empty/partial data sources (no intake today, no journal today, no prior digest — each alone and in combinations).
* Timezone edge case: user in Auckland completes intake at 09:00 NZ time, opens wrapup at 17:00 NZ time — "today's intake" must be found. Same user's wrapup at 23:30 NZ time when UTC has already rolled over — still the same local day.

## Rollout

1. Merge and deploy code to staging.
2. Run `/forge-analytics --week 4` on staging data to backfill pulse state.
3. Smoke-test staging with 3 real users (see testing plan).
4. Merge to main → auto-deploy to production.
5. Run `/forge-analytics --week 4` on production data for real backfill.
6. Monitor Week 5 wrapup sessions on Tuesday Apr 21 via PostHog for: completion rate, session length, pulse answer distribution.

## Open items

* Confirm `scripts/copy-user-to-staging.py` supports `--env local` for step 2 of the local testing plan. If it's staging-only today, add the local path as part of this work (trivial: same copy logic, different destination — DynamoDB local table + `/tmp/forge-storage/` instead of staging).
* Pulse config is not admin-editable in this scope. Surface it in the admin UI later only if it becomes friction to edit; a JSON file + redeploy is acceptable for the foreseeable bump cadence (every few weeks at most).
* Intake continues to use the `get_previous_digest` tool as-is. This design only changes wrapup's context-loading pattern; intake behavior is untouched.

## Coherence notes (things worth calling out before implementation)

* **The context is loaded once per session, not once per turn.** The existing executor rebuilds `system_prompt` on every turn (see `backend/agent/executor.py:209,273`). The wrapup_context dict is computed once at the top of `run_agent_session` and passed through to every rebuild. This matters because the three S3 reads are not free — we don't want them on every user message.
* **Version-stamping is run-time, not historical.** Documented inline above in Section 4. Re-stating because it's the one place a reader might expect more cleverness than is warranted.
* **Session dedup is our friend.** The existing one-wrapup-per-user-per-week constraint (`backend/api/websocket.py:157`) means we never have to worry about the pulse-responses log getting a second entry for the same week in the same wrapup.
* **Removing `_auto_save_journal` has a small side effect on the Week 4 metric.** Week 4 shows a 150% journal-write rate for wrapup because auto-save and AI-initiated saves both fire. Post-fix, that drops to 0% from wrapup (intentional). Analytics reports that count journal entries by session type should be aware of this.
* **Backfill timing is critical.** The Week 4 backfill run must happen *after* `config/pulse-surveys.json` is deployed and *before* the first Week 5 wrapup session. If we run analytics before the config exists, the mapper has nothing to version-stamp against. Order: deploy config → deploy code → run backfill → users start Week 5 on Tuesday.
