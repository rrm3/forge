# Preview card hydration via server-side session metadata (W4-04)

**Date:** 2026-04-19
**Bug:** W4-04 — `prepare_tip` / `prepare_idea` / `prepare_collab` returns success but the UI preview card never appears
**Status:** Design (v2 — supersedes in-transcript-marker approach after codex review)

## Problem

When the agent calls `prepare_tip`, the backend records a `tool_call` in the transcript, executes the tool, and emits a `tip_ready` WebSocket event. The frontend is supposed to render a preview card. Over all four program weeks, users have hit a recurring failure where the card never shows up despite the tool succeeding.

Tuesday's fix (`bc23840`, Apr 14 07:43 AM) fixed the *opposite* bug — the card persisting after publish — by restricting the post-turn detection check to scan only the current turn's messages. The one-shot `tip_ready` emission is now the only chance for the card to reach the user. If that emission is lost (WS reconnect, tab backgrounded mid-send, cold-start hiccup), the card never arrives.

Lian Tze Lim (Week 4 chat-batch-1): "the UI preview didn't appear for her despite tool returning success. She published manually." Emily Koechel had the same pattern for an idea card. Earlier weeks showed the same failure mode.

## Design history

An earlier version of this doc proposed writing a synthetic `tool_result` marker into the session transcript when the user published, and having the frontend re-scan the transcript on session load. An independent codex review flagged several problems:

1. `save_transcript` in `backend/storage.py:135` is a blind full rewrite. The session mutex (`backend/api/websocket.py:237`) only covers WebSocket chat handlers, not HTTP publish endpoints, so `load → append → save` in the publish handler could race with an agent turn's own `save_transcript` and either lose the marker or overwrite a later agent turn.
2. "Latest unpublished" reverse-scan would resurrect superseded drafts. If `prepare_tip(A)` is followed by `prepare_tip(B)` and the user publishes B, the original design would walk past B's marker and hydrate from A.
3. Tip and collab cards have no dismiss action; re-publishing creates a duplicate record. A stale card on reopen was not as benign as the original doc claimed.
4. A simpler approach was available: the source records (tips, collabs, ideas) can themselves record which session and tool_call they came from. The authoritative answer to "was this prepared card published?" then lives on the published record, not in a synthetic transcript marker.

This v2 pivots to that simpler approach.

## Goals

1. The preview card renders reliably even when the initial `tip_ready` WS event is dropped.
2. The card does not re-render after the user publishes it.
3. No transcript mutations from HTTP endpoints — transcript writes stay owned by the agent loop.
4. Same solution works uniformly for tips, ideas, and collabs.
5. Closes the cross-session state leak on `*_ready` handlers.

## Non-goals

* Redesigning the publish flow or WebSocket architecture.
* Changing agent prompt behavior around when `prepare_*` gets called.
* Fixing adjacent bugs outside the preview-card flow (e.g., the missing session-id filter on the `intake_complete` dispatch — noted for later).

## Design

### Source record provenance

Each of the three "prepared → published" record types (Tip, UserIdea, Collab) gains two fields:

* `source_session_id: str` — the session the `prepare_*` tool call fired in.
* `source_tool_call_id: str` — the `tool_call_id` of that specific `prepare_*` call.

`UserIdea` already has `source_session_id`. Tip and Collab don't. All three need `source_tool_call_id` added.

DynamoDB note: these are new optional attributes. Existing records without them will return empty strings on read (non-breaking).

Add a secondary index on `source_session_id` for each of the three tables, or if that's overkill given expected volume, a scan-with-filter on the small per-user list (`tips.list(user_id=X, source_session_id=Y)`). We're querying at most a few records per user per session — likely fine as a filtered scan on the existing user-scoped list. Decide at implementation time based on actual volumes.

### Active preview on session load

The backend endpoint `GET /api/sessions/{session_id}` (`backend/api/sessions.py:54`) returns a flat session object with an embedded `transcript` field today. **Add `active_preview` as a new top-level field alongside the existing ones** — do not restructure the response into a nested `{session: {...}}` shape. All existing fields stay exactly where they are; the new response includes one additional key:

```
... existing flat session fields ...
transcript: [ ... ]
active_preview: {  // new — null when no unpublished preview exists
  type: "tip" | "idea" | "collab",
  tool_call_id: "tc_abc",
  title: "...",
  content: "...",
  tags: ["..."],
  ...type-specific fields...
} | null
```

`active_preview` is `null` when there is no unpublished preview for this session. Old clients that don't know about the field simply ignore it.

Backend logic, in the session load handler:

```python
def compute_active_preview(user_id, session_id, transcript):
    # Walk transcript in reverse. Stop at the first prepare_* tool_call.
    latest = find_latest_prepare_call(transcript)  # tip / idea / collab or None
    if latest is None:
        return None
    if target_record_exists(user_id, latest.type, session_id, latest.tool_call_id):
        return None  # already published
    return build_preview_from_tool_call(latest)
```

`target_record_exists` checks the appropriate repo for a record matching `user_id == user_id AND source_session_id == session_id AND source_tool_call_id == latest.tool_call_id`. Existence means published.

Query approach — the three repos today have different list shapes:

* `UserIdeaRepository.list(user_id=X)` is already user-scoped. Load and filter in memory; a user's own idea list is tiny.
* `TipRepository.list(...)` and `CollabRepository.list(...)` are board-scoped (all users), not user-scoped. For these, **add a new targeted method** on each repo: `find_by_source(user_id, session_id, tool_call_id) -> TipRecord | None` (and equivalent on `CollabRepository`). Implementation uses a DynamoDB filtered query on `user_id` with a `FilterExpression` on `source_session_id` and `source_tool_call_id`. Small, self-contained addition — no GSI required, no change to the board list semantics.

A GSI on `(user_id, source_session_id)` is explicitly *not* needed for initial ship. Revisit only if real traffic shows a latency problem on session load.

The helper **must fail closed to null** on any exception — malformed legacy transcript, repo hiccup, schema drift — and log the error. `_check_tip_prepared` at `backend/agent/executor.py:828` already swallows errors this way; follow the same pattern. A single bad session must not 500 the entire session-load endpoint.

Critically: only the **latest** prepare call is considered. Superseded earlier drafts are never resurrected. This matches the existing backend behavior in `_check_tip_prepared` etc. at `backend/agent/executor.py:828-890`.

### Frontend state hydration

On `SELECT_SESSION` — which fires on user-clicks-a-session, on page load, and on WebSocket reconnect (the reconnect handler at `SessionContext.tsx:230-240` calls `SELECT_SESSION` with the reloaded transcript) — the caller already awaits `getSession(id)`. Extend the SELECT_SESSION action to carry `active_preview` and have the reducer populate `tipReady` / `ideaReady` / `collabReady` from it.

**The reducer must always hard-clear preview state first, then populate from `active_preview` only if it is present and non-null.** This preserves today's behavior exactly for every session that has no unpublished prepare — which is the overwhelming common case — and for any response from a legacy backend that doesn't yet include the field.

```ts
case 'SELECT_SESSION': {
  const preview = action.activePreview ?? null;  // undefined → null
  return {
    ...state,
    activeSessionId: action.sessionId,
    messages: action.messages,
    // Always clear first — default behavior unchanged from today:
    tipReady: null,
    tipPublished: false,
    collabReady: null,
    collabPublished: false,
    ideaReady: null,
    ideaPublished: false,
    ideaContext: null,
    // Then populate from preview only when present and matching type:
    ...(preview?.type === 'tip'    ? { tipReady: extractTipFields(preview) } : {}),
    ...(preview?.type === 'idea'   ? { ideaReady: extractIdeaFields(preview) } : {}),
    ...(preview?.type === 'collab' ? { collabReady: extractCollabFields(preview) } : {}),
    streamingText: '',
    isStreaming: false,
  };
}
```

No client-side transcript scanning. No parsing duplication. The authoritative answer comes from the server.

### Publish path writes provenance, doesn't touch the transcript

The frontend already knows the `tool_call_id` (threaded through the `tip_ready` / `idea_ready` / `collab_ready` WS payload — new addition, see wire changes below) and the `session_id`. The publish API calls pass both:

```ts
await createTip({
  title, content, tags, department, category,
  source_session_id: activeSessionId,
  source_tool_call_id: tipReady.tool_call_id,
});
```

Backend handlers persist both fields onto the new record:

```python
tip = Tip(
    tip_id=..., user_id=user.user_id, ...,
    source_session_id=body.source_session_id,
    source_tool_call_id=body.source_tool_call_id,
)
await repo.create(tip)
```

No transcript write. No race.

### Session-id filter on `*_ready` dispatch

Pre-existing gap in `SessionContext.tsx:369-404`. The `tip_ready` / `idea_ready` / `collab_ready` handlers do not filter on `msg.session_id === activeSessionIdRef.current`. Nearby handlers (`token`, `tool_call`, `tool_result`, `done`, `error`) do. Add the filter. One-line changes per handler.

**Explicitly out of scope: the `intake_complete` handler.** A review pass flagged that adding a session-id filter to `intake_complete` at `SessionContext.tsx:362` — a change we initially considered bundling — would introduce a new way for users to get stuck in intake. If `activeSessionIdRef` is transiently null or stale during a WS reconnect at the instant `intake_complete` arrives, the filter would drop the event; backend has marked intake complete via `intake_completed_at`, but frontend's `intakeComplete` flag would stay false, trapping the user. This is exactly the "stuck in intake" failure pattern we've hit before and cannot reliably QA. The correct fix is to reconcile `intakeComplete` from `profile.intake_completed_at` on session load, which is a bigger change and not in scope. Leaving `intake_complete` unfiltered preserves today's behavior where the worst case is a brief cosmetic flash of "intake complete!" UI in a non-intake session.

## Wire changes

| Surface | Change |
|---|---|
| WS event `tip_ready` / `idea_ready` / `collab_ready` | Add `tool_call_id: string`. Already available in the transcript row being scanned in `_check_tip_prepared` et al. at `backend/agent/executor.py:828+`. |
| HTTP response `GET /api/sessions/{id}` | Add `active_preview: {...} \| null`. |
| HTTP request `POST /api/tips`, `POST /api/ideas`, `POST /api/collabs` | Add optional `source_session_id: str`, `source_tool_call_id: str`. |
| DynamoDB tables `forge-tips`, `forge-user-ideas`, `forge-collabs` | Two new optional attributes per item: `source_session_id`, `source_tool_call_id`. |
| Frontend state | `tipReady.tool_call_id` (and idea/collab equivalents) added. |

All new WS payload fields and request body fields are optional for backward compat during rollout.

## Implementation plan

| # | File | Change |
|---|---|---|
| 1 | `backend/models.py` | Add `source_session_id: str = ""` and `source_tool_call_id: str = ""` to `Tip` and `Collab`. Add `source_tool_call_id: str = ""` to `UserIdea` (source_session_id already exists). |
| 2 | `backend/repository/tips.py`, `backend/repository/collabs.py`, `backend/repository/user_ideas.py` | Extend both `_serialize` and `_deserialize` for the new fields in each repo. These are hand-written, so missing one path silently loses provenance. Add explicit round-trip unit tests per repo, including a test that deserializes a legacy record (no `source_*` attributes) and returns empty strings without error. Also add a new `find_by_source(user_id, session_id, tool_call_id)` method on `TipRepository` and `CollabRepository` (DynamoDB query on user_id with FilterExpression on source_session_id + source_tool_call_id). `UserIdeaRepository` reuses its existing `list(user_id)` + in-memory filter. |
| 3 | `backend/api/sessions.py:54` | After loading the transcript, compute `active_preview` via a new helper. Include in the response. |
| 4 | `backend/api/sessions.py` (new helper) | `_compute_active_preview(user_id, session_id, transcript, repos)` — scan transcript reverse for latest `prepare_*` tool_call, check target repo for existence by `(source_session_id, source_tool_call_id)`. Return the preview dict or None. |
| 5 | `backend/agent/executor.py:828-890` | Add `tool_call_id` to the `tip_ready` / `idea_ready` / `collab_ready` WS event payloads. |
| 6 | `backend/api/tips.py:278`, `backend/api/user_ideas.py`, `backend/api/collabs.py` | Accept `source_session_id` and `source_tool_call_id` on the create request bodies. Persist them onto the new record. No transcript writes. |
| 7 | `frontend/src/api/types.ts`, `websocket.ts`, `sessions.ts` | Add `tool_call_id` to WS event shapes. Add `active_preview` to the session-load response shape. |
| 8 | `frontend/src/state/SessionContext.tsx` | (a) Thread `active_preview` through `SELECT_SESSION` action and reducer. (b) Store `tool_call_id` in `tipReady` / `ideaReady` / `collabReady` state. (c) Add session-id filter to `tip_ready` / `idea_ready` / `collab_ready` dispatch handlers. |
| 9 | `frontend/src/components/TipPreviewCard.tsx`, `IdeaPreviewCard.tsx`, `CollabPreviewCard.tsx` | Read `tool_call_id` from `initial`, pass it + `session_id` into the create API call. |
| 10 | `frontend/src/api/tips.ts`, `userIdeas.ts`, `collabs.ts` | Accept + forward the two new fields. |
| 11 | `tests/` | Backend: `_compute_active_preview` with each scenario (no prepare call, latest published, latest unpublished, superseded drafts). Repo serialization of new fields. Frontend: reducer handles `active_preview` in `SELECT_SESSION`, session-id filter enforced on `*_ready`. |

## Data flow (new steady state)

1. Agent calls `prepare_tip` in session X, turn N.
2. Backend records `tool_call` (TC1) in session X's transcript. Emits `tip_ready` WS event with `session_id=X, tool_call_id=TC1`.
3. Frontend receives `tip_ready`, passes session-id filter, `SET_TIP_READY` fires, card renders. `tipReady.tool_call_id = TC1`.
4a. **Happy path.** User clicks Publish. Frontend calls `createTip({..., source_session_id: X, source_tool_call_id: TC1})`. Backend persists the tip with those fields. Frontend dispatches `SET_TIP_PUBLISHED`, card clears.
4b. **Dropped WS event.** `tip_ready` never arrives at step 3. User eventually reloads or the WS reconnects. `SELECT_SESSION` fires, carrying `active_preview` from the reloaded session. Backend's `_compute_active_preview` sees TC1 in the transcript, checks `tips WHERE source_tool_call_id = TC1` — none found, so returns the preview. Card renders.
4c. **Reopen after publish.** User returns to session X later. `SELECT_SESSION` loads session. `_compute_active_preview` sees TC1, finds a matching tip in the tips table (published in step 4a), returns `null`. Card does not reappear.
4d. **Superseded draft.** Agent calls `prepare_tip` (TC1), then later in same session calls `prepare_tip` (TC2). Latest call is TC2. Hydration considers TC2 only. If TC2 is published, card cleared. If TC2 unpublished, card shows TC2's content. TC1 is never resurrected.

## Testing plan

### Local-first e2e

1. `./scripts/dev.sh start`.
2. Scenarios:
   * **Happy path.** Prompt the agent for a tip, see card, publish, verify card clears, verify the tip in DynamoDB has `source_session_id` and `source_tool_call_id` populated.
   * **Dropped WS event.** Kill the backend before the `tip_ready` event round-trips. Restart backend. Reconnect frontend. Confirm the card rehydrates via the `SELECT_SESSION` path.
   * **Reload after publish.** Happy path, then browser reload. Card should not reappear.
   * **Superseded draft.** Ask for a tip, then before publishing, ask the agent to prepare a different tip. The card should show the latest version. Publish it. Reload. No card.
   * **Cross-session.** Two tabs, two sessions. Prepare a tip in session A. Session B's UI should not show a card.
3. Repeat for `prepare_idea` and `prepare_collab`.

### Staging pass

Copy one or two test users to staging with `AWS_PROFILE=forge python scripts/copy-user-to-staging.py --email <user> --week 4 --include-sessions`, masquerade via the localStorage trick, repeat the happy-path and reload-after-publish scenarios.

### Unit coverage

* `_compute_active_preview` — the four scenarios named in data flow, plus an empty transcript and a transcript with only non-prepare tool_calls.
* Tip / Idea / Collab serialize/deserialize round-trip of the new fields (including missing-field legacy records).
* Frontend reducer: `SELECT_SESSION` with `active_preview` of each type, with `active_preview: null`, and when `active_preview` is absent from the response entirely (legacy backend).
* Session-id filter regression test: injecting `tip_ready` with a non-active session_id should be a no-op.

## Rollout

1. Deploy backend changes first. Old frontend clients ignore the new optional response fields; new model attributes are initialized to empty strings on existing records. Zero-impact on running traffic.
2. Deploy frontend.
3. Smoke-test staging, then production.
4. Monitor PostHog: `prepare_tip` call count vs. published tip count should tighten. Historical baseline is in the Week 4 analytics — Lian's session is the clearest signal.

## Coherence notes

* **No transcript writes from the HTTP path.** The race codex flagged is structurally eliminated, not mitigated.
* **Source-of-truth is the published record.** Published state lives where publishing actually happens. No synthetic markers, no reconciliation risk.
* **Latest-only matches existing backend semantics.** `_check_tip_prepared` already emits only the latest; `_compute_active_preview` follows the same rule. No resurrection of superseded drafts.
* **Backward compatibility is clean.** New optional fields on both response and request shapes. Old clients ignore them. Old records have empty strings and simply never match a `source_tool_call_id` lookup (which is correct — there was no lookup before this change).
* **One caveat: cross-tab publish.** If the user has two tabs open on the same session, publishes in tab A, then tab B's next `SELECT_SESSION` correctly shows no card. But if tab B is already showing the card (it was rendered before the publish), tab B won't auto-clear — no broadcast. Acceptable for now; tab B hitting Publish creates a duplicate only if the user ignores the already-visible confirmation. This existed before the fix too.

## Open items

* GSI on `source_session_id` is not required for initial ship — we rely on the existing per-user list + in-memory filter. Revisit if volumes grow.
* Proper fix for the cross-session `intake_complete` cosmetic glitch is to reconcile `intakeComplete` from `profile.intake_completed_at` on session load. Out of scope for Tuesday.
* Cross-tab publish broadcast (noted below) is accepted as-is for now.
