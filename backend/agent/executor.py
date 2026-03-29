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
from backend.analytics import identify as posthog_identify, track as posthog_track
from backend.api.transport import MessageSender
from backend.config import settings
from backend.deps import AgentDeps
from backend.llm import call_llm
from backend.models import Message, UserIdea, get_program_week
from backend.repository.department_config import DepartmentConfigRepository
from backend.storage import load_intake_responses, load_memory, load_transcript, load_weekly_briefing, save_intake_responses, save_transcript
from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

# Token batching interval (seconds)
_TOKEN_BATCH_INTERVAL = 0.05  # 50ms

# Tools whose calls/results are shown to the client (others hidden unless dev_mode)
_USER_VISIBLE_TOOLS = {"search_internal", "search_web", "retrieve_document"}


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
    # PostHog: track session start (identify with full profile happens after profile load)
    trace_id = str(uuid.uuid4())
    posthog_track(user_id, "session_started", {
        "session_id": session_id,
        "session_type": session_type,
        "is_new_session": is_new_session,
    })
    posthog_metadata = {
        "user_id": user_id,
        "session_id": session_id,
        "trace_id": trace_id,
    }

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

    # PostHog: identify with full profile on new sessions
    if is_new_session and profile:
        posthog_identify(user_id, {
            "email": profile.email,
            "name": profile.name,
            "title": profile.title,
            "department": profile.department,
            "team": profile.team,
            "location": profile.location,
            "onboarding_complete": profile.onboarding_complete,
            "intake_completed_at": profile.intake_completed_at.isoformat() if profile.intake_completed_at else None,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
        })

    memory = await load_memory(deps.storage, user_id)

    # Completed intake sessions behave like normal chats.
    # Skipped intakes stay in intake mode so objectives continue evaluating.
    # Week-aware: check if the current week is in intake_weeks.
    current_week = get_program_week()
    intake_is_complete = (
        session_type == "intake"
        and profile
        and str(current_week) in (profile.intake_weeks or {})
        and not profile.intake_skipped
    )

    # Load company config (shared across all sessions)
    dept_config_repo = DepartmentConfigRepository(deps.storage)
    company_config = await dept_config_repo.get_company_config()
    company_prompt = (company_config or {}).get("prompt", "") or None

    # Load department config for all sessions when user has a department.
    # For intake sessions, merge company-wide + department-specific objectives.
    department_config = None
    merged_objectives: list[dict] = []
    intake_responses = {}
    if profile and profile.department:
        dept_slug = profile.department.lower().replace(" ", "-")
        department_config = await dept_config_repo.get_department_config(dept_slug)
        merged_objectives = await dept_config_repo.get_merged_objectives(dept_slug)
    # Load intake responses only for incomplete intake sessions
    if session_type == "intake" and not intake_is_complete:
        intake_responses = await load_intake_responses(deps.storage, user_id)

    # Build a merged config dict for context/evaluation (company + dept objectives)
    merged_config = dict(department_config or {})
    if merged_objectives:
        merged_config["objectives"] = merged_objectives

    # Load weekly briefing for intake sessions (Week 2+)
    weekly_briefing = None
    if session_type == "intake" and not intake_is_complete and current_week > 1:
        weekly_briefing = await load_weekly_briefing(deps.storage, user_id)

    # Load session-type prompt
    skill_instructions = None
    if session_type == "intake" and intake_is_complete:
        skill_instructions = load_skill("chat")  # completed intake behaves like chat
    else:
        skill_instructions = load_skill(session_type)

    # Build system prompt.
    # Pass merged_config (company + dept objectives) for intake objective tracking,
    # but department_config for department context prompt.
    system_prompt = build_system_prompt(
        profile=profile,
        memory=memory,
        skill_instructions=skill_instructions,
        session_type=session_type,
        department_config=department_config,
        intake_responses=intake_responses,
        idea=idea,
        company_prompt=company_prompt,
        merged_objectives=merged_objectives if session_type == "intake" else None,
        weekly_briefing=weekly_briefing,
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
    if session_type == "intake" and not intake_is_complete and user_message.strip() and merged_objectives:
        try:
            from backend.agent.extraction import evaluate_objectives

            extraction_messages = _transcript_to_llm_messages(transcript)
            extraction_messages.append({"role": "user", "content": user_message.strip()})

            newly_completed = await evaluate_objectives(extraction_messages, merged_objectives, intake_responses)

            if newly_completed:
                intake_responses.update(newly_completed)
                await save_intake_responses(deps.storage, user_id, intake_responses)
                # Update progress counts on profile for dashboard
                await deps.profiles_repo.update(user_id, {
                    "intake_objectives_done": len(intake_responses),
                    "intake_objectives_total": len(merged_objectives),
                })
                # Rebuild system prompt with updated progress
                system_prompt = build_system_prompt(
                    profile=profile,
                    memory=memory,
                    skill_instructions=skill_instructions,
                    session_type=session_type,
                    department_config=department_config,
                    intake_responses=intake_responses,
                    company_prompt=company_prompt,
                    merged_objectives=merged_objectives,
                    weekly_briefing=weekly_briefing,
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
                    department_config=department_config,
                    company_prompt=company_prompt,
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
    # Defer the 'done' message until after all cleanup so the session lock/mutex
    # is released before the frontend allows sending the next message.
    deferred_done_payload: dict | None = None

    try:
        async for event in react_loop(
            user_message=llm_prompt,
            messages=llm_messages,
            system_prompt=system_prompt,
            tools=deps.tool_registry,
            context=context,
            cancel_event=cancel_event,
            metadata=posthog_metadata,
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
                            "checklist": get_intake_checklist(merged_config if merged_objectives else department_config, intake_responses, profile),
                        })
                    except Exception:
                        pass

                # Defer sending 'done' until after cleanup (transcript save, title
                # generation, etc.) so the session lock is released first.  Without
                # this, a fast follow-up message hits "Session is already processing".
                deferred_done_payload = {
                    "type": "done",
                    "session_id": session_id,
                    "usage": usage_data,
                }
                posthog_track(user_id, "agent_completed", {
                    "session_id": session_id,
                    "session_type": session_type,
                    **(usage_data or {}),
                })
            elif isinstance(event, ErrorEvent):
                await flush_tokens()
                await sender.send({
                    "type": "error",
                    "session_id": session_id,
                    "message": event.error,
                })
                posthog_track(user_id, "agent_error", {
                    "session_id": session_id,
                    "session_type": session_type,
                    "error": event.error,
                })
    finally:
        if cancel_task:
            cancel_task.cancel()

    # Post-loop cleanup: save transcript, generate title, detect tips/ideas.
    # Wrapped in try/finally to guarantee the deferred 'done' message is sent
    # even if cleanup fails — otherwise the frontend hangs in isStreaming.
    enrichment_args = None
    try:
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
            enrichment_args = await _check_intake_completion(
                deps, user_id, transcript, sender, session_id,
                merged_config if merged_objectives else department_config,
                intake_responses,
            )

        # Generate title for sessions
        # - intake/wrapup: hardcoded titles, never overwritten
        # - all others: defer until user's first real message (silent start has no content to name)
        SESSION_TITLE_PREFIXES = {"brainstorm": "Brainstorm", "stuck": "Help", "tip": "New Tip"}
        needs_title = False
        if session_type not in ("intake", "wrapup"):
            if not is_silent_start and user_message.strip() and assistant_text and session:
                needs_title = not session.title

        if needs_title:
            try:
                title = await _generate_title(user_message or "New conversation", assistant_text, metadata=posthog_metadata)
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
    except Exception:
        logger.exception("Post-loop cleanup failed for session=%s", session_id)
    finally:
        # Send the deferred 'done' message AFTER cleanup completes (or fails).
        # This ensures the session lock/mutex is released before the frontend
        # allows the user to send the next message.
        if deferred_done_payload:
            await sender.send(deferred_done_payload)

    # Opus enrichment runs AFTER the done message so the user is unblocked.
    # Awaited (not fire-and-forget) because Lambda's asyncio.run() tears down
    # the event loop when the outer coroutine returns, killing pending tasks.
    if enrichment_args:
        await _enrich_profile_async(**enrichment_args)


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
) -> dict | None:
    """Mark intake complete when all required objectives/fields have been captured.

    When department_config is available, completion is based on objective coverage.
    Falls back to legacy field-based checking when no department config exists.

    Returns enrichment args dict if intake just completed (caller should await
    _enrich_profile_async after sending the 'done' message), or None otherwise.
    """
    try:
        profile = await deps.profiles_repo.get(user_id)
        if not profile:
            return

        # Already completed in a previous turn - ensure ideas exist and notify frontend
        if profile.intake_completed_at:
            suggestions = await _extract_suggestions(transcript)
            if suggestions and deps.user_ideas_repo and session_id:
                existing = await deps.user_ideas_repo.list(user_id)
                intake_ideas = [i for i in existing if i.source == "intake"]
                if not intake_ideas:
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
                                logger.info("Created intake idea (recovery): user=%s title=%s", user_id, title)
                            except Exception:
                                logger.warning("Failed to create intake idea: %s", title, exc_info=True)
            if sender and session_id:
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
            week_str = str(get_program_week())
            now_iso = datetime.now(UTC).isoformat()
            current_weeks = dict(profile.intake_weeks or {}) if profile else {}
            current_weeks[week_str] = now_iso
            await deps.profiles_repo.update(user_id, {
                "intake_completed_at": now_iso,
                "onboarding_complete": True,
                "intake_skipped": False,
                "intake_weeks": current_weeks,
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

            # Return enrichment args so caller can await after sending 'done'.
            # Running enrichment here as fire-and-forget doesn't work on Lambda
            # because asyncio.run() tears down the event loop (and all pending
            # tasks) as soon as the outer coroutine returns.
            objectives = department_config.get("objectives", []) if department_config else []
            return {"deps": deps, "user_id": user_id, "transcript": transcript, "objectives": objectives}
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


async def _generate_title(user_msg: str, assistant_msg: str, metadata: dict | None = None) -> str:
    """Call the LLM to generate a short session title."""
    prompt_messages = [
        {"role": "system", "content": "Generate a short title (max 6 words) for this conversation. Return only the title, no quotes or punctuation."},
        {"role": "user", "content": user_msg or "User started a new session"},
        {"role": "assistant", "content": assistant_msg},
        {"role": "user", "content": "Generate a short title for this conversation."},
    ]
    response = await call_llm(prompt_messages, metadata=metadata)
    title = (response.content or "New Chat").strip().strip('"').strip("'")
    return title[:100]
