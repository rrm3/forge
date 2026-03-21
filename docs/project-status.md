# Forge - Project Status

*Last updated: 2026-03-21*

## Architecture (v2)

* **Text chat:** WebSocket via API Gateway WebSocket API (production) or FastAPI native WebSocket (local dev). Dispatcher-Worker Lambda pattern for long-running agent loops.
* **Voice:** OpenAI Realtime API (GPT-4o) via client-direct ephemeral token pattern. Audio never touches AWS. Backend creates server-configured sessions with system prompts injected server-side.
* **Session types:** Tagged sessions (chat, tip, stuck, brainstorm, wrapup, intake) with type-specific prompts driving each conversation.
* **Search:** Federated multi-table search across department resources, Gong, Dovetail, roadmap, and Klue battlecards. Hybrid FTS + vector with Cohere reranking.
* **Intake:** Deep 6-phase conversational assessment blocking all features until complete. AI-inferred proficiency scoring (5 dimensions, 1-5 scale). Voice-compatible with analyze_and_advise tool routing to Claude Opus.

## Implementation Status

### Complete

* **WebSocket chat** - API Gateway WebSocket API with Dispatcher-Worker Lambda pattern. Session mutex via DynamoDB conditional put. Token batching (50ms), frame chunking (128KB), heartbeat, auto-reconnect with offline queue.
* **Session types** - 6 types (chat, tip, stuck, brainstorm, wrapup, intake) with type field on Session model, DynamoDB GSI for cross-user queries.
* **Session-type prompts** - Structured conversation flows for tip, stuck, brainstorm, wrapup, and intake. Tone guidance and tool integration.
* **Action buttons + UI** - Satoshi font, slate palette, Lucide icons. Context-aware greeting (day-sensitive, session-count-aware). Session list with weekly grouping, collapsible sections, search bar, type icons. Reconnection banner with ARIA live regions. 44px touch targets.
* **Department resources** - 7 department files (global, technology, marketing, product, sales, people, finance) with indexing script.
* **Federated search** - Multi-table search with content hash deduplication and parameterized name boosting. Replaces single-table curriculum search.
* **Profile schema** - 9 new fields for intake (products, daily_tasks, core_skills, learning_goals, ai_tools_used, ai_superpower, ai_proficiency, intake_summary, intake_completed_at).
* **Voice mode** - OpenAI Realtime API ephemeral token generation, server-side tool validation, frontend VoiceOrb animation, tool call relay, transcript persistence, mic permission handling, session recovery/resume.
* **Intake flow** - 6-phase conversational assessment, analyze_and_advise tool for Claude Opus routing, full-screen focused layout, auto-save, resume handling.
* **Production Lambda** - Separate WS Lambda function with raw handler (awslambdaric), DynamoDB connections table with TTL, session processing mutex, cancel flags.
* **ReAct agent loop** - Multi-iteration tool calling with streaming. Transport-agnostic via MessageSender protocol.
* **All tools** - search, retrieve_document, read/update/search_profile, save/read_journal, propose_idea, list_ideas, analyze_and_advise
* **OIDC auth** - PKCE flow in frontend, JWT verification in backend. Works for both REST and WebSocket.
* **Org chart integration** - SQLite loaded from S3 at startup. Profile enrichment on first access.
* **AWS deployment** - CDK stack with Lambda (REST + WS), DynamoDB, S3, CloudFront, API Gateway WebSocket API, SSM.
* **CI/CD** - GitHub Actions with per-environment deploys.
* **75 tests passing** - WebSocket, prompts, profile schema, voice, intake, agent, Lambda handler.

### In Progress

* **Logout flow** - ds-identity post_logout_redirect_uri not honored. Documented.
* **Bedrock model access** - Intermittent Marketplace permission errors in forge account.

### Not Yet Implemented

* **Community tips feed** - Read-only list of tips from across the org (P2, depends on session data).
* **Progress tracking** - 12-week baseline from intake scores, weekly visualization (P2).
* **Admin dashboard** - Org-wide participation and engagement metrics (P2).
* **Memory extraction** - Scheduled Lambda to extract durable facts from transcripts (P3).
* **Curriculum content** - Real AI Tuesdays content needs to be authored (department resources are the replacement for now).

## Environments

| | Production | Staging | Local Dev |
|---|---|---|---|
| **App URL** | aituesday.digitalscience.ai | aituesday-staging.digitalscience.ai | localhost:5173 |
| **Branch** | main | staging | any |
| **OIDC Provider** | id.digitalscience.ai | id.digitalscience.ai | id.digitalscience.ai |
| **OIDC Client ID** | 0bfe6d8ddb94027981248d2a0bd21991 | 40656eed824af4e6ebeaca1f99740bcc | 40656eed824af4e6ebeaca1f99740bcc (staging) |
| **AWS Account** | 887690967243 | 887690967243 | ReadCube 688951407356 (Bedrock) |
| **CDK Stack** | forge-production | forge-staging | n/a |
| **Chat transport** | API Gateway WebSocket API | API Gateway WebSocket API | FastAPI native WebSocket |
| **REST Lambda** | forge-{env}-backend (LWA + uvicorn) | forge-{env}-backend | uvicorn local |
| **WS Lambda** | forge-{env}-ws (awslambdaric) | forge-{env}-ws | n/a (uses FastAPI WS) |

## Key Accounts and Resources

* **Forge AWS account:** 887690967243
* **Bedrock (local dev):** ReadCube account 688951407356
* **ds-identity:** Account 109743758290
* **GitHub repo:** rrm3/forge
* **OpenAI API key:** SSM Parameter Store `/forge/openai-api-key`
* **Org chart source:** /Users/rmcgrath/Documents/caio/ds-twin/sources/org-chart.db (685 people)
* **Org chart on S3:** s3://forge-production-data/orgchart/org-chart.db
