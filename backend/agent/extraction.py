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

# Fast, cheap model for extraction
EXTRACTION_MODEL = "bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0"

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
            # Ensure list fields are lists
            if field in LIST_FIELDS and isinstance(value, str):
                value = [v.strip() for v in value.split(",") if v.strip()]
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
