"""Transport-agnostic agent session executor.

Runs the ReAct agent loop and sends results via a MessageSender.
Used by both FastAPI WebSocket (local dev) and Lambda handler (production).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from backend.agent.context import build_system_prompt
from backend.agent.events import (
    DoneEvent,
    ErrorEvent,
    TextEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from backend.agent.loop import react_loop
from backend.agent.skills import load_skill
from backend.api.transport import MessageSender
from backend.config import settings
from backend.deps import AgentDeps
from backend.llm import call_llm
from backend.models import Message, UserIdea
from backend.repository.department_config import DepartmentConfigRepository
from backend.storage import load_intake_responses, load_memory, load_transcript, save_intake_responses, save_transcript
from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

# Token batching interval (seconds)
_TOKEN_BATCH_INTERVAL = 0.05  # 50ms

# Tools whose calls/results are shown to the client (others hidden unless dev_mode)
_USER_VISIBLE_TOOLS = {"search", "retrieve_document", "search_profiles"}


async def run_agent_session(
    sender: MessageSender,
    user_id: str,
    user_email: str,
    user_name: str,
    session_id: str,
    user_message: str,
    deps: AgentDeps,
    is_new_session: bool = False,
    session_type: str = "chat",
    cancel_check: Callable[[], bool] | None = None,
    idea: UserIdea | None = None,
) -> None:
    """Run the ReAct agent loop for a session, streaming results via sender.

    Args:
        sender: Transport for pushing messages to the client.
        user_id: Authenticated user ID.
        user_email: User's email.
        user_name: User's display name.
        session_id: Session ID.
        user_message: The user's message text (empty for session-initiated).
        deps: Agent dependencies (repos, storage, tools, orgchart).
        is_new_session: Whether this is a new session (triggers title generation).
        session_type: Session type (chat, tip, stuck, brainstorm, wrapup, intake).
        cancel_check: Optional callable that returns True if the session is cancelled.
        idea: Optional UserIdea to provide context for idea-focused chat.
    """
    # Load session transcript
    transcript: list[Message] = []
    if not is_new_session:
        loaded = await load_transcript(deps.storage, user_id, session_id)
        if loaded:
            transcript = loaded

    # Load profile (auto-create on first access)
    profile = await deps.profiles_repo.get(user_id)
    if profile is None:
        from backend.models import UserProfile
        from backend.orgchart import enrich_profile_kwargs
        kwargs: dict = dict(user_id=user_id, email=user_email, name=user_name)
        if deps.orgchart and user_email:
            try:
                kwargs.update(enrich_profile_kwargs(deps.orgchart, user_email))
            except Exception:
                logger.warning("Org chart lookup failed for %s", user_email, exc_info=True)
        profile = UserProfile(**kwargs)
        await deps.profiles_repo.create(profile)

    memory = await load_memory(deps.storage, user_id)

    # Completed intake sessions behave like normal chats
    intake_is_complete = session_type == "intake" and profile and profile.intake_completed_at

    # Load department config and intake responses for intake sessions
    department_config = None
    intake_responses = {}
    if session_type == "intake" and not intake_is_complete and profile and profile.department:
        dept_config_repo = DepartmentConfigRepository(deps.storage)
        department_config = await dept_config_repo.get_department_config(
            profile.department.lower().replace(" ", "-")
        )
        intake_responses = await load_intake_responses(deps.storage, user_id)

    # Load session-type prompt
    skill_instructions = None
    if session_type and session_type != "chat":
        if session_type == "intake" and intake_is_complete:
            pass  # completed intake - no skill, behaves like chat
        else:
            skill_instructions = load_skill(session_type)

    # Build system prompt
    system_prompt = build_system_prompt(
        profile=profile,
        memory=memory,
        skill_instructions=skill_instructions,
        session_type=session_type,
        department_config=department_config,
        intake_responses=intake_responses,
        idea=idea,
    )

    # Build tool context
    context = ToolContext(
        user_id=user_id,
        session_id=session_id,
        repos={
            "sessions": deps.sessions_repo,
            "profiles": deps.profiles_repo,
            "journal": deps.journal_repo,
            "ideas": deps.ideas_repo,
            "tips": deps.tips_repo,
            "user_ideas": deps.user_ideas_repo,
        },
        storage=deps.storage,
        config=settings,
    )

    # For intake: evaluate objectives from the user's message BEFORE the agent responds.
    # This updates intake responses so the system prompt checklist is current.
    # Skip the silent start turn (session auto-created with no user message).
    if session_type == "intake" and not intake_is_complete and user_message.strip() and department_config:
        try:
            from backend.agent.extraction import evaluate_objectives

            extraction_messages = _transcript_to_llm_messages(transcript)
            extraction_messages.append({"role": "user", "content": user_message.strip()})

            objectives = department_config.get("objectives", [])
            newly_completed = await evaluate_objectives(extraction_messages, objectives, intake_responses)

            if newly_completed:
                intake_responses.update(newly_completed)
                await save_intake_responses(deps.storage, user_id, intake_responses)
                # Rebuild system prompt with updated progress
                system_prompt = build_system_prompt(
                    profile=profile,
                    memory=memory,
                    skill_instructions=skill_instructions,
                    session_type=session_type,
                    department_config=department_config,
                    intake_responses=intake_responses,
                )
                logger.info("Objective evaluation completed %d objectives for user=%s", len(newly_completed), user_id)
        except Exception:
            logger.warning("Objective evaluation failed, continuing without it", exc_info=True)
    elif session_type == "intake" and not intake_is_complete and user_message.strip() and not department_config:
        # Legacy fallback: field-based extraction when no department config
        try:
            from backend.agent.extraction import extract_profile_data

            extraction_messages = _transcript_to_llm_messages(transcript)
            extraction_messages.append({"role": "user", "content": user_message.strip()})

            extracted = await extract_profile_data(extraction_messages, profile)
            if extracted:
                existing_captured = list(profile.intake_fields_captured) if profile.intake_fields_captured else []
                new_captured = list(set(existing_captured) | set(extracted.keys()))
                extracted["intake_fields_captured"] = new_captured

                await deps.profiles_repo.update(user_id, extracted)
                profile = await deps.profiles_repo.get(user_id) or profile
                system_prompt = build_system_prompt(
                    profile=profile,
                    memory=memory,
                    skill_instructions=skill_instructions,
                    session_type=session_type,
                )
                logger.info("Shadow extraction updated %d fields for user=%s", len(extracted), user_id)
        except Exception:
            logger.warning("Shadow extraction failed, continuing without it", exc_info=True)

    # Convert transcript to LLM message format
    llm_messages = _transcript_to_llm_messages(transcript)

    # Set up cancellation bridge to asyncio.Event
    cancel_event = asyncio.Event()
    cancel_task = None
    if cancel_check:
        cancel_task = asyncio.create_task(_poll_cancel(cancel_check, cancel_event))

    # Determine the prompt
    llm_prompt = user_message.strip() if user_message else "The user just opened the app. Begin the conversation."
    is_silent_start = not user_message.strip()

    # Token batching state
    token_buffer: list[str] = []
    last_flush_time = time.monotonic()

    async def flush_tokens():
        nonlocal token_buffer, last_flush_time
        if token_buffer:
            combined = "".join(token_buffer)
            await sender.send({
                "type": "token",
                "session_id": session_id,
                "content": combined,
            })
            token_buffer = []
            last_flush_time = time.monotonic()

    # Run the loop
    first_assistant_text: list[str] = []

    try:
        async for event in react_loop(
            user_message=llm_prompt,
            messages=llm_messages,
            system_prompt=system_prompt,
            tools=deps.tool_registry,
            context=context,
            cancel_event=cancel_event,
        ):
            if isinstance(event, TextEvent):
                first_assistant_text.append(event.text)
                token_buffer.append(event.text)
                if time.monotonic() - last_flush_time >= _TOKEN_BATCH_INTERVAL:
                    await flush_tokens()
            elif isinstance(event, ToolCallEvent):
                await flush_tokens()
                # Record in transcript for auditability
                transcript.append(Message(
                    role="tool_call",
                    content=json.dumps(event.arguments),
                    tool_name=event.tool_name,
                    tool_call_id=event.tool_call_id,
                    timestamp=datetime.now(UTC),
                ))
                # Send to client: search tools always visible, others only in dev mode
                if event.tool_name in _USER_VISIBLE_TOOLS or settings.dev_mode:
                    await sender.send({
                        "type": "tool_call",
                        "session_id": session_id,
                        "tool": event.tool_name,
                        "tool_call_id": event.tool_call_id,
                        "args": event.arguments,
                    })
            elif isinstance(event, ToolResultEvent):
                # Record in transcript
                transcript.append(Message(
                    role="tool_result",
                    content=event.result if isinstance(event.result, str) else json.dumps(event.result),
                    tool_call_id=event.tool_call_id,
                    timestamp=datetime.now(UTC),
                ))
                # Only send result to client for user-visible tools or dev mode
                if settings.dev_mode:
                    await sender.send({
                        "type": "tool_result",
                        "session_id": session_id,
                        "tool_call_id": event.tool_call_id,
                        "result": event.result,
                    })
            elif isinstance(event, DoneEvent):
                await flush_tokens()
                usage_data = None
                if event.usage:
                    usage_data = event.usage.model_dump()
                # Send intake checklist state before done (for debug UI)
                if session_type == "intake" and not intake_is_complete:
                    try:
                        from backend.agent.context import get_intake_checklist
                        await sender.send({
                            "type": "intake_progress",
                            "session_id": session_id,
                            "checklist": get_intake_checklist(department_config, intake_responses, profile),
                        })
                    except Exception:
                        pass

                await sender.send({
                    "type": "done",
                    "session_id": session_id,
                    "usage": usage_data,
                })
            elif isinstance(event, ErrorEvent):
                await flush_tokens()
                await sender.send({
                    "type": "error",
                    "session_id": session_id,
                    "message": event.error,
                })
    finally:
        if cancel_task:
            cancel_task.cancel()

    # Final flush
    await flush_tokens()

    # Append messages to transcript
    now = datetime.now(UTC)
    if not is_silent_start:
        transcript.append(Message(
            role="user",
            content=user_message.strip(),
            timestamp=now,
        ))
    assistant_text = "".join(first_assistant_text)
    if assistant_text:
        transcript.append(Message(
            role="assistant",
            content=assistant_text,
            timestamp=now,
        ))

    # Save transcript and update session
    await save_transcript(deps.storage, user_id, session_id, transcript)
    session = await deps.sessions_repo.get(user_id, session_id)
    if session:
        session.message_count = len(transcript)
        session.updated_at = datetime.now(UTC)
        await deps.sessions_repo.update(session)

    # Detect prepared tips and send preview data to frontend
    if session_type == "tip":
        await _check_tip_prepared(transcript, sender, session_id)

    # Detect prepared ideas and send preview data to frontend
    if session_type in ("brainstorm", "chat", "tip", "stuck", "intake"):
        await _check_idea_prepared(transcript, sender, session_id)

    # Intake state machine: check required fields and mark complete when done
    if session_type == "intake" and not intake_is_complete:
        await _check_intake_completion(deps, user_id, transcript, sender, session_id, department_config, intake_responses)

    # Generate title for sessions
    # - intake/wrapup: hardcoded titles, never overwritten
    # - brainstorm/stuck: defer until user's first real message (opening prompt is generic)
    # - chat/tip: generate immediately on first turn
    SESSION_TITLE_PREFIXES = {"brainstorm": "Brainstorm", "stuck": "Help"}
    DEFERRED_TITLE_TYPES = {"brainstorm", "stuck"}
    needs_title = False
    if session_type not in ("intake", "wrapup"):
        if session_type in DEFERRED_TITLE_TYPES:
            # Deferred: wait for user's first real message
            if not is_new_session and user_message.strip() and assistant_text and session:
                needs_title = len(transcript) <= 3  # opening + first user msg + response
        elif is_new_session and assistant_text:
            needs_title = True

    if needs_title:
        try:
            title = await _generate_title(user_message or "New conversation", assistant_text)
            prefix = SESSION_TITLE_PREFIXES.get(session_type)
            if prefix:
                title = f"{prefix}: {title}"
            if session:
                session.title = title
                await deps.sessions_repo.update(session)
            await sender.send({
                "type": "session_update",
                "session_id": session_id,
                "title": title,
            })
        except Exception:
            logger.warning("Failed to generate session title", exc_info=True)


async def _poll_cancel(cancel_check: Callable[[], bool], cancel_event: asyncio.Event):
    """Periodically poll the cancel_check and set the asyncio.Event if True."""
    try:
        while True:
            await asyncio.sleep(1.0)
            if cancel_check():
                cancel_event.set()
                return
    except asyncio.CancelledError:
        pass


def _transcript_to_llm_messages(transcript: list[Message]) -> list[dict]:
    """Convert stored Message objects to the LLM's message format."""
    messages = []
    for msg in transcript:
        if msg.role in ("user", "assistant", "system"):
            messages.append({"role": msg.role, "content": msg.content})

    # Bedrock requires conversations to start with a user message
    if messages and messages[0].get("role") == "assistant":
        messages.insert(0, {"role": "user", "content": "(session started)"})

    return messages




async def _extract_suggestions(transcript: list[Message]) -> list[str]:
    """Extract structured suggestions from the intake conversation using Haiku."""
    from backend.agent.extraction import extract_suggestions
    llm_messages = _transcript_to_llm_messages(transcript)
    return await extract_suggestions(llm_messages)


async def _check_intake_completion(
    deps: AgentDeps,
    user_id: str,
    transcript: list[Message],
    sender: MessageSender | None = None,
    session_id: str | None = None,
    department_config: dict | None = None,
    intake_responses: dict | None = None,
):
    """Mark intake complete when all required objectives/fields have been captured.

    When department_config is available, completion is based on objective coverage.
    Falls back to legacy field-based checking when no department config exists.
    """
    try:
        profile = await deps.profiles_repo.get(user_id)
        if not profile:
            return

        # Already completed in a previous turn - just notify the frontend
        if profile.intake_completed_at:
            if sender and session_id:
                suggestions = await _extract_suggestions(transcript)
                await sender.send({
                    "type": "intake_complete",
                    "session_id": session_id,
                    "suggestions": [s.get("title", "") if isinstance(s, dict) else str(s) for s in suggestions],
                })
            return

        # Check if all objectives are completed
        if department_config:
            objectives = department_config.get("objectives", [])
            objective_ids = {obj["id"] for obj in objectives}
            completed_ids = set(intake_responses.keys()) if intake_responses else set()
            all_complete = objective_ids.issubset(completed_ids)
        else:
            # Legacy fallback
            from backend.agent.context import _INTAKE_FIELDS
            required_fields = {field for field, _ in _INTAKE_FIELDS}
            captured = set(profile.intake_fields_captured) if profile.intake_fields_captured else set()
            all_complete = required_fields.issubset(captured)

        if all_complete:
            await deps.profiles_repo.update(user_id, {
                "intake_completed_at": datetime.now(UTC).isoformat(),
                "onboarding_complete": True,
            })
            if department_config:
                logger.info("Intake complete: user=%s objectives_completed=%s", user_id, completed_ids)
            else:
                logger.info("Intake complete: user=%s fields_captured=%s", user_id, captured)

            # Extract suggestions (Haiku, fast) and save as UserIdeas
            suggestions = await _extract_suggestions(transcript)
            if suggestions and deps.user_ideas_repo and session_id:
                for suggestion in suggestions:
                    title = suggestion.get("title", "")
                    description = suggestion.get("description", "")
                    if title:
                        idea = UserIdea(
                            user_id=user_id,
                            idea_id=str(uuid.uuid4()),
                            title=title,
                            description=description,
                            source="intake",
                            source_session_id=session_id,
                            tags=["intake"],
                        )
                        try:
                            await deps.user_ideas_repo.create(idea)
                            logger.info("Created intake idea: user=%s title=%s", user_id, title)
                        except Exception:
                            logger.warning("Failed to create intake idea: %s", title, exc_info=True)

            # Notify the frontend immediately so it can show the completion card
            if sender and session_id:
                await sender.send({
                    "type": "intake_complete",
                    "session_id": session_id,
                    "suggestions": [s.get("title", "") for s in suggestions],
                })

            # Fire-and-forget: Opus enrichment of profile + objective summaries
            objectives = department_config.get("objectives", []) if department_config else []
            asyncio.create_task(
                _enrich_profile_async(deps, user_id, transcript, objectives)
            )
    except Exception:
        logger.warning("Failed to check intake completion", exc_info=True)


async def _enrich_profile_async(
    deps: AgentDeps,
    user_id: str,
    transcript: list[Message],
    objectives: list[dict],
):
    """Background task: Opus enrichment of profile and objective summaries.

    Runs after intake completes. Updates profile fields and objective responses
    with thorough summaries based on the full transcript. Fire-and-forget.
    """
    try:
        from backend.agent.extraction import enrich_profile_with_opus, LIST_FIELDS

        llm_messages = _transcript_to_llm_messages(transcript)
        result = await enrich_profile_with_opus(llm_messages, objectives)
        if not result:
            logger.warning("Opus enrichment returned nothing for user=%s", user_id)
            return

        # Update profile fields
        profile_fields = result.get("profile", {})
        if profile_fields:
            # Filter to known fields and coerce types
            allowed = {
                "work_summary", "daily_tasks", "products", "ai_tools_used",
                "core_skills", "learning_goals", "ai_superpower", "goals",
                "intake_summary",
            }
            filtered = {k: v for k, v in profile_fields.items() if k in allowed and v}

            # Coerce string fields that came back as lists
            string_fields = allowed - LIST_FIELDS
            for key in string_fields:
                if key in filtered and isinstance(filtered[key], list):
                    filtered[key] = "; ".join(str(v) for v in filtered[key])

            if filtered:
                await deps.profiles_repo.update(user_id, filtered)
                logger.info("Opus enrichment updated profile: user=%s fields=%s", user_id, list(filtered.keys()))

        # Update objective summaries in intake responses
        obj_summaries = result.get("objectives", {})
        if obj_summaries:
            from backend.storage import load_intake_responses, save_intake_responses
            intake_responses = await load_intake_responses(deps.storage, user_id)
            updated = False
            for obj_id, summary in obj_summaries.items():
                if obj_id in intake_responses and isinstance(summary, str) and summary:
                    intake_responses[obj_id]["value"] = summary
                    updated = True
            if updated:
                await save_intake_responses(deps.storage, user_id, intake_responses)
                logger.info("Opus enrichment updated %d objective summaries for user=%s", len(obj_summaries), user_id)

        # Score AI proficiency (Opus has the full context, better than Haiku)
        from backend.agent.extraction import score_ai_proficiency
        proficiency = await score_ai_proficiency(llm_messages)
        if proficiency:
            await deps.profiles_repo.update(user_id, {"ai_proficiency": proficiency})
            logger.info("AI proficiency scored: user=%s level=%d", user_id, proficiency["level"])

    except Exception:
        logger.warning("Opus enrichment failed for user=%s", user_id, exc_info=True)


async def _check_tip_prepared(transcript: list[Message], sender: MessageSender, session_id: str):
    """Check if prepare_tip was called in this turn and send preview data to frontend."""
    try:
        for msg in reversed(transcript):
            if msg.role == "tool_call" and msg.tool_name == "prepare_tip":
                args = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                # Normalize department: "all" -> "Everyone"
                dept = args.get("department", "Everyone")
                if dept.lower() in ("all", ""):
                    dept = "Everyone"
                await sender.send({
                    "type": "tip_ready",
                    "session_id": session_id,
                    "title": args.get("title", ""),
                    "content": args.get("content", ""),
                    "tags": args.get("tags", []),
                    "department": dept,
                })
                return
    except Exception:
        logger.warning("Failed to check tip prepared", exc_info=True)


async def _check_idea_prepared(transcript: list[Message], sender: MessageSender, session_id: str):
    """Check if prepare_idea was called in this turn and send preview data to frontend."""
    try:
        for msg in reversed(transcript):
            if msg.role == "tool_call" and msg.tool_name == "prepare_idea":
                args = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                await sender.send({
                    "type": "idea_ready",
                    "session_id": session_id,
                    "title": args.get("title", ""),
                    "description": args.get("description", ""),
                    "tags": args.get("tags", []),
                })
                return
    except Exception:
        logger.warning("Failed to check idea prepared", exc_info=True)


async def _generate_title(user_msg: str, assistant_msg: str) -> str:
    """Call the LLM to generate a short session title."""
    prompt_messages = [
        {"role": "system", "content": "Generate a short title (max 6 words) for this conversation. Return only the title, no quotes or punctuation."},
        {"role": "user", "content": user_msg or "User started a new session"},
        {"role": "assistant", "content": assistant_msg},
        {"role": "user", "content": "Generate a short title for this conversation."},
    ]
    response = await call_llm(prompt_messages)
    title = (response.content or "New Chat").strip().strip('"').strip("'")
    return title[:100]
