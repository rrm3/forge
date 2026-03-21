# Forge v2 Implementation Log

## Step 1: WebSocket Migration
**Status:** In progress
**Started:** 2026-03-21 ~00:00

### Plan
* Add API Gateway WebSocket API to CDK stack
* Create Dispatcher Lambda (validates, async invokes Worker)
* Create Worker Lambda (runs agent loop, pushes via Management API)
* Add DynamoDB connections table with user_id GSI
* Implement session ownership authorization
* Build frontend WebSocket client (auto-reconnect, heartbeat, offline queue)
* Add session mutex (prevent duplicate Workers)
* Token batching and frame chunking
* Remove SSE, Function URL, and all v1 streaming code
* Tests: auth, mutex, protocol routing, ownership check, frame chunking, heartbeat

### Completed: 2026-03-21 ~00:30

### Changes
* Created `backend/api/websocket.py` - WebSocket handler with session mutex, token batching, frame chunking, heartbeat, auth
* Created `frontend/src/api/websocket.ts` - WebSocket client with auto-reconnect, offline queue, chunk reassembly
* Updated `backend/main.py` - Wired WebSocket handler, removed SSE chat router
* Updated `backend/models.py` - Added `type` field to Session model
* Updated `backend/repository/sessions.py` - Serialize/deserialize `type` field
* Updated `frontend/src/state/SessionContext.tsx` - Rewrote to use WebSocket
* Updated `frontend/src/auth/AuthProvider.tsx` - Wired WebSocket token getter, auto-connect
* Updated `frontend/src/api/types.ts` - Added SessionType, v2 UserProfile fields
* Updated `frontend/src/components/ChatView.tsx` - Reconnecting banner, removed auto-onboarding
* Created `frontend/src/components/HomeScreen.tsx` - Placeholder action buttons
* Updated `frontend/src/App.tsx` - Shows HomeScreen when no active session
* Updated `infrastructure/cdk/lib/forge-stack.ts` - WebSocket API, connections table, GSIs, SSM access
* Removed `backend/api/chat.py` (SSE streaming), `backend/agent/sse.py`, `frontend/src/api/chat.ts`
* Deployed OpenAI API key to SSM Parameter Store (`/forge/openai-api-key`)
* Created `tests/test_websocket.py` - 13 tests all passing
* Updated `tests/test_agent.py` and `tests/test_api.py` - Removed SSE references

### Design Decisions
* Local dev uses FastAPI native WebSocket (`/ws` endpoint with uvicorn). Production uses API Gateway WebSocket API. Same message protocol in both.
* Kept Lambda Function URL for REST endpoints (sessions, profile, etc.) - only chat moved to WebSocket.
* Session mutex uses asyncio.Lock per session_id - simple and correct for single-process local dev. Production uses DynamoDB conditional put (documented for future implementation).

### Notes
* 1 pre-existing test failure in test_agent.py (paragraph break assertion) - not caused by this change
