"""Shadow extraction: extract structured profile data from conversation turns.

Runs a fast, cheap LLM call (Haiku) after each user message to extract
profile fields from the conversation. This is separate from the main
conversational agent, ensuring data capture doesn't depend on the agent
remembering to call update_profile.

The extraction runs BEFORE the main agent responds, so the system prompt
checklist is up-to-date when the agent generates its response.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from backend.llm import call_llm
from backend.models import UserProfile

logger = logging.getLogger(__name__)

# Fast, cheap model for profile field extraction
EXTRACTION_MODEL = "bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0"

# More capable model for nuanced judgment (objective evaluation)
EVALUATION_MODEL = "bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0"

# Fields we extract and their descriptions (for the extraction prompt)
EXTRACTABLE_FIELDS = {
    "work_summary": "Brief description of what they do day-to-day",
    "daily_tasks": "Specific tasks and responsibilities they mentioned",
    "products": "Products, projects, or systems they work on",
    "ai_tools_used": "AI tools they've tried (as a list)",
    "core_skills": "Skills they mentioned having (as a list)",
    "learning_goals": "Things they want to learn (as a list)",
    "ai_superpower": "What AI superpower they'd want",
    "goals": "Their goals for the 12-week program (as a list)",
}

# Fields that are stored as lists
LIST_FIELDS = {"ai_tools_used", "core_skills", "learning_goals", "goals", "products"}

_EXTRACTION_PROMPT_TEMPLATE = """\
You are a data extraction assistant. Read the conversation below and extract any profile information the user has shared.

Return a JSON object with ONLY the fields that have NEW information from the most recent user message. Do not repeat information already in the current profile. If the latest message doesn't contain extractable information, return an empty JSON object.

Fields to extract (ONLY from what the USER said, never from the AI's questions or statements):
- work_summary: the user's OWN description of what they do day-to-day. Must be based on what the user actually described, NOT their job title or org chart data. Requires at least 2-3 specific details about their actual work.
- daily_tasks: specific tasks the user described doing regularly (string)
- products: products/projects/systems the user said they work on (list of strings)
- ai_tools_used: AI tools the user said they have personally used (list of strings)
- core_skills: skills the user described having (list of strings)
- learning_goals: things the user said they want to learn (list of strings)
- ai_superpower: what AI capability the user said they'd want most (string)
- goals: goals the user stated for the program (list of strings)

IMPORTANT: Only extract from USER messages. Never extract from the AI assistant's questions, assumptions, or rephrasing. If the user hasn't provided enough detail for a field, do NOT fill it.

Current profile state:
CURRENT_PROFILE_PLACEHOLDER

Return ONLY valid JSON. No explanation, no markdown, no code fences."""


async def extract_profile_data(
    transcript_messages: list[dict],
    current_profile: UserProfile,
) -> dict:
    """Extract profile fields from the latest conversation turn.

    Args:
        transcript_messages: The conversation history as role/content dicts.
        current_profile: The current profile state (to avoid re-extracting known data).

    Returns:
        Dict of field_name -> value for newly extracted fields. Empty dict if nothing new.
    """
    if not transcript_messages:
        return {}

    # Build a summary of what's already in the profile
    current_state = {}
    for field in EXTRACTABLE_FIELDS:
        value = getattr(current_profile, field, None)
        if value:
            current_state[field] = value

    # Build the extraction prompt
    profile_json = json.dumps(current_state, default=str) if current_state else "{}"
    system = _EXTRACTION_PROMPT_TEMPLATE.replace("CURRENT_PROFILE_PLACEHOLDER", profile_json)

    # Include last few messages for context (not the entire history)
    recent = transcript_messages[-6:] if len(transcript_messages) > 6 else transcript_messages

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": _format_conversation(recent)},
    ]

    try:
        response = await call_llm(messages, model=EXTRACTION_MODEL, stream=False)
        if not response.content:
            return {}

        # Parse the JSON response
        text = response.content.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        extracted = json.loads(text)

        if not isinstance(extracted, dict):
            return {}

        # Filter to only valid fields with actual values
        result = {}
        for field, value in extracted.items():
            if field not in EXTRACTABLE_FIELDS:
                continue
            if not value:
                continue
            # Ensure list fields are lists, string fields are strings
            if field in LIST_FIELDS and isinstance(value, str):
                value = [v.strip() for v in value.split(",") if v.strip()]
            elif field not in LIST_FIELDS and isinstance(value, list):
                value = "; ".join(str(v) for v in value)
            result[field] = value

        if result:
            logger.info("Extracted %d fields: %s", len(result), list(result.keys()))

        return result

    except json.JSONDecodeError:
        logger.warning("Shadow extraction returned invalid JSON")
        return {}
    except Exception:
        logger.warning("Shadow extraction failed", exc_info=True)
        return {}


def _format_conversation(messages: list[dict]) -> str:
    """Format only USER messages for extraction. We exclude assistant messages
    to prevent the extractor from attributing AI statements to the user."""
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if role == "user":
            lines.append(f"USER: {content}")
    return "\n\n".join(lines)


_PROFICIENCY_PROMPT = """\
You are scoring a user's AI proficiency based on their intake conversation.

Score on a 1-5 scale:
1 - Aware: Knows AI exists, hasn't used it meaningfully
2 - Experimenting: Has tried ChatGPT or similar for basic tasks (writing, search)
3 - Practicing: Uses AI tools regularly, can prompt effectively, understands limitations
4 - Proficient: Has built workflows around AI, uses multiple tools, understands technical concepts (embeddings, RAG, agents)
5 - Advanced: Builds AI applications, fine-tunes models, deep technical understanding, teaches others

Base your score ONLY on what the user themselves described doing, not on their job title or aspirations.

Return ONLY a JSON object with two fields:
- "level": integer 1-5
- "rationale": one sentence explaining why

No markdown, no code fences, just JSON."""


async def score_ai_proficiency(transcript_messages: list[dict]) -> dict | None:
    """Score the user's AI proficiency from the full intake transcript.

    Called once after intake completes. Returns {"level": int, "rationale": str}
    or None if scoring fails.
    """
    user_text = _format_conversation(transcript_messages)
    if not user_text:
        return None

    messages = [
        {"role": "system", "content": _PROFICIENCY_PROMPT},
        {"role": "user", "content": user_text},
    ]

    try:
        response = await call_llm(messages, model=EXTRACTION_MODEL, stream=False)
        if not response.content:
            return None

        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        result = json.loads(text)
        if not isinstance(result, dict) or "level" not in result:
            return None

        level = int(result["level"])
        if level < 1 or level > 5:
            return None

        return {"level": level, "rationale": result.get("rationale", "")}

    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("AI proficiency scoring returned invalid response")
        return None
    except Exception:
        logger.warning("AI proficiency scoring failed", exc_info=True)
        return None


_OBJECTIVES_PROMPT_TEMPLATE = """\
You are evaluating whether an intake conversation has covered specific objectives.

Objectives to evaluate:
REMAINING_OBJECTIVES_PLACEHOLDER

Already completed (do not re-evaluate):
COMPLETED_OBJECTIVES_PLACEHOLDER

Based on what the USER said in the conversation below, determine which remaining objectives the user has directly addressed. An objective is covered when the user has shared enough that you wouldn't need to ask them about it again. A passing mention or vague reference doesn't count - the user should have actually talked about the topic, not just brushed past it. Generic answers that could apply to anyone (e.g., "I spend time in meetings and emails") don't count - the answer should be specific enough to tell you something about this person's actual situation.

IMPORTANT: Only evaluate based on USER messages, not the AI's questions or statements. If the AI said "you're a VP of Engineering" but the user never confirmed or discussed it, that doesn't count.

Return a JSON object where keys are objective IDs and values are a brief summary (1-2 sentences) of what the user said that covers it. Only include objectives that ARE covered. If none are newly covered, return {}.

Return ONLY valid JSON. No explanation, no markdown, no code fences."""


async def evaluate_objectives(
    transcript_messages: list[dict],
    objectives: list[dict],
    current_responses: dict,
) -> dict:
    """Evaluate which intake objectives have been covered in the conversation.

    Uses Sonnet for nuanced judgment - distinguishing direct answers from
    vague or tangential mentions. Captures a brief summary of what the user
    said for each covered objective, so the data is useful even without
    the post-completion Opus enrichment pass.

    Args:
        transcript_messages: The conversation as role/content dicts.
        objectives: List of objective dicts from department config, each with id, label, description.
        current_responses: Already-captured responses {objective_id: {value, captured_at}}.

    Returns:
        Dict of newly completed objectives: {objective_id: {"value": "summary", "captured_at": "ISO datetime"}}
        Only includes objectives that are NEW (not already in current_responses).
    """
    if not transcript_messages or not objectives:
        return {}

    # Split objectives into remaining vs completed
    completed_ids = set(current_responses.keys())
    remaining = [o for o in objectives if o["id"] not in completed_ids]
    completed = [o for o in objectives if o["id"] in completed_ids]

    if not remaining:
        return {}

    # Build the prompt
    remaining_lines = []
    for o in remaining:
        remaining_lines.append(f"- {o['id']}: {o['label']} - {o.get('description', '')}")
    remaining_text = "\n".join(remaining_lines) if remaining_lines else "(none)"

    completed_lines = []
    for o in completed:
        completed_lines.append(f"- {o['id']}: {o['label']}")
    completed_text = "\n".join(completed_lines) if completed_lines else "(none)"

    system = _OBJECTIVES_PROMPT_TEMPLATE.replace(
        "REMAINING_OBJECTIVES_PLACEHOLDER", remaining_text
    ).replace(
        "COMPLETED_OBJECTIVES_PLACEHOLDER", completed_text
    )

    # Include last 6 messages, USER-only via _format_conversation
    recent = transcript_messages[-6:] if len(transcript_messages) > 6 else transcript_messages

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": _format_conversation(recent)},
    ]

    valid_remaining_ids = {o["id"] for o in remaining}

    try:
        response = await call_llm(messages, model=EVALUATION_MODEL, stream=False)
        if not response.content:
            return {}

        text = response.content.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        extracted = json.loads(text)

        if not isinstance(extracted, dict):
            return {}

        # Filter to valid remaining objective IDs, store summaries as values
        now = datetime.now(UTC).isoformat()
        result = {}
        for obj_id, val in extracted.items():
            if obj_id not in valid_remaining_ids:
                continue
            if not val:
                continue
            # Sonnet returns summary strings; fall back to "answered" for booleans
            summary = str(val) if not isinstance(val, bool) else "answered"
            result[obj_id] = {"value": summary, "captured_at": now}

        if result:
            logger.info("Objectives completed: %s", list(result.keys()))

        return result

    except json.JSONDecodeError:
        logger.warning("Objective evaluation returned invalid JSON")
        return {}
    except Exception:
        logger.warning("Objective evaluation failed", exc_info=True)
        return {}


# ---------------------------------------------------------------------------
# Post-completion Opus enrichment
# ---------------------------------------------------------------------------

_ENRICHMENT_PROMPT = """\
You are a profile analyst. Read the full intake conversation and extract comprehensive, accurate information about this person.

Extract the following fields based ONLY on what the USER said (never from the AI's questions or assumptions):

PROFILE FIELDS:
- work_summary: 2-3 sentence description of what they actually do day-to-day
- daily_tasks: Specific tasks and responsibilities (string, semicolon-separated if multiple)
- products: Products, projects, or systems they work on (list of strings)
- ai_tools_used: AI tools they've personally used (list of strings)
- core_skills: Skills they described having (list of strings)
- learning_goals: Things they want to learn (list of strings)
- ai_superpower: What AI capability they'd want most (string)
- goals: Their goals for the program (list of strings)
- intake_summary: A concise narrative (3-5 sentences) summarizing who this person is, what they do, their AI experience, and what they want to get out of the program

OBJECTIVE SUMMARIES:
For each objective ID listed below, write a thorough summary (50-100 words) of what the user shared that addresses it. Use specifics from the conversation.

OBJECTIVES_PLACEHOLDER

Return a JSON object with two keys:
- "profile": object with the profile fields above (omit any field the user didn't address)
- "objectives": object mapping objective_id to summary string

Return ONLY valid JSON. No explanation, no markdown, no code fences."""


async def enrich_profile_with_opus(
    transcript_messages: list[dict],
    objectives: list[dict] | None = None,
) -> dict | None:
    """Run a thorough Opus pass over the full transcript to extract rich profile data.

    Called asynchronously after intake completes. Returns a dict with:
    - "profile": dict of profile fields to update
    - "objectives": dict of objective_id -> detailed summary

    Returns None on failure.
    """
    if not transcript_messages:
        return None

    # Build objectives section
    if objectives:
        obj_lines = [f"- {o['id']}: {o['label']} - {o.get('description', '')}" for o in objectives]
        obj_text = "\n".join(obj_lines)
    else:
        obj_text = "(none)"

    system = _ENRICHMENT_PROMPT.replace("OBJECTIVES_PLACEHOLDER", obj_text)

    # Include full conversation (both user and assistant for context)
    formatted = []
    for msg in transcript_messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        if role in ("USER", "ASSISTANT"):
            formatted.append(f"{role}: {content}")
    conversation = "\n\n".join(formatted)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": conversation},
    ]

    text = ""
    try:
        from backend.config import settings
        response = await call_llm(messages, model=settings.llm_model, stream=False)
        if not response.content:
            return None

        text = response.content.strip()
        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        if text.startswith("```"):
            # Remove opening fence line
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        result = json.loads(text)
        if not isinstance(result, dict):
            logger.warning("Opus enrichment returned non-dict: %s", type(result))
            return None

        logger.info(
            "Opus enrichment complete: profile_fields=%s, objectives=%s",
            list(result.get("profile", {}).keys()),
            list(result.get("objectives", {}).keys()),
        )
        return result

    except json.JSONDecodeError:
        logger.warning("Opus enrichment returned invalid JSON: %s", text[:500] if text else "(empty)")
        return None
    except Exception:
        logger.warning("Opus enrichment failed", exc_info=True)
        return None


_SUGGESTIONS_PROMPT = """\
You are extracting personalized AI activity suggestions from an intake conversation.

Read the conversation and identify 2-4 specific, actionable suggestions the AI coach gave the user for their AI Tuesdays. These are things the user could work on in their first sessions.

Return a JSON array of objects, each with:
- "title": short activity title (under 15 words)
- "description": 1-2 sentence explanation connecting the suggestion to what the user shared

Example:
[{"title": "Build a decision context agent", "description": "Pull relevant context from Confluence and Slack to prep for prioritization calls, saving the manual gathering you described."}]

If the conversation doesn't contain clear suggestions, return an empty array.

No markdown, no code fences, just a JSON array."""


async def extract_suggestions(transcript_messages: list[dict]) -> list[dict]:
    """Extract structured suggestions from the intake conversation.

    Returns list of dicts with 'title' and 'description' keys.
    """
    if not transcript_messages:
        return []

    # Include full conversation - assistant messages have the suggestions
    recent = transcript_messages[-10:] if len(transcript_messages) > 10 else transcript_messages
    formatted = []
    for msg in recent:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        if role in ("USER", "ASSISTANT"):
            formatted.append(f"{role}: {content}")
    conversation = "\n\n".join(formatted)

    messages = [
        {"role": "system", "content": _SUGGESTIONS_PROMPT},
        {"role": "user", "content": conversation},
    ]

    try:
        response = await call_llm(messages, model=EXTRACTION_MODEL, stream=False)
        if not response.content:
            return []

        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        result = json.loads(text)
        if not isinstance(result, list):
            return []

        # Normalize: accept both old string format and new object format
        suggestions = []
        for item in result[:4]:
            if isinstance(item, str) and item:
                suggestions.append({"title": item, "description": ""})
            elif isinstance(item, dict) and item.get("title"):
                suggestions.append({
                    "title": str(item["title"]),
                    "description": str(item.get("description", "")),
                })
        return suggestions

    except (json.JSONDecodeError, ValueError):
        logger.warning("Suggestion extraction returned invalid JSON")
        return []
    except Exception:
        logger.warning("Suggestion extraction failed", exc_info=True)
        return []
