# Forge v2 Implementation Log

## Summary
All 9 implementation steps completed. 60 new/updated tests passing.

## Step 1: WebSocket Migration
**Completed:** 2026-03-21 ~00:30

* Created `backend/api/websocket.py` - WebSocket handler with session mutex, token batching, frame chunking, heartbeat, auth
* Created `frontend/src/api/websocket.ts` - WebSocket client with auto-reconnect, offline queue, chunk reassembly
* Updated `backend/main.py` - Wired WebSocket handler, removed SSE chat router
* Updated `backend/models.py` - Added `type` field to Session model
* Updated `backend/repository/sessions.py` - Serialize/deserialize `type` field
* Updated `frontend/src/state/SessionContext.tsx` - Rewrote to use WebSocket
* Updated `frontend/src/auth/AuthProvider.tsx` - Wired WebSocket token getter, auto-connect
* Updated `frontend/src/api/types.ts` - Added SessionType, v2 UserProfile fields
* Updated `frontend/src/components/ChatView.tsx` - Reconnecting banner
* Created `frontend/src/components/HomeScreen.tsx` - Action buttons
* Updated `frontend/src/App.tsx` - Shows HomeScreen when no active session
* Updated `infrastructure/cdk/lib/forge-stack.ts` - WebSocket API, connections table, GSIs, SSM access
* Removed `backend/api/chat.py`, `backend/agent/sse.py`, `frontend/src/api/chat.ts`
* Deployed OpenAI API key to SSM Parameter Store (`/forge/openai-api-key`)
* 13 tests passing

## Step 2: Session Tagging
**Completed:** 2026-03-21 (bundled with Step 1)

Session type field (`chat|tip|stuck|brainstorm|wrapup|intake`) implemented as part of the WebSocket migration. Type-created_at GSI added to CDK stack.

## Step 3: Session-Type Prompts
**Completed:** 2026-03-21 ~00:45

* Created `skills/tip.md`, `skills/stuck.md`, `skills/brainstorm.md`, `skills/wrapup.md`
* Removed v1 skills: `onboarding.md`, `tuesday_checkin.md`, `end_of_day.md`, `journaling.md`
* 8 tests passing

## Step 4: Action Buttons + UI Chrome
**Completed:** 2026-03-21 ~01:00

* Migrated to Satoshi font (from Inter), full DESIGN.md color palette
* Action buttons with Lucide icons (Lightbulb, Compass, Star, Sunrise)
* Context-aware greeting (day-sensitive, session-count-aware)
* Session list with weekly grouping, collapsible sections, search bar, type icons
* Reconnection banner with ARIA live regions
* lucide-react added as dependency
* Removed v1 skill auto-detection

## Step 5: Department Resources
**Completed:** 2026-03-21 ~01:10

* Created 7 department resource files (global, technology, marketing, product, sales, people, finance)
* Created indexing script `scripts/index_department_resources.py`

## Step 6: Search Migration
**Completed:** 2026-03-21 ~01:20

* Created `backend/lance/federated.py` - Multi-table search with deduplication and name boosting
* Created `backend/tools/search.py` - General search tool replacing search_curriculum
* Updated system prompt for federated search guidance
* Removed `backend/tools/curriculum.py`

## Step 7: Profile Schema Expansion
**Completed:** 2026-03-21 ~01:30

* Added AIProficiency model (5 dimensions, 1-5 scale)
* Added 9 new profile fields: products, daily_tasks, core_skills, learning_goals, ai_tools_used, ai_superpower, ai_proficiency, intake_summary, intake_completed_at
* Updated DynamoDB serialization for nested objects and nullable datetimes
* Updated update_profile tool to accept all new fields
* 5 tests passing

## Step 8: Voice Mode
**Completed:** 2026-03-21 ~01:45

* Created `backend/voice.py` - OpenAI Realtime API ephemeral token generation
* Implemented voice_session, tool_call, and transcript WebSocket handlers
* Created `VoiceOrb.tsx` - Canvas-based multi-color animation with audio reactivity
* Created `VoiceMode.tsx` - Full voice session management with tool relay
* Added mic toggle to ChatView
* 7 tests passing

## Step 9: Intake
**Completed:** 2026-03-21 ~02:00

* Created `skills/intake.md` - 6-phase conversational intake prompt
* Created `backend/tools/analyze.py` - analyze_and_advise tool for Claude Opus routing
* Created `IntakeView.tsx` - Full-screen focused intake layout
* App.tsx checks intake_completed_at to gate access
* 10 tests passing

## Design Decisions Made Without Input

1. **Local dev WebSocket**: Used FastAPI native WebSocket (uvicorn) rather than spinning up a local API Gateway emulator. Same message protocol in both modes.
2. **Session mutex**: Used asyncio.Lock per session_id for local dev. Production should use DynamoDB conditional put (documented but not yet implemented).
3. **Token batching**: Fixed 50ms interval rather than adaptive. Simple and effective for typical typing speeds.
4. **Voice WebSocket protocol**: Used native WebSocket connection to OpenAI Realtime API rather than WebRTC, matching the current OpenAI API capabilities.
5. **Intake gate**: Checks `intake_completed_at` on the profile rather than `onboarding_complete`. The v1 `onboarding_complete` field is still set for backward compatibility.
6. **analyze_and_advise model selection**: Attempts to use Opus by string replacement on the model name. Falls back to the configured model if Opus isn't available.
7. **Department resource content**: Wrote initial content for 7 departments. These are starting points - department leads should review and customize.

## Known Issues

1. **Pre-existing test failure**: `test_tool_call_and_response` in test_agent.py fails due to paragraph break assertion (`\n\nGot it!` vs `Got it!`). Pre-existing, not caused by v2 changes.
2. **WebSocket in production**: The API Gateway WebSocket API is defined in CDK but the Lambda handler doesn't yet have the API Gateway event format routing (it uses FastAPI WebSocket for local dev). Production deployment will need a Lambda handler adapter.
3. **OpenAI Realtime API**: The WebSocket protocol for connecting to OpenAI Realtime may need adjustment based on the actual API version available at deployment time.

## Test Summary
* test_websocket.py: 13 passed
* test_prompts.py: 8 passed
* test_profile_schema.py: 5 passed
* test_voice.py: 7 passed
* test_intake.py: 10 passed
* test_agent.py: 17 passed (1 pre-existing failure)
* **Total: 60 passed, 1 pre-existing failure**
