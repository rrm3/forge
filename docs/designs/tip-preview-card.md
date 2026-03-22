# Tip Preview Card - Design Spec

## Problem
The current tip flow has the AI call `publish_tip` immediately without letting the user preview or edit the tip before it goes live. Users should be able to review, edit, and approve before publishing.

## Proposed Flow

1. AI refines the tip through conversation (unchanged)
2. AI calls a new tool `prepare_tip` (instead of `publish_tip`) that sends tip data to the frontend
3. Frontend renders an **editable preview card** in the chat:
   - Title (editable text input)
   - Content (editable textarea with basic markdown support - bold, italic, lists)
   - Rendered preview below the editor (live markdown preview)
   - Tags (editable, add/remove pills)
   - Department selector dropdown (default to user's dept, "Everyone" option)
   - "Publish" button + "Edit" toggle
4. User can edit any field, then clicks "Publish"
5. Frontend calls `POST /api/tips` directly (new endpoint) to create the tip
6. Card updates to show "Tip Published!" confirmation

## Implementation

### Backend changes
- Rename `publish_tip` tool to `prepare_tip` - same schema but instead of saving to the repo, it just returns the structured data
- Add `POST /api/tips` endpoint that creates a tip directly (currently tips are only created via the agent tool)
- The executor detects `prepare_tip` tool call and sends a `tip_ready` WebSocket message (instead of `tip_published`)

### Frontend changes
- New `TipPreviewCard` component with:
  - Editable title input
  - Markdown textarea (basic formatting toolbar: bold, italic, list)
  - Live markdown preview (using existing react-markdown)
  - Tags editor (click to remove, input to add)
  - Department dropdown
  - Publish button
- `ChatView` renders `TipPreviewCard` when `tipReady` state is set
- On publish: calls `POST /api/tips`, then transitions card to confirmation state

### Skill update
- `skills/tip.md`: Change step 6 from "Call publish_tip" to "Call prepare_tip to let the user review before publishing"
- Remove the instruction to call `save_journal` (the frontend publish action can handle both)

## Markdown editing
Keep it minimal - a textarea with a small toolbar above it:
- **B** (bold) - wraps selection in `**`
- *I* (italic) - wraps selection in `*`
- List icon - adds `- ` prefix to line
- The preview shows rendered markdown below

No need for a full rich text editor. Raw markdown in the textarea, rendered preview below.
