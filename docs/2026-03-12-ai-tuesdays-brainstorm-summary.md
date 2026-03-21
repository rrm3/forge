# AI Tuesdays - Brainstorm Summary

## Context

Digital Science runs "Forge," an initiative giving staff all day Tuesday for AI upskilling. AI Tuesdays is a chat application that serves as a collaborative AI partner in that process. It helps employees figure out how to incorporate AI into their work based on their role, skill level, and goals. It also captures learnings and builds organizational knowledge over time.

## Key Decisions

**Architecture:**
* Lambda Web Adapter + Function URLs running FastAPI (not Fargate). Scale-to-zero makes sense given the Tuesday-heavy usage pattern.
* SSE streaming over HTTP (not WebSockets). Simpler, no persistent connections needed, works with Lambda. Mid-stream cancellation handled by a separate POST /cancel endpoint.
* React + Vite + Tailwind for the frontend (confirmed via Gemini research as the best fit given existing React expertise, ecosystem maturity, and Cognito library support). SvelteKit, Vue, Next.js, and HTMX were evaluated and rejected.
* OIDC via Digital Science ID (ds-identity). PKCE flow in frontend, JWT verification directly in the FastAPI backend. Originally planned as a Cognito App Client, migrated to ds-identity's custom OIDC server.

**Data stores:**
* DynamoDB for session index (metadata/pointers), user profiles, and journal entries
* S3 for full session transcripts (JSON), per-user memory files, curriculum documents, and LanceDB tables
* LanceDB on S3 for curriculum/RAG search (populated by a separate process)

**LLM:**
* Single model (Claude) via LiteLLM. No model selection UI.
* Own agentic ReAct loop with tool calling. Stateless across sessions except for memory loaded at runtime.

## Tools (Phase 1)

* **search_curriculum** - RAG search over LanceDB curriculum index
* **retrieve_document** - Full file retrieval from S3
* **read_profile / update_profile** - User profile CRUD in DynamoDB
* **save_journal / read_journal** - Learning log entries in DynamoDB

## Skills (Phase 1)

* **Onboarding** - First login: validate org data, assess AI skill level, search curriculum for role-appropriate starting points, suggest a plan for their first Tuesday
* **Tuesday Morning Check-in** - Review last week's journal and progress, suggest focus areas from curriculum
* **End-of-Day Wrap-up** - Summarize session or accept manual input about external tool usage, generate journal entry
* **General Journaling** - Available any time for capturing learnings, tips, reflections

## User Profiles

Pre-populated from DS org data (name, title, department, manager, direct reports, team). Refined by the user during onboarding. Includes AI experience level, interests, tools used, and goals. First session walks users through validating their profile and then uses it to recommend curriculum.

## Memory

Per-user memory extracted periodically from session transcripts into a markdown file on S3. Loaded into system prompt at runtime. Captures implicit knowledge (preferences, skill progression, recurring topics) distinct from the structured profile and explicit journal entries.

## Phase 2 (Future)

* Cross-user profile search ("who has expertise in X?") via a separate LanceDB index
* Ideas Exchange for proposing projects, matching skills to people, forming teams
* User-facing progress/stats view
* Admin dashboard for aggregate analytics and curriculum optimization

## Build Strategy

Start fresh in a new repo rather than forking Acumentum. Reference Acumentum's implementation patterns (LiteLLM wiring, streaming, ReAct loop, session management) but keep the codebase independent and simpler.

## Open Items

* Transcript write strategy (after each response vs. session end)
* Skill triggering (agent decides from context vs. hardcoded routing)
* Profile pre-population batch import process (out of scope but needs to happen before launch)
* ~~Infrastructure as Terraform or CDK~~ (resolved: using AWS CDK)
