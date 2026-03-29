# Day 2+ Intake Refactor

**Date:** 2026-03-29
**Status:** Draft

## Problem

The intake system was designed for Day 1 only: a one-time onboarding gate with per-department questions that are identical across all 12 departments. The program is 12 weeks. We need the intake to evolve into a recurring weekly ritual that captures new information cumulatively and helps users plan each AI Tuesday.

## Design decisions

* **Cumulative questions, not per-week** - questions are added to a running list over time. Each week's intake checks what's already been answered and only asks unanswered ones. No week-tagging needed.
* **Two-tier question architecture** - company-wide base questions (apply to everyone) + department-specific extras (currently only Product and Tech have these).
* **Two-stage weekly gate** - Stage 1: unanswered cumulative objectives. Stage 2: recurring weekly check-in (review last week, plan today). Both must complete before entering the app.
* **Batch pre-processing** - a Monday-night script generates per-user briefings from their previous sessions so the Week 2+ check-in is warm and specific from the first message.
* **Clean UUID migration** - remap old per-department UUIDs to new company-wide UUIDs. No legacy lookup code.

## Architecture

### 1. Question storage

**Before:**
```
config/departments/{dept}.json
  └── objectives: [...7 identical questions per department...]
```

**After:**
```
config/company.json
  └── prompt: "..."           (existing - company-wide system prompt)
  └── objectives: [...]       (NEW - company-wide questions, apply to everyone)

config/departments/{dept}.json
  └── prompt: "..."           (existing - department context)
  └── objectives: [...]       (department-specific extras only, empty for most)
```

**Runtime merge:** When building the objectives list for a user, the system concatenates `company.objectives + department.objectives`. The intake prompt, evaluation, and completion logic all operate on this merged list.

### 2. Company-wide objectives (post-migration)

Six objectives (original 7 minus "Starting points for AI Tuesdays" which is Day 1-specific):

| # | Label | Description |
|---|-------|-------------|
| 1 | What they work on day-to-day | Actual daily work, not job title. 2-3 specific details. |
| 2 | Their daily tasks and responsibilities | Specific tasks, meetings, reports, tools used daily. |
| 3 | AI tools they've tried | Which AI tools used personally and for what. |
| 4 | Their core skills | Strengths - technical, interpersonal, domain expertise. |
| 5 | What they want to learn | Curiosity areas, what they want to get better at with AI. |
| 6 | Goals for the 12 weeks | What they want to achieve during the program. |

New Day 2 objectives added to company list:

| # | Label | Description |
|---|-------|-------------|
| 7 | What they tried in Week 1 | Did they experiment with anything? What worked, what didn't? Ground truth vs stated goals. |
| 8 | How they prefer to learn | Docs, videos, pair-working, trial and error? Helps tailor future suggestions. |

**Department-specific objectives:** Product and Tech retain their 2 existing extra questions (migrated from their current S3 configs). All other departments start with an empty extras list.

### 3. UUID migration

One-time script that runs against production S3:

1. Read each department config from S3, build a mapping: `{old_dept_uuid: new_company_uuid}` for the 7 shared objectives (matched by `extraction_key` since labels are identical).
2. For each user's `profiles/{user_id}/intake-responses.json`:
   - Read the file
   - Remap keys from old department UUIDs to new company UUIDs
   - Write back
3. Upload new `config/company.json` with the 6 retained objectives (drop #7 "Starting points")
4. Rewrite each department config to only contain department-specific extras
5. **Data preservation:** Responses to "Starting points for AI Tuesdays" remain in `intake-responses.json` under their original UUID. They're just no longer tracked as an active objective.

### 4. Two-stage weekly gate

**Stage 1 - Cumulative objectives** (tracked, one-time per question)

Same mechanics as today's intake: LLM evaluates transcript against remaining objectives, marks them complete in `intake-responses.json`. Gate lifts when all unanswered objectives are addressed.

For Week 1 users returning for Week 2: they've already answered objectives 1-6 (and old #7). The system sees objectives 7-8 ("What they tried in Week 1", "How they prefer to learn") as unanswered. Stage 1 is a short conversation covering just those two.

For users who missed Week 1 entirely: Stage 1 covers all 8 objectives. Longer intake, but same flow.

**Stage 2 - Weekly check-in** (recurring, conversational, not tracked as objectives)

After Stage 1 clears (or immediately if no unanswered objectives), the conversation transitions to a recurring check-in. Three prompts, guided by the AI:

* **How did things go since last time?** - follow up on what they worked on, whether they applied what was discussed
* **Review ideas/projects** - are previous ideas still valid or do they want to pivot?
* **Plan the day** - what do they want to focus on today? What would success look like?

The AI uses the **weekly briefing** (see below) to make this specific and warm. These are evaluated conversationally: the AI confirms they've been addressed before showing the completion card. Responses live in the transcript, not `intake-responses.json`. Can be batch-extracted retroactively if needed.

**Completion signals:**
- Stage 1 complete: all cumulative objectives answered (existing `evaluate_objectives` logic)
- Stage 2 complete: AI confirms review/planning is done (new lightweight evaluation - could be a simple "has the user confirmed their plan for today?" check)
- Both stages complete: show completion card, unlock the app

### 5. Intake prompt changes

The intake skill prompt (`skills/intake.md`) needs to be week-aware:

**Week 1 flow** (mostly unchanged):
1. Onboarding cards (4-card sequence)
2. Warm greeting, verify org chart data
3. Work through cumulative objectives conversationally
4. Completion card with resource overview

**Week 2+ flow:**
1. No onboarding cards (skip entirely for returning users)
2. Greeting that picks up where they left off, referencing the weekly briefing
3. If unanswered cumulative objectives exist: weave them into the conversation naturally
4. Transition to weekly check-in: review last week, confirm/adjust direction, plan today
5. Completion card with weekly message (see below)

The prompt should reference the weekly briefing to be specific: "Last week you mentioned trying Claude for your quarterly reports - how did that go?" rather than generic "How was your week?"

### 6. Weekly briefing (batch pre-processing)

A Claude Code skill (`/forge-weekly-briefing` or similar) that Rob runs manually on Mondays. For each active user, it:

1. **Reads:** intake responses, recent session transcripts (chats, wrapups), ideas created, profile data
2. **Generates via LLM:** a structured briefing containing:
   - What the user said they'd work on
   - Ideas they created and current status
   - Key themes from their wrapup
   - Suggested follow-up threads for the check-in
   - Any notable patterns (e.g., user hasn't used tips, user mentioned a blocker)
3. **Writes:** `profiles/{user_id}/weekly-briefing.json`

The intake prompt includes this briefing as context so the AI is warm and specific from message one.

**Schema:**
```json
{
  "generated_at": "2026-03-30T22:00:00Z",
  "program_week": 2,
  "last_session_summary": "Explored using Claude for quarterly report drafting...",
  "ideas": [
    {"title": "Automate quarterly report first draft", "status": "active"}
  ],
  "wrapup_highlights": "Felt productive, wants to go deeper on report automation",
  "suggested_followups": [
    "Did they try the quarterly report workflow during the week?",
    "They mentioned wanting to share the template with their team"
  ],
  "nudges": ["Has not submitted any tips yet"]
}
```

### 7. Completion card changes

**Week 1 completion card** (unchanged):
- Headline: "You're all set!"
- Lists app resources (tips, stuck, brainstorm, wrapup)
- Button: "Let's get started"

**Week 2 completion card:**
- Headline: "Ready for Day 2"
- Brief acknowledgment of what was covered
- Feature nudge: "Did you know you can share tips and tricks with your colleagues? When you discover something useful, tap 'Share a tip' to help others learn from your experience."
- Button: "Let's go"

**Week 3+ completion cards:** Same structure, different feature nudge each week. These can be hardcoded per week or driven from a simple config. Examples:
- Week 3: Nudge brainstorming ("Have a problem you keep running into? Try 'Brainstorm' to explore AI solutions")
- Week 4: Nudge wrapups ("End your day with a quick wrapup to track your progress")
- Later weeks: Cross-functional projects, sharing with colleagues, etc.

### 8. Onboarding cards logic

**Returning users (intake previously completed at least once):** Skip the 4-card onboarding sequence entirely. Go straight into the check-in conversation.

**New users (never completed intake):** Show the full 4-card sequence as today.

**Detection:** Check `profile.intake_completed_at` - if it has a value, this is a returning user regardless of current week.

### 9. Dashboard changes

**Company Questions tab** (new, full admins only):
- Same card-based UI as department objectives
- Editable labels and descriptions
- Add/remove/reorder
- Lives under a "Company" section in the admin panel, separate from department selection

**Department Questions tab** (existing, scoped):
- After migration, most departments show an empty list with "Add objective" button
- Product and Tech show their 2 department-specific questions
- Department admins can add extras for their department

**Weekly Messages tab** (optional, future):
- Edit the completion card nudge text per week
- Low priority - can hardcode for now

### 10. Backend changes summary

**`department_config.py`:**
- `get_company_config()` already exists - extend schema to include `objectives` array
- New helper: `get_merged_objectives(department)` that returns company + department objectives

**`executor.py`:**
- Intake session creation becomes week-aware
- Stage 1 → Stage 2 transition logic
- Load weekly briefing into prompt context

**`extraction.py`:**
- `evaluate_objectives()` unchanged (operates on merged list)
- New lightweight check for Stage 2 completion

**`context.py` (system prompt builder):**
- Week 2+ intake prompt variant
- Include weekly briefing in context

**`models.py`:**
- Profile may need `last_intake_week` field to track which week's check-in was last completed
- Or derive from session data (find most recent intake session, check its week)

**Frontend:**
- `IntakeView.tsx`: Skip onboarding cards for returning users, week-aware completion card
- `OnboardingCards.tsx`: No changes needed (just not shown)
- `AdminPanel.tsx`: New "Company Questions" section
- `program.ts`: Completion card content per week

## Migration plan

1. Write UUID migration script (maps old dept UUIDs to new company UUIDs)
2. Create `config/company.json` with 6 base objectives (new stable UUIDs) + 2 new Day 2 objectives
3. Run migration against production S3 (remap user responses, rewrite department configs)
4. Deploy backend changes (merged objectives, two-stage gate, weekly briefing support)
5. Deploy frontend changes (returning user flow, week-aware completion card, admin panel)
6. Run weekly briefing skill Monday night before Day 2

## Open questions

- Exact wording for Day 2 objectives ("What they tried in Week 1", "How they prefer to learn") - needs refinement
- Should Stage 2 check-in have a time/message minimum, or just let the AI judge when it's done?
- Weekly briefing: how to handle users with zero sessions (no wrapup, no chats)? Probably just skip the briefing and let the check-in be more exploratory.
