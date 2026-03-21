# AI Tuesdays - Design Document

**Project location:** `/Users/rmcgrath/dev/forge`
**Reference codebase:** `/Users/rmcgrath/dev/acumentum`

## Mission

AI Tuesdays is an internal Digital Science application supporting the "Forge" initiative, where staff dedicate Tuesdays to AI upskilling. The app serves as a collaborative AI partner that helps employees figure out how to incorporate AI into their daily work based on their role, skill level, and responsibilities.

Users open the app on Tuesday mornings. It greets them with context about who they are (pre-populated from org data and refined over time), suggests curriculum based on their role and progress, brainstorms approaches with them, and captures what they learn throughout the day. The app is available any day of the week for general AI-assisted work, journaling, and brainstorming.

The captured data serves two purposes: helping individuals progress week-over-week, and providing organizational-level insights to optimize curriculum and share best practices across Digital Science.

## Architecture

```
                    ┌─────────────────────────┐
                    │   S3 / CloudFront        │
                    │   (React SPA)            │
                    └────────┬────────────────┘
                             │ HTTPS
                             ▼
                    ┌─────────────────────────┐
                    │   Lambda Function URL    │
                    │   (streaming enabled)    │
                    └────────┬────────────────┘
                             │
                    ┌────────▼────────────────┐
                    │   Lambda Web Adapter     │
                    │   + FastAPI              │
                    │                          │
                    │  POST /chat   (SSE)      │
                    │  POST /cancel            │
                    │  GET  /sessions          │
                    │  GET  /sessions/:id      │
                    │  DELETE /sessions/:id    │
                    │  GET  /profile           │
                    │  PUT  /profile           │
                    │  GET  /health            │
                    └──┬──────┬──────┬────────┘
                       │      │      │
              ┌────────┘      │      └────────┐
              ▼               ▼               ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │  DynamoDB     │ │  S3          │ │  LanceDB     │
     │              │ │              │ │  (on S3)     │
     │ - Sessions   │ │ - Transcripts│ │              │
     │   (index)    │ │ - Memory     │ │ - Curriculum │
     │ - Profiles   │ │ - Curriculum │ │ - Profiles   │
     │ - Journal    │ │   files      │ │   (search)   │
     │   entries    │ │ - Journal    │ │              │
     └──────────────┘ └──────────────┘ └──────────────┘
```

### Stack

* **Frontend:** React + Vite + Tailwind CSS (SPA deployed to S3/CloudFront)
* **Backend:** Python FastAPI running inside AWS Lambda via Lambda Web Adapter + Function URLs
* **Streaming:** Server-Sent Events (SSE) over HTTP
* **Auth:** OIDC via Digital Science ID (ds-identity), PKCE flow in frontend, JWT verification in backend
* **LLM:** Claude via AWS Bedrock, wrapped by LiteLLM (single model, no model selection)
* **Embeddings:** Cohere Embed v3 via AWS Bedrock (1024-dim vectors)
* **Reranking:** Cohere Rerank v3 via AWS Bedrock
* **Storage:** DynamoDB (session index, user profiles, journal entries) + S3 (transcripts, memory files, curriculum documents, LanceDB tables)

### Why these choices

* **Lambda Web Adapter over Fargate:** Scale-to-zero economics. 500 users, mostly active on Tuesdays. Fargate would idle 6 days a week. Lambda scales naturally for the Tuesday spike pattern.
* **SSE over WebSockets:** Unidirectional streaming is sufficient. No need for bidirectional communication. SSE works through standard HTTP infrastructure, is trivial to implement, and keeps Lambda as an option (WebSockets would require persistent connections).
* **Function URLs over API Gateway:** Native response streaming support without API Gateway's chunked encoding quirks. Simpler, cheaper.
* **LanceDB on S3:** Serverless vector search, no infrastructure to manage. Supports hybrid search (FTS + vector) with reranking.

## Embedding & Search Pipeline

Ported from Acumentum's LanceDB pipeline. Content goes through: chunking, embedding, storage, then hybrid search with reranking at query time.

### Chunking

Markdown-aware chunking that preserves document structure (from `acumentum/backend/indexer/chunking.py`):

* Default chunk size: 2000 chars with 200-char overlap
* Preserves heading hierarchy (heading_path tracks enclosing headings)
* Keeps atomic units intact: code blocks, tables, prose sentences
* Base64 images excluded from length calculations

```python
chunk_markdown(text, chunk_size=2000, overlap=200) -> list[Chunk]

@dataclass
class Chunk:
    text: str
    heading_path: list[str]
    start_line: int
    end_line: int
    chunk_index: int
```

### Embedding Generation

Cohere Embed v3 via AWS Bedrock (from `acumentum/backend/indexer/embeddings.py`):

* Model: `cohere.embed-english-v3` (Bedrock)
* Dimension: 1024 float32
* `input_type="search_document"` for indexing, `"search_query"` for queries
* Batch size: up to 96 texts per call
* Strips base64 image references before embedding

```python
async def generate_embedding(text, input_type="search_document") -> list[float]
async def generate_embeddings_batch(texts, input_type="search_document", batch_size=96) -> list[list[float]]
```

### LanceDB Schema

For curriculum content:

```python
CURRICULUM_SCHEMA = {
    "id": string,           # UUID
    "document_key": string,  # S3 key, used for upsert
    "filename": string,
    "category": string,      # e.g. "marketing", "engineering", "general"
    "difficulty": string,    # "beginner", "intermediate", "advanced"
    "chunk_index": int32,
    "content": string,       # Chunk text
    "heading_path": string,  # JSON array of headings
    "metadata": string,      # JSON blob
    "created_at": timestamp,
    "vector": vector(1024),
}
```

For profile search (cross-user):

```python
PROFILES_SCHEMA = {
    "id": string,
    "user_id": string,       # Document ID for upsert
    "name": string,
    "title": string,
    "department": string,
    "content": string,       # Full-text profile summary for search
    "metadata": string,
    "created_at": timestamp,
    "vector": vector(1024),
}
```

### Indexing Pipeline

Content ingestion flow (adapted from `acumentum/backend/lance/indexing.py`):

1. Accept content (markdown, extracted PDF text, etc.)
2. Chunk via `chunk_markdown()`
3. Generate embeddings via `generate_embeddings_batch()`
4. Build rows with schema fields + vector
5. Upsert: delete existing rows by document_key, insert new rows
6. Create FTS index on `content` column for hybrid search

Curriculum population is a separate process (CLI script or scheduled Lambda) that:
1. Scans S3 curriculum folder for new/updated documents
2. Extracts text (markdown pass-through, PDF via pymupdf4llm)
3. Indexes each document into the curriculum LanceDB table

### Search Pipeline

Hybrid search with reranking (adapted from `acumentum/backend/lance/search.py`):

1. Embed query with `input_type="search_query"`
2. Execute hybrid search: FTS keyword matching + vector similarity, combined via RRF (Reciprocal Rank Fusion)
3. Rerank top results via Cohere Rerank v3 (`cohere.rerank-v3-5:0` on Bedrock)
4. Apply relevance filtering: min_score threshold + score gap detection (cut at >40% drop)
5. Return ranked results with content snippets and metadata

```python
async def search(
    query: str,
    collection: str,
    limit: int = 20,
    filter_expr: str | None = None,
    rerank: bool = True,
    min_score: float = 0.1,
) -> dict  # {results: [...], error: str | None}
```

### LanceDB Storage Layout

```
s3://{bucket}/lance/curriculum/     # Curriculum content index
s3://{bucket}/lance/profiles/       # Cross-user profile search index
```

## Tools

Tools are functions available to the agentic loop on every turn. They are stateless and operate on specific data stores.

### search_curriculum

Search the curriculum LanceDB index for relevant materials based on a query. Returns ranked snippets with source document references.

* **Data:** LanceDB curriculum table on S3
* **Input:** query string, optional filters (category, difficulty)
* **Output:** ranked results with text snippets, scores, and S3 document keys

### retrieve_document

Fetch the full content of a curriculum document or resource from S3 when the agent needs more than a snippet.

* **Data:** S3 bucket with curriculum files (markdown, PDF text extracts)
* **Input:** S3 key (from search_curriculum results)
* **Output:** full document text

### search_profiles

Search across all user profiles to find people with specific expertise, roles, or interests. Uses the profiles LanceDB index.

* **Data:** LanceDB profiles table on S3
* **Input:** query string (e.g. "machine learning expertise", "finance team")
* **Output:** ranked list of matching profiles with name, title, department, relevance score

### read_profile

Read the current user's profile from DynamoDB. Includes org data (pre-populated) and user-refined information (skills, interests, AI experience level).

* **Data:** DynamoDB profiles table, keyed by OIDC subject ID
* **Input:** none (current user from auth context)
* **Output:** profile JSON

### update_profile

Write updates to the current user's profile. Used during onboarding and whenever the user shares new information about their role or skills. Also re-indexes the profile into LanceDB for cross-user search.

* **Data:** DynamoDB profiles table + LanceDB profiles index
* **Input:** fields to update (partial update)
* **Output:** confirmation

### save_journal

Write a journal/learning log entry. Captures what the user learned, tools they used, tips, reflections. Can be auto-generated from session context or manually dictated.

* **Data:** DynamoDB journal table (PK: user_id, SK: timestamp) + optionally S3 for longer entries
* **Input:** entry text, optional tags/categories, optional date override
* **Output:** confirmation with entry ID

### read_journal

Retrieve past journal entries for the current user. Used by the agent to understand progress and avoid repeating suggestions.

* **Data:** DynamoDB journal table
* **Input:** optional date range, optional limit
* **Output:** list of journal entries

### propose_idea

Submit a project idea or opportunity to the Ideas Exchange. The agent helps structure the proposal with a summary, required skills, and potential team members (via profile search).

* **Data:** DynamoDB ideas table (PK: idea_id)
* **Input:** title, description, required_skills, proposed_by (current user)
* **Output:** confirmation with idea ID

### list_ideas

Browse and search the Ideas Exchange for project proposals. Users can find ideas that match their skills or interests.

* **Data:** DynamoDB ideas table
* **Input:** optional search query, optional skill filter
* **Output:** list of ideas with summaries and proposer info

## Skills

Skills are higher-level orchestration recipes defined as markdown files. They combine system prompt instructions with tool usage patterns. The agent selects them based on context or the user can request them.

### Onboarding (first login)

Triggered when a user has no prior sessions or their profile is incomplete.

1. Greet the user, show their pre-populated org data (name, title, manager, team)
2. Ask them to validate and refine (correct title, add context about what they actually do)
3. Assess AI experience level through conversation (novice / intermediate / advanced)
4. Search curriculum for role-appropriate starting materials
5. Suggest a plan for their first Tuesday based on skill level and role
6. Save the refined profile

### Tuesday Morning Check-in

Triggered on Tuesdays for returning users.

1. Read the user's profile and recent journal entries
2. Summarize last week's progress and learnings
3. Search curriculum for next-level materials based on where they left off
4. Suggest focus areas for today
5. Ask if they have specific goals or questions for the day

### End-of-Day Wrap-up

Available any day, suggested on Tuesday evenings.

1. If the user chatted throughout the day: summarize key learnings from session history
2. If the user worked externally: prompt them to describe what they did, what tools they used, what they learned
3. Generate a journal entry (editable by the user before saving)
4. Highlight tips or insights worth sharing with the broader org
5. Save journal entry

### General Journaling

Available any time. User can dictate learnings, tips, reflections, and the agent structures and saves them as journal entries.

## User Memory

Per-user memory extracted from session transcripts, stored as a markdown file on S3 (`memory/{user_id}/memory.md`). Loaded into the system prompt at the start of each session.

Extraction runs periodically (could be a scheduled Lambda): reads recent session transcripts, pulls out durable facts about the user (preferences, skill progression, recurring topics, stated goals), and appends to the memory file. Similar pattern to OpenClaw's memory consolidation.

This is distinct from the user profile (structured org data) and the journal (explicit learning logs). Memory captures implicit knowledge from conversation patterns.

## User Profile Schema

Stored in DynamoDB. Pre-populated from DS org data, refined by the user through the onboarding skill.

```json
{
  "user_id": "oidc-sub-uuid",
  "email": "jane.smith@digital-science.com",
  "name": "Jane Smith",
  "title": "Senior Product Manager",
  "department": "Dimensions",
  "manager": "John Doe",
  "direct_reports": ["Alice", "Bob"],
  "team": "Discovery Platform",
  "ai_experience_level": "intermediate",
  "interests": ["product analytics", "customer research automation"],
  "tools_used": ["ChatGPT", "Claude"],
  "goals": ["Automate weekly reporting", "Use AI for user research synthesis"],
  "onboarding_complete": true,
  "created_at": "2026-03-12T00:00:00Z",
  "updated_at": "2026-03-18T10:30:00Z"
}
```

## Ideas Exchange Schema

DynamoDB table for project proposals and opportunities.

```json
{
  "idea_id": "uuid",
  "title": "AI-powered quarterly report generation",
  "description": "Automate the creation of quarterly business reports...",
  "required_skills": ["data analysis", "Python", "report writing"],
  "proposed_by": "oidc-sub-uuid",
  "proposed_by_name": "Jane Smith",
  "status": "open",
  "interested_users": ["user-id-1", "user-id-2"],
  "created_at": "2026-03-18T10:30:00Z"
}
```

## Session Persistence

* **DynamoDB sessions table:** PK=user_id, SK=session_id. Stores metadata: title, created_at, updated_at, message_count, summary.
* **S3 transcripts:** Full message history as JSON at `sessions/{user_id}/{session_id}.json`. Written after each assistant response (append-friendly).
* **Concurrent access:** DynamoDB conditional writes on the session metadata prevent overwrites if a user is logged in on two devices. Transcript writes use session_id + message sequence number to avoid conflicts.

## API Surface

```
POST   /api/chat              SSE stream; body: {session_id, message}
POST   /api/chat/cancel       Cancel a running stream
GET    /api/sessions          List user's sessions
POST   /api/sessions          Create new session
GET    /api/sessions/:id      Get session with transcript
DELETE /api/sessions/:id      Delete session
PATCH  /api/sessions/:id      Rename session
GET    /api/profile           Get current user's profile
PUT    /api/profile           Update profile fields
GET    /api/journal            List journal entries
GET    /api/ideas              List ideas
GET    /api/health            Health check
```

Auth: all endpoints require `Authorization: Bearer <id-token>` header. Backend validates JWT signature against the OIDC provider's JWKS endpoint (Digital Science ID).

## Frontend

Minimal React SPA with two panels:

* **Left sidebar:** Session list (title, date, message count). New session button. User avatar/menu at bottom.
* **Right panel:** Chat view with message bubbles, markdown rendering, streaming text display. Input box at bottom.
* **No:** file uploads, model selector, code execution UI.

State management: React context + useReducer for session state initially. Zustand if complexity grows.

## Infrastructure

AWS CDK (TypeScript) at `infrastructure/cdk/`:
* Lambda function with Web Adapter layer
* Function URL with streaming enabled
* DynamoDB tables (sessions, profiles, journal, ideas)
* S3 bucket (transcripts, memory, curriculum, LanceDB)
* CloudFront distribution for frontend SPA
* OIDC client registered with Digital Science ID (ds-identity)
* IAM roles for Lambda (DynamoDB, S3, Bedrock access for LLM + embeddings + reranking)

## What We're Not Building

* File upload/management UI
* Code execution sandbox
* Multiple model support
* iOS or mobile app
* Recorder/meeting features
* Modal integration
* Real-time collaboration
* WebSocket infrastructure

## Acumentum Code to Reference

Key modules from the Acumentum codebase to adapt for this project:

| **Capability** | **Acumentum source** |
|---|---|
| Markdown chunking | `backend/indexer/chunking.py` |
| Cohere embeddings (Bedrock) | `backend/indexer/embeddings.py` |
| Text extraction (PDF, DOCX, etc.) | `backend/indexer/text_extraction.py` |
| LanceDB connection/caching | `backend/lance/connection.py` |
| LanceDB schemas (PyArrow) | `backend/lance/schemas.py` |
| Document indexing (chunk + embed + store) | `backend/lance/indexing.py` |
| Hybrid search + reranking | `backend/lance/search.py` |
| Cohere reranking (Bedrock) | `backend/lance/reranking.py` |
| Collection management | `backend/lance/collections.py` |
| LLM calls via LiteLLM | `backend/llm.py` |
| ReAct agentic loop | `backend/agent/loop.py` |
| System prompt / context building | `backend/agent/context.py` |
| Session models | `backend/models.py` |
| JWT auth verification | `backend/auth.py` |
| Chat UI components | `frontend/src/components/ChatView.tsx` |
| Session list | `frontend/src/components/SessionList.tsx` |
| SSE/streaming hooks | `frontend/src/hooks/useChat.ts` |
| Auth (OIDC / ds-identity) | `frontend/src/auth/oidc.ts`, `AuthProvider.tsx` |
