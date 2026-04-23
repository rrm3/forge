# Week 5 e2e test plan — risk-prioritized

**Date:** 2026-04-19 (Sunday night, ships Tuesday Apr 21)
**Scope:** Validate Phase 1 (enrichment gate) + Phase 2 (preview hydration) + Phase 3 (wrapup context) against the specific regression risks both adversarial reviewers flagged.
**Environment:** staging (deploy `24643840479` succeeded at 01:13 UTC)
**Execute:** Monday Apr 20

## What this plan is NOT

Not a full regression test. Not a substitute for running every feature. It targets **the exact scenarios where our tests have gaps** — the places a merge-and-ship could bite us that weren't covered by the 333 unit tests.

Priority ranking: P0 = must pass before merging staging → main. P1 = strong preference. P2 = nice-to-have validation.

## Setup (run once at start of testing)

```bash
# Make sure AWS is authed
AWS_PROFILE=forge aws sts get-caller-identity

# Copy three flavors of test users
# (pick real prod users matching each shape — if none match, create synthetic state)

# User A: returning user, already enriched. Used for Phase 1 returning-user check.
AWS_PROFILE=forge python scripts/copy-user-to-staging.py \
  --email fabio@digital-science.com --week 4 --include-sessions

# User B: user who skipped their Week 1 intake. Used for Phase 1 skip-intake trap regression.
# If no real user fits, create manually on staging DynamoDB:
#   intake_skipped=True, intake_weeks={"1": "<timestamp>"}, intake_enrichment_completed_at absent
AWS_PROFILE=forge python scripts/copy-user-to-staging.py \
  --email <user-who-skipped>@digital-science.com --week 4 --include-sessions

# User C: fresh user, no intake at all. Used for Phase 1 late joiner + full journey scenarios.
# Create synthetic on staging — just a new email, no profile yet.
```

Masquerade in browser:
```js
localStorage.setItem('forge-masquerade', '<email>');
location.reload();
```

## Phase 1 — enrichment gate (W4-03)

### P0-1: Fabio's original bug — returning-user corrections persist

**Why:** This is the exact scenario Fabio reported. The test that would have saved us.

**Setup:** User A (already-enriched, intake_weeks contains Week 1-4, intake_enrichment_completed_at is set).

**Action:**
1. Masquerade as User A on staging.
2. Set `program_week_override = 5` on their profile.
3. Start a Week 5 intake session.
4. Complete the intake normally. If asked about work summary, give a DIFFERENT answer than what's in their current profile (e.g. "I'm working on X new thing this week").
5. Let the session complete.

**Verification (DynamoDB):**
```bash
AWS_PROFILE=forge aws dynamodb get-item \
  --table-name forge-staging-profiles \
  --key '{"user_id": {"S": "<staging-user-id>"}}' \
  --projection-expression "intake_enrichment_completed_at, intake_summary, work_summary, core_skills"
```
* `intake_enrichment_completed_at`: should be UNCHANGED from before (same timestamp).
* `intake_summary`: should be UNCHANGED (not overwritten by Week 5 check-in).
* Any `update_profile` calls the AI made during Week 5 intake should have persisted.

**Pass criteria:** Pre-existing identity fields are preserved. User corrections made DURING Week 5 intake survive.

**Fail signal:** If `intake_summary` or `work_summary` changed to reflect something from the Week 5 transcript, the gate didn't fire. REVERT Phase 1.

### P0-2: Fresh user first-ever intake runs enrichment

**Why:** The gate must not block enrichment for users who have never been enriched.

**Setup:** User C (no profile yet, or fresh profile with no intake_weeks).

**Action:** Log in as User C, complete their Week 5 intake (set override).

**Verification:**
```bash
AWS_PROFILE=forge aws dynamodb get-item \
  --table-name forge-staging-profiles \
  --key '{"user_id": {"S": "<user-c-id>"}}' \
  --projection-expression "intake_enrichment_completed_at, intake_summary, ai_proficiency, work_summary"
```
* `intake_enrichment_completed_at`: should be SET to a timestamp within the last minute.
* `intake_summary`, `work_summary`, `ai_proficiency`: should be populated from the transcript.

**Pass criteria:** All identity fields populated. Marker set.

**Fail signal:** Enrichment didn't run → identity fields empty → check logs for "Skipping enrichment" with a user_id that shouldn't have been skipped.

### P0-3: Skip-intake user first REAL intake still runs enrichment

**Why:** 149 production users are in `intake_skipped=True` state. The predicate MUST correctly identify them as eligible for first enrichment.

**Setup:** User B. If no real user fits, manually put a staging profile into this state:
```bash
AWS_PROFILE=forge aws dynamodb update-item \
  --table-name forge-staging-profiles \
  --key '{"user_id": {"S": "<user-b-id>"}}' \
  --update-expression "SET intake_skipped = :t, intake_weeks = :w REMOVE intake_enrichment_completed_at" \
  --expression-attribute-values '{":t": {"BOOL": true}, ":w": {"M": {"1": {"S": "2026-03-24T10:00:00+00:00"}}}}'
```

**Action:** Masquerade, set week override = 5, complete a real Week 5 intake.

**Verification:** Same as P0-2 — `intake_enrichment_completed_at` should be set, identity fields populated.

**Pass criteria:** Even though `intake_weeks["1"]` exists (from skip), enrichment still fires.

**Fail signal:** If the gate skipped enrichment for this user, the predicate is using the wrong signal.

### P1-4: Double intake in one week doesn't re-run enrichment

**Why:** The "already completed this week" recovery path.

**Setup:** User C after P0-2 has run.

**Action:** Start a new intake session for the same week (shouldn't be possible via UI, but hit the endpoint directly if needed). Otherwise, reload the app multiple times — the frontend should skip intake if `intake_weeks[current_week]` is set.

**Verification:** `intake_enrichment_completed_at` timestamp should NOT change.

## Phase 2 — preview card hydration (W4-04)

### P0-5: Tip preview happy path + reload doesn't resurrect

**Why:** The published-card-reappears bug (bc23840 fixed) must NOT come back.

**Setup:** User A (logged in as any user).

**Action:**
1. Start a chat session.
2. Prompt: "I want to share a tip about using Claude for code review." Let the AI draft and call `prepare_tip`.
3. Verify: TipPreviewCard appears with editable fields.
4. Click Publish. Verify: card clears, "Tip published" confirmation shows.
5. Navigate to /tips and verify the tip appears.
6. Navigate back to the session.

**Verification step 6:** The preview card MUST NOT reappear.

**DynamoDB check:**
```bash
AWS_PROFILE=forge aws dynamodb scan \
  --table-name forge-staging-tips \
  --filter-expression "author_id = :u" \
  --expression-attribute-values '{":u": {"S": "<staging-user-id>"}}' \
  --projection-expression "tip_id, source_session_id, source_tool_call_id, title"
```
* Latest tip should have both `source_session_id` and `source_tool_call_id` populated (not empty strings).

**Pass criteria:** Card appears on prepare, clears on publish, does not reappear on reload. Published record has provenance fields.

**Fail signal:** If card reappears, the Limit-before-FilterExpression fix didn't stick. If provenance fields empty, the request body threading broke.

### P0-6: Tips gallery still loads (regression check)

**Why:** New optional fields on existing hand-serialized Tip records. Must not break legacy row deserialization.

**Action:** Navigate to /tips as any user. Scroll through the list.

**Verification:** All existing tips load. No console errors. No 500 on `GET /api/tips`.

**Pass criteria:** Tips gallery works identically to before.

**Fail signal:** Blank page, 500 error, or specific tips missing → serializer broke on legacy data.

### P0-7: WS event dropped → rehydration via active_preview

**Why:** The original Lian Tze Lim failure. If `tip_ready` gets lost, the card should still appear on reload.

**Action (hardest to simulate cleanly):**
1. Start a chat session, prompt for a tip.
2. While the AI is generating (look for the typing indicator after prepare_tip), close the browser tab IMMEDIATELY after the tool_call pill appears but before the card renders. Or: disable WS in DevTools → Network → toggle "Offline" for 2 seconds around the prepare_tip moment.
3. Reopen the tab, return to the session.

**Verification:** Preview card appears via the active_preview hydration path.

**Alternative verification (direct API hit):**
```bash
# After a prepare_tip has fired on a session (even successful ones), verify active_preview is computed correctly:
curl -H "Authorization: Bearer <staging-token>" \
  https://staging.forge.digital-science.com/api/sessions/<session_id> | jq '.active_preview'
```
* Unpublished tip: returns the preview JSON.
* Published tip: returns `null`.

**Pass criteria:** `active_preview` correctly reflects published vs unpublished state based on the latest `prepare_*` tool call in the transcript.

### P1-8: Superseded draft doesn't resurrect

**Why:** Phase 2 spec said latest prepare_* wins. Tests are unit-level; validate in a real session.

**Action:**
1. Session. Prompt: "Prepare a tip about X."
2. Before clicking Publish, prompt: "Actually, prepare a different tip about Y instead." AI should call prepare_tip again with new content.
3. Verify card now shows the Y version.
4. Publish Y.
5. Reload the session.

**Verification:** No card appears. The X draft is not resurrected.

### P1-9: Idea and Collab previews (parity with tips)

Repeat P0-5 for `prepare_idea` and `prepare_collab`. Idea via the brainstorm flow. Collab via intake week 3+ where the collab objective is present or via direct chat prompt.

## Phase 3 — wrapup context + journal + pulse (W4-01)

### P0-10: Wrapup context renders today's intake plan

**Why:** This is the specific trust-damaging bug from Week 4. AI must reference today's plan in the opening.

**Setup:** User A with a completed Week 5 intake today (run P0-1 first). Confirm `intake-responses.json` has a `plan-day5` entry.

**Action:** Masquerade, set program_week_override=5, start a Week 5 wrapup session.

**Verification:** AI's opening message should explicitly reference the plan. Example: "This morning you said you wanted to work on [X from intake]. How did that go?"

**If access to backend logs (dev_mode):** Inspect the system prompt and verify it contains:
```
## Context for Today's Wrap-up
### This morning you set these intentions
- Plan for Day 5: <their plan text>
```

**Pass criteria:** AI visibly references the plan. System prompt shows the Context section with today's intake subsection.

**Fail signal:** AI opens generically ("How was your day?") — context loader returned empty. Check logs for "Failed to load wrapup context".

### P0-11: Wrapup does NOT write a journal entry

**Why:** `_auto_save_journal` was deleted. Must not regress to creating entries.

**Action:** Complete the wrapup from P0-10.

**Verification:**
```bash
AWS_PROFILE=forge aws dynamodb query \
  --table-name forge-staging-journal \
  --key-condition-expression "user_id = :u" \
  --expression-attribute-values '{":u": {"S": "<staging-user-id>"}}' \
  --projection-expression "entry_id, created_at, tags"
```
Look for entries with `created_at` during the wrapup session. There should be ZERO new entries from the wrapup.

**Pass criteria:** No journal entry created during wrapup.

**Fail signal:** New journal entry with `auto-save` tag → the deletion didn't stick.

### P0-12: Intake does NOT allow save_journal

**Why:** Tool filter was added. Verify the AI cannot save journals during intake (and that intake completes anyway).

**Setup:** User C (or any user starting fresh intake).

**Action:** Complete the intake. The AI should not attempt to call save_journal (you won't see a save_journal tool pill if dev_mode is on).

**Verification:**
```bash
# After intake completes, verify no journal entries were written during it.
# Compare timestamps of journal entries to intake session window.
AWS_PROFILE=forge aws dynamodb query \
  --table-name forge-staging-journal \
  --key-condition-expression "user_id = :u" \
  --expression-attribute-values '{":u": {"S": "<user-c-id>"}}'
```

**Pass criteria:** No journal entries during the intake session. Intake completes normally (user is not stuck; `intake_weeks` updated).

**Fail signal (CRITICAL):** User stuck at intake → REVERT Phase 3 immediately.

### P0-13: Pulse asked cold to fresh user

**Why:** First time a user is asked pulse, they should see the questions.

**Setup:** User C (or any user without a `pulse-responses.json` file).

**Verify pre-state:**
```bash
AWS_PROFILE=forge aws s3 ls s3://forge-staging-data/profiles/<user-c-id>/pulse-responses.json
# Should return NoSuchKey / empty
```

**Action:** Start a wrapup session, let the AI walk through the questions.

**Verification:** AI asks both pulse questions (progress 1-5, impact 1-5) one at a time after the open-ended discussion.

**Pass criteria:** Both pulse questions asked.

### P1-14: Pulse SKIPPED when already answered

**Why:** The entire point of the versioned pulse infrastructure.

**Setup:** After P0-13, seed User C's pulse-responses.json with v1 answers:
```bash
cat > /tmp/pulse.json <<EOF
[
  {"question_id": "progress", "version": "v1", "level": 3, "week": 5, "answered_at": "2026-04-20T16:00:00+00:00"},
  {"question_id": "impact", "version": "v1", "level": 3, "week": 5, "answered_at": "2026-04-20T16:00:00+00:00"}
]
EOF
AWS_PROFILE=forge aws s3 cp /tmp/pulse.json s3://forge-staging-data/profiles/<user-c-id>/pulse-responses.json
```

**Action:** Start a NEW wrapup session (or reset session and start over).

**Verification:** AI should NOT ask the pulse questions. The wrapup skips straight from the open-ended discussion to the next-week setup.

**Pass criteria:** No pulse questions asked.

**Fail signal:** AI asks pulse despite pulse-responses.json being present → predicate broken. Users will be re-asked every week.

### P1-15: Wrapup graceful when no prior digest

**Why:** Week 1 users have no previous digest. Must not break.

**Setup:** User C post-P0-13 (only one week of data, no week-4 digest in staging).

**Action:** Start Week 5 wrapup.

**Verification:** Session runs, context section omits the "Last week's digest" subsection, AI behavior is normal.

**Pass criteria:** No error, session completes.

### P2-16: Timezone — Auckland user

**Why:** Timezone logic for "today's intake" / "today's journal" is the trickiest piece.

**Setup:** Manually set a staging user's timezone:
```bash
AWS_PROFILE=forge aws dynamodb update-item \
  --table-name forge-staging-profiles \
  --key '{"user_id": {"S": "<user-id>"}}' \
  --update-expression "SET #tz = :t" \
  --expression-attribute-names '{"#tz": "timezone"}' \
  --expression-attribute-values '{":t": {"S": "Pacific/Auckland"}}'
```

**Action:** If possible, time-shift the test — or just verify the system prompt rendering when user's timezone is set. A full Auckland e2e is unlikely; the unit tests cover the date-window math.

**Pass criteria:** Session works. Context rendering doesn't crash.

## Combined scenario — full user journey (P1-17)

**The one test that exercises all three phases in sequence.**

**Setup:** User C (fresh).

**Action:**
1. First visit: land on home page. Frontend should route to intake.
2. Complete Week 5 intake. State the plan for today: "I want to try using Claude for writing documentation."
3. Verify intake completes, user is out of intake view (Phase 1 enrichment runs, marker set — check DB).
4. Navigate to home, start a chat session. Prompt: "I learned something cool, let me share a tip about document generation."
5. AI calls prepare_tip. Card appears (Phase 2).
6. Edit the tip slightly, click Publish. Card clears. Tip is in /tips gallery.
7. Navigate back to home, click "End-of-Day Wrap-up".
8. Wrapup starts. AI should reference the documentation plan (Phase 3 context) AND the tip that was published today (via today's journal entries if save_journal was called in the chat).
9. Answer both pulse questions.
10. Session ends.

**Verification:** All three phases visibly contributed. User state shows:
* `intake_enrichment_completed_at` set
* A Tip record with provenance
* No journal entry from the wrapup itself
* (After /forge-analytics runs) `pulse-responses.json` with v1 answers

## Rollback cheatsheet

Each phase is a distinct merge commit on staging. Can revert individually without touching the others.

```bash
# Get the merge commits
git log staging --oneline | grep "Merge Phase"

# Revert Phase 3 only (biggest scope, most likely to need rollback)
git revert -m 1 <phase-3-merge-sha>

# Revert Phase 2 only
git revert -m 1 <phase-2-merge-sha>

# Revert Phase 1 only
git revert -m 1 <phase-1-merge-sha>

# Push the revert, auto-deploys
git push origin staging
```

## Exit criteria

**Proceed to merge staging → main for Tuesday if:**
* All P0 scenarios pass.
* At least half of P1 scenarios pass.
* No stuck-in-intake failure on any scenario (any such failure is an automatic revert of the relevant phase).

**Hold and revert the offending phase if:**
* Any P0 fails with a data-corruption signal (profile overwrites, stuck intake, duplicate publishes).
* Tips gallery or admin panel regresses on legacy records.

## Time budget

Estimated walkthrough time: ~90-120 minutes for all P0 + selected P1. Plus 30 minutes of setup. Plan a 3-hour block Monday.

Shortest viable path if time pressure is acute: **P0-1, P0-2, P0-5, P0-6, P0-10, P0-11, P0-12**. That's seven scenarios, covers one critical path per phase plus the two nastiest regression checks. ~60 minutes.
