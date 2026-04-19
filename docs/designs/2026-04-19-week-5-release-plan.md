# Week 5 release plan — phased implementation of Week 4 bug fixes

**Date:** 2026-04-19
**Ships:** Tuesday April 21, 2026 (start of Week 5)
**Status:** Approved, ready for implementation

## Summary

Three bugs from Week 4 analytics affect user trust enough to merit a fix before Week 5 starts. They are phased so that the smallest and lowest-risk change goes first, allowing each phase to bake and prove out before the next one stacks on top. Five other Week 4 bugs are explicitly deferred with rationale.

## Phases

Implement in this order. Do not start the next phase until the previous phase's test criteria pass on both local and staging.

### Phase 1 — W4-03: Gate weekly enrichment to first-ever intake

**Design doc:** `docs/designs/2026-04-19-weekly-enrichment-overwrite.md`

**What it changes:** One conditional in `backend/agent/executor.py`. `_enrich_profile_async` now only runs when `profile.intake_weeks` was empty before this completion. Prevents weekly check-in transcripts from overwriting identity fields (core_skills, work_summary, intake_summary, ai_proficiency, learning_goals) with sparse re-extractions.

**Blast radius:** Very small. Under 20 lines of production code. Only the intake-completion path is touched. No schema changes, no new endpoints, no frontend changes.

**Success criteria:**
* Scenario A (returning user): Week 2+ intake completion leaves identity fields unchanged. User-initiated `update_profile` calls persist.
* Scenario B (late joiner): first-ever intake in any calendar week triggers enrichment normally.
* Unit tests for both scenarios pass.

**Approval gate before Phase 2:** Rob confirms local + staging smoke tests pass and no regressions surface in intake completion or profile reads.

### Phase 2 — W4-04: Preview card hydration via server-side session metadata

**Design doc:** `docs/designs/2026-04-19-preview-card-hydration.md`

**What it changes:** Adds `source_session_id` and `source_tool_call_id` to Tip, Collab, and UserIdea records. `GET /api/sessions/{id}` returns a new `active_preview` field computed from the latest `prepare_*` tool_call minus any that have a matching published record. Frontend reducer populates preview state from that field on `SELECT_SESSION`. Adds `tool_call_id` to `tip_ready` / `idea_ready` / `collab_ready` WS events. Adds session-id filter to the three `*_ready` dispatch handlers.

**Blast radius:** Medium. Touches three repo schemas (additive fields only), adds a backend helper in the session-load hot path, adds request-body fields to three POST endpoints, reshapes the `SELECT_SESSION` reducer. Uses a new `find_by_source` repo method to keep queries scoped.

**Success criteria:**
* Happy path: prepare tip, card renders, publish, card clears.
* Dropped WS event: kill backend between `prepare_tip` tool call and WS emit, restart, verify card rehydrates via `GET /api/sessions/{id}`.
* Reload after publish: card does not reappear.
* Superseded draft: two `prepare_tip` calls in one session, publish the second, reload — card does not show the first.
* Cross-session: two tabs, prepare tip in tab A, tab B shows no card.
* All four scenarios pass for tip, idea, and collab.

**Approval gate before Phase 3:** Rob confirms local + staging coverage of the five scenarios. Monitor tips gallery and idea board for 15-30 minutes post-staging-deploy for any regression in existing record reads.

### Phase 3 — W4-01: Wrapup context loading, journal policy, versioned pulse

**Design doc:** `docs/designs/2026-04-19-wrapup-context-loading.md`

**What it changes:** Wrapup sessions pre-load three context sources (today's intake responses, today's journal entries, previous week's digest) into the system prompt at session start. Removes `_auto_save_journal` fallback from wrapup. Filters `save_journal` out of intake's tool registry. Moves pulse questions out of `skills/wrapup.md` into `config/pulse-surveys.json` with versioned per-user answer tracking in `profiles/{user_id}/pulse-responses.json`. Extends `/forge-analytics` map-reduce pipeline to extract pulse answers from wrapup transcripts.

**Blast radius:** Largest of the three phases. Touches multiple files across backend agent, skills, config, and analytics. Adds a new JSON config file and new S3 storage path. Modifies the wrapup skill's flow.

**Success criteria:**
* Wrapup system prompt contains the "Context for Today's Wrap-up" section with correct subsections (or graceful subset).
* AI references today's plan specifically in opening turns.
* Pre-Tuesday backfill: running `/forge-analytics --week 4` on production populates `pulse-responses.json` for users who completed Week 4 wrapup.
* Week 4 completers do not get re-asked the pulse questions on their Week 5 wrapup.
* Week 4 skippers get asked normally on Week 5 wrapup.
* No journal entry is written at wrapup session end.
* Late joiner's late-week wrapup still works when prior-week digest is missing.

**Approval gate before prod deploy:** Rob confirms all scenarios pass on staging with 2-3 copied production users (including at least one Week 4 pulse completer and one skipper).

## Out of scope (deferred to post-Week 5)

| Bug | Why deferred |
|---|---|
| W4-02 (journal duplicate saves, wrong week tag) | Wrong week tag was a testing artifact from `program_week_override`, not a real bug. Duplicate saves are mostly cosmetic; W4-01 removes the largest source (wrapup auto-save) as a side effect. Remaining dedup fix (across-turn transcript stripping) is too big a structural change for a 5-day ship. |
| W4-05 (wrap-up entry discoverability) | Home button already exists; system prompt tells AI where it is. Fix path would be prompt-tightening, but not priority for Week 5. |
| W4-06 (save_journal called without content) | 1 confirmed session, self-healing on retry. Low frequency, no user-felt trust damage. |
| W4-07 (pronouns) | No field exists on UserProfile. Fix requires schema addition + activity-log-generation prompt change + retroactive regeneration. Too much surface for this ship. |
| W4-08 (Day N label wrong) | Evidence strongly suggests stale `program_week_override` on test profiles (Rob's and José Segarra's). Data hygiene check, not a code bug. |

## Rollout sequence

1. **Merge Phase 1 to main → production deploys automatically.** Verify prod is stable via PostHog intake-completion events for 30 minutes.
2. **Merge Phase 2 to main.** Verify prod stable: tips gallery, idea board, session loads all continue to work.
3. **Merge Phase 3 to main.** Verify pre-Tuesday: run production `/forge-analytics --week 4` to backfill pulse-responses. Spot-check a few users' pulse state.
4. **Tuesday morning:** monitor first Week 5 wrapups. Intervene only if multiple users hit the same failure.

## Rollback strategy

Each phase is independent enough to revert via a single commit revert if it misbehaves in production. None of the three changes create data that prevents rollback:
* Phase 1 revert: weekly enrichment resumes; the only "loss" is that users who relied on the gate to protect their corrections will start getting clobbered again (same as today).
* Phase 2 revert: the `source_session_id` + `source_tool_call_id` columns on Tip/Collab/UserIdea remain populated but unused; harmless.
* Phase 3 revert: `pulse-responses.json` files remain in S3 but unused; wrapup reverts to the current prompt-based flow. No user-visible data loss.

## Invocation for `/validate-design-and-build`

This plan is the parent. Invoke the skill **once**, pointing at this doc. The skill walks the three phases sequentially.

```
/validate-design-and-build docs/designs/2026-04-19-week-5-release-plan.md
```

Expected behavior, per phase, in order (Phase 1 → Phase 2 → Phase 3):

1. Read the phase's per-phase design doc — these are already approved and codex-validated, so skip the design-draft and codex-validate steps and proceed directly to implementation.
2. Implement via subagent per that design doc's "Implementation plan" section.
3. Iterate `/review` up to 3 times until the diff is clean.
4. Stop at that phase's approval gate. Present to Rob: the phase's success criteria (from the "Success criteria" subsection), the diff summary, and any signals from local/staging smoke tests. Do not commit yet.
5. On Rob's explicit approval, commit and move to the next phase.
6. Repeat for the next phase.

After Phase 3 is approved and committed, the skill is done. Rob handles the merge/deploy sequence described in "Rollout sequence" above.

**Do not skip the approval gates.** Each phase's gate is a deliberate checkpoint — the rationale is blast-radius stacking, not ceremony. If a phase fails to meet its success criteria, stop there and surface the problem rather than proceeding.
