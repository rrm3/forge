# Department-Configurable Intake + Admin UI

## Problem

The intake system has hardcoded objectives (work_summary, daily_tasks, etc.) and a hardcoded system prompt. Every employee gets the same intake regardless of department. This means:
- Marketing and Technology employees answer the same questions
- Department-specific context (tools, workflows, knowledge systems) isn't surfaced
- Department heads can't customize what their team's intake covers
- "Surface starting points for AI Tuesdays" isn't a tracked objective, so the AI may complete all fields before getting to it

## Design

### System prompt architecture

The intake system prompt becomes four composable layers:

```
┌─────────────────────────────────────┐
│  1. Base prompt (shared)            │  AI coach persona, behavior rules,
│                                     │  general instructions
├─────────────────────────────────────┤
│  2. Department context (per-dept)   │  Short markdown doc - tools, systems,
│                                     │  domain knowledge for this department
├─────────────────────────────────────┤
│  3. Intake objectives (per-dept)    │  List of things to cover, managed
│                                     │  via admin UI as cards
├─────────────────────────────────────┤
│  4. Turn progress (dynamic)         │  Haiku analyzes each turn, injects
│                                     │  "Done: X, Y. Remaining: Z"
└─────────────────────────────────────┘
```

Layers 1-3 are static for the duration of a conversation and should use prompt caching (Anthropic cache_control via LiteLLM). Layer 4 is rebuilt each turn.

Messages are also cached: all messages except the current user message get a cache breakpoint.

### Intake objectives

Each objective is a card with:
- `id`: UUID
- `label`: Short name shown in the admin UI ("What they work on day-to-day")
- `description`: Instructions for the AI on what to cover and how to evaluate completion
- `extraction_key`: Key used to store the captured response

Example default objectives (ship with every department):
- What they work on day-to-day
- Their daily tasks and responsibilities
- AI tools they've tried
- Their core skills
- What they want to learn
- Goals for the 12 weeks
- **Identify starting points for their first AI Tuesday** (new)

Departments can add, remove, or reorder these. The AI coach uses the objective descriptions to steer the conversation and knows when each one has been covered.

### Per-turn progress tracking

After each user message, Haiku (fast extraction model) evaluates all objectives against the conversation so far. For each objective it returns:
- `done`: boolean
- `value`: short summary of what was captured (if done)

This replaces the current shadow extraction + field-matching approach. The per-turn progress is injected as layer 4 of the system prompt so the AI coach knows what's left to cover.

When all objectives are marked done, the system prompt tells the AI to wrap up (no more questions, give a warm summary). After the AI responds, `_check_intake_completion` fires and sends the `intake_complete` WebSocket message.

### Department context document

A short markdown document (target: under 500 words) injected directly into the system prompt. Contains department-specific knowledge the AI coach should know during intake:
- Key tools and systems the department uses
- Common workflows
- Relevant organizational context

This is separate from the longer `department-resources/*.md` files used for search. Those remain in the search index for post-intake conversations.

### Storage

All config stored as JSON files - on disk for local dev, S3 for production.

**Department config** (`config/departments/{department}.json`):
```json
{
  "prompt": "Technology uses GitHub, AWS, Jira...",
  "objectives": [
    {
      "id": "abc123",
      "label": "What they work on day-to-day",
      "description": "Understand their actual daily work, not just their title",
      "extraction_key": "work_summary"
    },
    {
      "id": "def456",
      "label": "Starting points for AI Tuesdays",
      "description": "Identify 2-3 specific activities they could work on",
      "extraction_key": "starting_points"
    }
  ]
}
```

**Admin access** (`config/admin-access.json`):
```json
{
  "rob@digitalscience.com": ["*"],
  "sarah@digitalscience.com": ["marketing", "sales"],
  "james@digitalscience.com": ["technology"]
}
```

**Per-user intake responses** (`profiles/{email}/intake-responses.json` in S3):
```json
{
  "abc123": {
    "value": "Manages meetings, emails, firefighting...",
    "captured_at": "2026-03-21T10:00:00Z"
  },
  "def456": {
    "value": "Build a knowledge-connecting agent, automate decision workflows",
    "captured_at": "2026-03-21T10:05:00Z"
  }
}
```

This is schemaless - departments define objectives, responses are stored as key-value pairs by objective ID. Athena-queryable later for analytics.

### Admin UI

**Entry point:** "Manage Department" in the TopBar user dropdown menu. Only visible to users listed in `admin-access.json`. Clicking it opens a full-page admin view (replaces the entire app, no sidebar).

**Layout:**
```
┌──────────────────────────────────────────────────┐
│  DS Logo        [Marketing ▾]           RM  Rob  │
├──────────────────────────────────────────────────┤
│                                                  │
│   ← Back to AI Tuesdays                         │
│                                                  │
│   Marketing Department                           │
│   ════════════════════                           │
│                                                  │
│   Objectives    Context                          │
│   ═══════════   ───────                          │
│                                                  │
│   ┌────────────────────────────────────────┐     │
│   │  What they work on day-to-day      ⋯  │     │
│   └────────────────────────────────────────┘     │
│   ┌────────────────────────────────────────┐     │
│   │  Their daily tasks                 ⋯  │     │
│   └────────────────────────────────────────┘     │
│   ┌────────────────────────────────────────┐     │
│   │  AI tools they've tried            ⋯  │     │
│   └────────────────────────────────────────┘     │
│                                                  │
│   ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐     │
│   │  + Add objective                      │     │
│   └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘     │
│                                                  │
└──────────────────────────────────────────────────┘
```

**Department picker:** Dropdown in the top bar area, only shown if user manages multiple departments. If they manage one department, just show the name.

**Objectives tab - card interactions:**
- Collapsed card shows label + three-dot menu (⋯)
- Click card to expand inline, revealing:
  - Label input (text field)
  - AI Instructions textarea (with placeholder: "e.g., Ask about the specific tools they use for reporting and what frustrates them most.")
  - Help text below textarea: "Tell the AI what to ask about and how to know when this topic is covered."
  - Save button (collapses card, shows brief checkmark), Cancel button, Delete icon
- Each card saves independently (auto-save per card pattern - no page-level save)
- Drag handle on left edge to reorder
- Cannot delete the last objective (delete button disabled, tooltip: "At least one objective is required")
- "+ Add objective" is a dashed-border card at the bottom, clicks to create a new expanded card

**Context tab:**
- Markdown textarea (full width, ~300px height)
- Placeholder: "Describe your department's key tools, systems, and workflows..."
- Save button below the textarea
- No preview pane (keep it simple - admins write plain text or light markdown)

**DESIGN.md tokens:**
- Page heading: `2xl` (24px), Satoshi 600, `text-primary`
- Tab labels: `sm` (14px), Satoshi 500, active = `primary` with underline
- Card labels: `base` (16px), Satoshi 400, `text-primary`
- Card description/inputs: `sm` (14px), Satoshi 400, `text-secondary`
- Help text: `xs` (12px), Satoshi 500, `text-muted`
- Cards: `surface-white` bg, `border` border, `md` radius, `md` padding
- "+ Add objective": `sm` (14px), `primary` color, dashed `border` border
- Back link: `sm` (14px), `text-muted`, ArrowLeft icon
- Save button: `primary` bg, white text, `md` radius
- Delete: Trash icon in `error` color, no background
- Toasts: `sm` (14px), `surface-raised` bg, `md` radius, top-right position

**Interaction states:**
| Feature | Loading | Empty | Error | Success |
|---------|---------|-------|-------|---------|
| Page load | 3 skeleton cards | N/A (defaults seeded) | "Couldn't load config" + retry | Renders cards |
| Save card | Button shows spinner, inputs disabled | N/A | Toast: "Save failed. Try again." | Card collapses, brief checkmark |
| Save context | Button shows spinner | N/A | Toast: "Save failed. Try again." | Toast: "Saved." |
| Delete card | Instant (optimistic) | N/A (can't delete last) | Toast: "Delete failed." + undo | Card removed with 200ms ease-out |

**Responsive:** Desktop only (768px+ viewport). On mobile, show: "Please use a desktop browser to manage department settings." with a back link.

**Accessibility:**
- Tab through cards, Enter to expand/collapse
- Focus moves to label input on expand, returns to card on collapse
- Tab bar: `role="tablist"`, cards: `role="button"` with `aria-expanded`
- All buttons 44px+ touch targets

**No need to build:**
- User management (handled by admin-access.json)
- Role/permission system (just a lookup against the access list)
- Approval workflows (department heads are trusted to edit their own config)

### Migration from current system

The current hardcoded `_INTAKE_FIELDS` in `context.py` becomes the default objectives. Default config files are pre-created for all 12 departments at deploy time. Rob will work with each department head to customize.

Intake-captured fields are removed from `UserProfile` model: `work_summary`, `daily_tasks`, `ai_tools_used`, `core_skills`, `learning_goals`, `goals`, `ai_superpower`, `intake_fields_captured`. These move entirely to `intake-responses.json`. Fields that come from the org chart (`name`, `email`, `title`, `department`, `manager`, `direct_reports`, `team`, `location`, `start_date`) stay on the profile.

The `intake_completed_at`, `onboarding_complete`, and `ai_proficiency` fields also stay on the profile since they're system-level flags, not intake responses.

### Edge cases

**Mid-intake config changes:** If a department head updates objectives while someone is mid-intake, the next turn picks up the new objectives. This may create inconsistency between completed and remaining objectives in the intake-responses file. Accepted trade-off - not expected to happen often.

### Backend changes

**New files:**
- `backend/repository/department_config.py` - Read/write department config (local files or S3)
- `backend/api/admin.py` - Admin API endpoints (get/update department config, get admin access)

**Modified files:**
- `backend/agent/context.py` - Build system prompt from four layers instead of hardcoded
- `backend/agent/extraction.py` - Per-turn objective evaluation replaces field-matching
- `backend/agent/executor.py` - Check all objectives done instead of field list
- `backend/api/websocket.py` - Load department config when starting intake session
- `backend/lambda_ws.py` - Same for production

### Frontend changes

**New files:**
- `frontend/src/components/AdminPanel.tsx` - Department config editor
- `frontend/src/api/admin.ts` - Admin API client

**Modified files:**
- `frontend/src/App.tsx` - Route to admin panel for authorized users
- `frontend/src/components/TopBar.tsx` - Admin link for authorized users

### Prompt caching implementation

LiteLLM supports Anthropic prompt caching via the `cache_control` field on messages:

```python
messages = [
    {
        "role": "system",
        "content": [
            {"type": "text", "text": base_prompt + dept_context + objectives},
            {"type": "text", "text": turn_progress, "cache_control": {"type": "ephemeral"}},
        ],
    },
    # ... conversation messages ...
    {
        "role": "user",  # second-to-last message
        "content": "...",
        "cache_control": {"type": "ephemeral"},
    },
    {
        "role": "user",  # current message, not cached
        "content": "...",
    },
]
```

The static layers (base + department context + objectives) are cached across turns. The conversation history up to the previous message is also cached. Only the current turn's progress injection and the new user message are uncached.

### NOT in scope

- **Responsive admin panel** - Desktop only. Department heads editing AI instructions is a sit-down task.
- **Admin access management UI** - Admin list is a JSON file, edited manually or via CLI. ~12 people.
- **Approval workflows** - Department heads are trusted to edit their own config.
- **Version history / undo for config** - Git history on the JSON files is sufficient for now.
- **Per-user analytics dashboard** - Intake responses are in S3, queryable via Athena later.
- **Dark mode for admin panel** - Internal tool, low priority.

### What already exists

- **DESIGN.md** - Comprehensive design system with typography, color, spacing, motion tokens
- **HomeScreen.tsx** - Card pattern (bordered cards, icon + label, hover to primary-subtle) reusable for objective cards
- **TopBar.tsx** - Dropdown menu pattern, banner pattern (masquerade) reusable for department context
- **SessionList.tsx** - Inline edit pattern (double-click rename, two-tap delete)
- **IntakeView.tsx** - Completion card already built (Sparkles icon, "You're all set!", "Let's get started" button)
- **department-resources/*.md** - 12 department markdown files (longer versions, for search index)
- **S3 storage abstraction** - Already used for transcripts, reusable for config and intake responses

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | CLEAR (stale) | mode: SELECTIVE_EXPANSION, 0 critical gaps |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 2 | CLEAR (stale) | 0 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 5 | CLEAR | score: 3/10 → 8/10, 5 decisions |

* **UNRESOLVED:** 0 across all reviews
* **VERDICT:** DESIGN CLEARED. Eng review is stale (from prior plan) - recommend re-running for this plan before implementation.
