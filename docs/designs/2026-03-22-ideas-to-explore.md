# Ideas to Explore

## Problem

Users surface AI opportunities through intake conversations, brainstorming sessions, and general chats, but these ideas evaporate once the session ends. There's no persistent, personal space to collect and revisit them. The journal captures free-form notes, and the Ideas Exchange is shared/public - neither serves as a personal ideas backlog.

## Design

### Data Model

`UserIdea` - personal to each user, separate from the shared Ideas Exchange.

```
user_id: str          (PK - owner)
idea_id: str          (SK - UUID)
title: str            (short name, max 200 chars)
description: str      (markdown content, refined over time, max 10000 chars)
source: str           (where it came from: "intake", "brainstorm", "chat", "manual")
source_session_id: str (session that created it, nullable)
linked_sessions: list[str]  (session_ids that have touched this idea)
tags: list[str]
status: str           ("new" | "exploring" | "done", default "new")
created_at: datetime
updated_at: datetime
```

**Storage:** DynamoDB table `{prefix}-user-ideas` with PK=`user_id`, SK=`idea_id`. Scan by user, sort in Python. Memory repo with JSON persistence for dev.

### Sidebar

```
┌─────────────────────────┐
│ 🏠 Home                 │
├─────────────────────────┤
│ 💡 Ideas (3)            │  ← lightbulb icon, count badge
├─────────────────────────┤
│  v This Week         2  │
│  💬 Brainstorm session  │
│  📋 Getting Started     │
│                         │
├─────────────────────────┤
│  🔍  +                  │
└─────────────────────────┘
```

- "Ideas" sits between Home and the session list
- Count badge shows total ideas
- Clicking shows the Ideas view in the content area
- All items have consistent icons (Lucide: Home, Lightbulb for Ideas, type icons for sessions)

### Ideas View

Shows when "Ideas" is clicked in the sidebar. Cards sorted by most recently updated.

Each card shows:
- Title + description preview (2-3 lines)
- Source label ("From: Getting Started" or "From: Brainstorm")
- Number of linked chats
- Tags as small pills
- "Chat" button - starts a new linked session with idea context
- Three-dot menu: edit, delete
- Status indicator (subtle: new/exploring/done)

Empty state: "No ideas yet. Start a brainstorm or share what you're curious about in any chat."

### Idea Preview Card (in ChatView)

When the AI calls `prepare_idea`, an editable preview card appears in the chat (same pattern as tip preview card):

- Editable title input
- Editable description textarea (markdown, with formatting toolbar)
- Editable tags
- "Save Idea" button + "Skip" button (or X to dismiss)
- On save: calls `POST /api/ideas` (user ideas endpoint), card transitions to confirmation
- On skip: card dismissed, nothing saved

### Chat from an Idea

Clicking "Chat" on an idea card:
1. Creates a new session of type "chat"
2. Injects idea context into the system prompt:
   ```
   ## Current Idea
   Title: {title}
   Description: {description}
   Status: {status}
   This idea was first captured during: {source}
   There have been {N} previous conversations about this idea.

   Help the user explore, refine, or make progress on this idea.
   You can call update_idea to refine the title, description, or status.
   ```
3. The session is automatically linked to the idea (`linked_sessions` updated)

### AI Integration

**How ideas get created:**
- **Intake:** Starting points from the completion card are auto-saved as ideas (source: "intake")
- **Brainstorm:** AI calls `prepare_idea` at the end of a brainstorm. Preview card shown. (source: "brainstorm")
- **Any chat:** AI can call `prepare_idea` whenever the user mentions something worth exploring (source: "chat")
- **Manual:** User clicks "+ Add idea" in the Ideas view (source: "manual")

**How ideas get updated:**
- In any idea-linked chat, the AI can call `update_idea(idea_id, fields)` to refine description, change status, add tags
- User can edit directly from the Ideas view (inline editing on cards)

**Tools:**
- `prepare_idea(title, description, tags)` - sends idea data to frontend for preview card (doesn't save)
- `update_idea(idea_id, fields)` - updates an existing idea's title/description/tags/status

### Backend

**New files:**
- `backend/models.py` - Add `UserIdea` model
- `backend/repository/user_ideas.py` - `UserIdeaRepository` (abstract + DynamoDB + Memory with JSON persistence)
- `backend/api/user_ideas.py` - REST endpoints: list (by user), get, create, update, delete
- `backend/tools/user_ideas.py` - `prepare_idea` and `update_idea` agent tools

**Modified files:**
- `backend/deps.py` - Wire user_ideas_repo
- `backend/main.py` - Include user_ideas router
- `backend/agent/executor.py` - Add user_ideas repo to ToolContext, detect `prepare_idea` calls, send `idea_ready` WS event
- `backend/api/websocket.py` - Pass user_ideas_repo through deps
- `skills/brainstorm.md` - Add step to call `prepare_idea` at end

### Frontend

**New files:**
- `frontend/src/components/IdeasView.tsx` - Ideas list with cards
- `frontend/src/components/IdeaPreviewCard.tsx` - Editable preview card (like TipPreviewCard)

**Modified files:**
- `frontend/src/api/types.ts` - Add `UserIdea` interface
- `frontend/src/api/client.ts` - Add user ideas API functions
- `frontend/src/api/websocket.ts` - Add `idea_ready` to ServerMessage
- `frontend/src/state/SessionContext.tsx` - Add `ideaReady` state + handler
- `frontend/src/components/SessionList.tsx` - Add "Ideas (N)" between Home and sessions
- `frontend/src/components/ChatView.tsx` - Render IdeaPreviewCard
- `frontend/src/App.tsx` - Add ideas view routing

### API Endpoints

- `GET /api/user-ideas` - List user's ideas (sorted by updated_at desc)
- `POST /api/user-ideas` - Create idea from frontend
- `GET /api/user-ideas/{idea_id}` - Get single idea
- `PUT /api/user-ideas/{idea_id}` - Update idea (title, description, tags, status)
- `DELETE /api/user-ideas/{idea_id}` - Delete idea
- `POST /api/user-ideas/{idea_id}/link-session` - Link a session to an idea

### Implementation Order

1. `UserIdea` model
2. `user_ideas` repository (Memory + DynamoDB)
3. REST API endpoints
4. `prepare_idea` + `update_idea` agent tools
5. Wire into deps/main/executor/websocket
6. Frontend types + API client
7. SessionContext state for `idea_ready`
8. IdeaPreviewCard component
9. IdeasView component
10. SessionList sidebar integration ("Ideas (N)")
11. App.tsx routing
12. Update brainstorm skill to call `prepare_idea`
13. ChatView integration (preview card + idea-linked sessions)
