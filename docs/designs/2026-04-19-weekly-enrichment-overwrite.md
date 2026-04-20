# Skip Opus enrichment on weekly check-in intakes (W4-03)

**Date:** 2026-04-19
**Bug:** W4-03 — Profile updates for identity fields (core_skills, work_summary, ai_proficiency, intake_summary, learning_goals) silently fail to persist
**Status:** Design

## Problem

User Fabio Mörmann reported that corrections he made to his profile via the AI would be gone the next session. He worked around by writing corrections into journal entries, which stick. He accumulated four "profile-correction" journal entries across weeks. He's the only user who diagnosed this, but other users are almost certainly affected and not sophisticated enough to name it.

## Verified root cause

`_enrich_profile_async` at `backend/agent/executor.py:722` runs after every intake completion — including Week 2, 3, and 4 weekly check-ins. It reads the current session's transcript, asks Opus to re-extract a fixed set of profile fields, and overwrites whatever is on the profile. Affected fields match Fabio's list exactly:

```python
allowed = {
    "work_summary", "daily_tasks", "products", "ai_tools_used",
    "core_skills", "learning_goals", "ai_superpower", "goals",
    "intake_summary",
}
# plus ai_proficiency scored separately at lines 777-782
```

The failure mechanism is more specific than "hallucination." Opus is following its prompt ("extract based ONLY on what the USER said"). Week 2+ intake transcripts are narrow weekly check-ins that barely discuss core_skills, work_summary, or proficiency in depth. Opus produces **minimal but non-empty** extractions from sparse input, and the defensive filter at line 751 (`if k in allowed and v`) only skips empty/falsy values. Partial extractions pass through and clobber the richer Week 1 baseline or any user correction.

Evidence from Fabio's data:
* Week 3 intake transcript shows him calling `update_profile` mid-session to set `intake_summary` for that week. The same session's enrichment wrote a different `intake_summary` over it a few minutes later.
* Week 4 intake same pattern: a user-set `intake_summary` update followed by an overwrite from that session's enrichment.
* Current production profile's `intake_summary` contains text signature from the Week 1 Opus extraction, not either of Fabio's Week 3 or Week 4 explicit corrections.

Second-order finding: `ai_proficiency` re-scoring has the same structural flaw. Weekly re-scoring on thin check-in transcripts can oscillate a stable score.

## Goals

1. User-initiated `update_profile` calls to the affected fields stick permanently.
2. Week 1 initial intake still fully enriches the profile — this is the only session where identity extraction is appropriate.
3. Weekly check-ins (Week 2+) do not modify identity profile fields, period.
4. `ai_proficiency` scoring follows the same rule.

## Non-goals

* Adding per-field "user-corrected" flags. Fancier than needed; D1 covers the observed failure mode without new schema.
* Extracting week-specific observations (e.g., "this week's wins") from check-in transcripts. That's a separate feature; different storage location; not in scope.
* Retroactively restoring lost corrections. Affected users re-state once after deploy; the fix ensures future corrections stick.

## Design

Gate `_enrich_profile_async` and the AI proficiency scoring inside it to **the user's first successful enrichment**, not to calendar Week 1 and not to first completed intake.

Why not `program_week == 1`: `effective_program_week()` is purely calendar/override-based. A user who joins in Week 3 would never satisfy `program_week == 1` and therefore never get their initial identity enrichment. Late joiners are a supported case.

Why not `not (profile.intake_weeks or {})`: `intake_weeks` gets populated by `POST /api/profile/skip-intake` *without* running enrichment. 149 production users are currently in that state (`intake_skipped=True`, `intake_weeks` populated, identity fields empty). If the gate uses `intake_weeks` emptiness, those users will be silently blocked from enrichment the first time they complete a real intake — a new bug caused by the fix. `intake_weeks` also gets populated by the migration script `migrate-objectives-to-company.py` without enrichment. And if a first enrichment crashes mid-flight, `intake_weeks[N]` is already written but the identity fields are empty — the user should get retried, but `intake_weeks` emptiness would say they shouldn't.

Why not `not profile.intake_summary`: `skills/intake.md:255` explicitly instructs the AI to call `update_profile` with `intake_summary` during the intake closing turn. `tools/profile.py:118` has `intake_summary` in the `update_profile` allowlist. So `intake_summary` is populated BEFORE `_enrich_profile_async` runs for the first time, making it a contaminated signal that would skip first enrichment for every new user.

The correct signal is a dedicated field `intake_enrichment_completed_at` that is written by `_enrich_profile_async` **and by nothing else** — no skill path, no `update_profile` allowlist, no API endpoint. The field is added to `UserProfile` as `datetime | None = None`, set to `datetime.now(UTC)` at the end of a successful enrichment run (after all writes), and read by `_check_intake_completion` as the gate predicate.

The enrichment is invoked from `backend/agent/executor.py:553-554`:

```python
if enrichment_args:
    await _enrich_profile_async(**enrichment_args)
```

`enrichment_args` comes from `_check_intake_completion`. Compute the first-enrichment signal from the dedicated `profile.intake_enrichment_completed_at` field (written only by `_enrich_profile_async`) and pass it through:

```python
is_first_intake = profile.intake_enrichment_completed_at is None

# ... existing completion write (intake_completed_at, onboarding_complete,
#     intake_weeks[N], intake_skipped=False) ...

return {
    "deps": deps,
    "user_id": user_id,
    "transcript": transcript,
    "objectives": objectives,
    "is_first_intake": is_first_intake,   # new
}
```

At the end of a successful enrichment run, `_enrich_profile_async` writes the marker:

```python
await deps.profiles_repo.update(
    user_id,
    {"intake_enrichment_completed_at": datetime.now(UTC).isoformat()},
)
```

The marker write is the last step inside the enrichment `try` block, so a crash anywhere earlier leaves the field None and the next intake retries.

Inside `_enrich_profile_async`, gate the whole body on that boolean:

```python
async def _enrich_profile_async(deps, user_id, transcript, objectives, is_first_intake):
    if not is_first_intake:
        logger.info("Skipping enrichment — not first intake (user=%s)", user_id)
        return
    # ... existing body unchanged
```

The gate covers both the field enrichment (lines 733-775) and the proficiency scoring (lines 777-782) since they share the function body.

Two lines of new logic. One early-return.

## What the gate preserves

* First-ever intake completion runs enrichment exactly as today — for every user, whether their first intake is in calendar Week 1, Week 3, or Week 8.
* `update_profile` tool, called from any session type at any time, continues to write directly to DynamoDB and will now survive indefinitely.
* `_check_intake_completion`'s other work — marking `intake_weeks[N]`, sending `intake_complete`, creating intake ideas — runs on every week as before.
* The raw per-objective answers in `intake_responses` continue to be written by the objective evaluator during each intake session.

## What the gate intentionally drops

* Opus re-extraction of identity fields from subsequent (Week 2+) intake transcripts. This is the behavior causing the bug. It provides no net value on narrow weekly transcripts and actively destroys user corrections.
* Weekly AI proficiency re-scoring. Stable once set initially; weekly oscillation from thin check-in data is noise, not signal.
* **Post-completion richer summaries on `intake_responses` for Week 2+.** `_enrich_profile_async` also rewrites per-objective values in `intake_responses` with Opus-synthesized summaries (lines 763-775). After this gate, Week 2+ intake_responses will retain the raw evaluator output (captured during the live session) but will not receive the richer Opus-post-processed summaries. Consumers of this data: `scripts/generate-digest.py:81` and the admin intake detail view. Both continue to work — they read whatever is in `intake_responses`, which will now be the evaluator's output instead of the post-hoc synthesis. Acceptable trade-off: digest and admin views show slightly less polished per-objective summaries for Week 2+ than they do today, in exchange for eliminating the identity-field corruption loop.

If any of these ever becomes desired in a more targeted form (e.g., "week-specific wins observations" or "richer per-objective summaries without touching identity fields"), they belong in a separate code path writing to separate storage — not in the identity-field enrichment.

## Implementation plan

| # | File | Change |
|---|---|---|
| 1 | `backend/models.py` | Add `intake_enrichment_completed_at: datetime | None = None` to `UserProfile`. |
| 2 | `backend/repository/profiles.py` | Extend `_serialize` and `_deserialize` for the new field (ISO-format round-trip through DynamoDB). |
| 3 | `backend/agent/executor.py:666-717` | In `_check_intake_completion`, compute `is_first_intake = profile.intake_enrichment_completed_at is None` inside the `if all_complete:` branch. Add `is_first_intake` to the dict returned as `enrichment_args`. |
| 4 | `backend/agent/executor.py:722-785` | Add `is_first_intake: bool` parameter to `_enrich_profile_async`. First line of the function body: early-return with a log line if `not is_first_intake`. At the end of the `try` block (after proficiency scoring), write the `intake_enrichment_completed_at` marker. |
| 5 | `tests/test_enrichment_gate.py` | Function-level: (a) calendar Week 1 first intake runs enrichment AND writes the marker; (b) late joiner first intake runs enrichment; (c) Week 2+ skips enrichment; (d) Week 2+ preserves existing values. Predicate-level: (e) fresh user is first; (f) enriched user is not first; (g) skip-intake user is still first; (h) crash-mid-flight retries; (i) intake skill writing `intake_summary` does NOT contaminate the gate. |

Total diff: under 20 lines of production code. Test surface is the meaningful addition.

## Testing plan

### Local-first e2e (per prior weeks' practice)

1. `./scripts/dev.sh start`.
2. **Scenario A — returning user (the bug case).** Pick two production users with a Week 1 intake already complete — copy to local dev using the established script (`/forge-analytics-sync` + `scripts/copy-user-to-staging.py --env local`). Include their profile and intake-responses.
3. Verify the copy: profile has populated `work_summary`, `core_skills`, `intake_summary`, `ai_proficiency`.
4. Set `program_week_override = 3` on the copied user.
5. Masquerade, complete a Week 3 intake check-in. After session completes:
   * Assert the profile's `work_summary`, `core_skills`, `intake_summary`, `ai_proficiency`, `learning_goals` are **unchanged** from step 3.
   * Assert `intake_weeks["3"]` was set.
   * Assert the intake_responses file has the Week 3 objective answers.
6. In the same local session, call `update_profile` explicitly (via a chat follow-up asking the AI to correct a specific field). Assert the field is written and persists through another Week 3 session reopen.
7. **Scenario B — late joiner (regression check for the revised gate).** Create a fresh local profile for a new user with `intake_weeks = {}`. Set `program_week_override = 3`. Start and complete their first-ever intake. Assert that enrichment ran: `work_summary`, `core_skills`, `intake_summary`, `ai_proficiency` are populated by the Opus extraction. Assert `intake_weeks["3"]` was set. This scenario confirms the gate doesn't starve late joiners of their initial enrichment.

### Staging pass

Copy one user to staging, set program_week_override to 3, repeat steps 5-6.

### Unit coverage

See implementation plan item 3.

## Rollout

1. Merge to staging.
2. Run the local-first scenarios, then the staging scenarios.
3. Merge to main → production deploy.
4. Post-deploy: affected users (Fabio at minimum) re-state their corrections once. The corrections now stick. No automated backfill — the scope of users impacted is small enough that re-correction on demand is simpler than replaying journal entries into DynamoDB.

## Coherence notes

* **Bug fix is structural, not probabilistic.** Today's failure happens on every Week 2+ intake completion, not just under edge conditions. The gate eliminates the whole class rather than mitigating it.
* **No impact on non-intake session types.** Chat, stuck, brainstorm, tip, collab, wrapup, wrapup → none of them call `_enrich_profile_async`. This change is strictly about what the intake completion path triggers.
* **Consistent with the W4-01 journal policy.** Both fixes share the same principle: weekly check-ins should not duplicate or re-litigate what Week 1 already established. Week 1 is for identity; Week 2+ is for ongoing engagement.
* **`update_profile` continues to be the user-facing correction mechanism.** It was always the intended one; the bug made it unreliable. Post-fix, it works.

## Open items

None that affect this design. The Week 1 enrichment itself continues to work exactly as today — if it has issues (quality, prompt drift), those are separate work.
