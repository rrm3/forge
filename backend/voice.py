"""Voice mode: OpenAI Realtime API ephemeral token generation.

Creates server-side configured sessions with system prompts injected
so they're never exposed to the browser. The client receives an opaque
ephemeral token scoped to a single session.
"""

import json
import logging
from datetime import UTC, datetime

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

OPENAI_REALTIME_URL = "https://api.openai.com/v1/realtime/client_secrets"
OPENAI_MODEL = "gpt-4o-realtime-preview-2024-12-17"


def _get_openai_key() -> str:
    """Get the OpenAI API key from SSM or environment."""
    # Try environment first (for local dev)
    import os
    key = os.environ.get("OPEN_AI_KEY") or os.environ.get("OPENAI_API_KEY")
    if key:
        return key

    # Try SSM Parameter Store (production)
    try:
        import boto3
        ssm = boto3.client("ssm", region_name=settings.aws_region)
        response = ssm.get_parameter(Name="/forge/openai-api-key", WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        logger.error("Failed to get OpenAI API key from SSM: %s", e)
        raise ValueError("OpenAI API key not available") from e


# Tool definitions for voice sessions (subset of text tools that work well with voice)
VOICE_TOOLS = [
    {
        "type": "function",
        "name": "search",
        "description": "Search Digital Science's knowledge base for relevant information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "read_profile",
        "description": "Read the user's profile including their role, skills, and interests",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "update_profile",
        "description": "Update the user's profile with new information captured during conversation",
        "parameters": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "object",
                    "description": "Profile fields to update",
                },
            },
            "required": ["fields"],
        },
    },
    {
        "type": "function",
        "name": "save_journal",
        "description": "Save a journal entry capturing what the user learned or worked on",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Journal entry content"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for the entry"},
            },
            "required": ["content"],
        },
    },
    {
        "type": "function",
        "name": "analyze_and_advise",
        "description": (
            "Route a complex analytical question to Claude Opus for deeper analysis. "
            "Use this for proficiency scoring, generating personalized insights, "
            "or creating first-day suggestions during intake."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Current session ID"},
                "question": {"type": "string", "description": "What to analyze"},
            },
            "required": ["session_id", "question"],
        },
    },
]


async def create_voice_session(
    system_prompt: str,
    session_id: str,
    transcript_context: str | None = None,
) -> dict:
    """Create an OpenAI Realtime session and return the ephemeral token.

    Args:
        system_prompt: The system prompt to configure the session with.
        session_id: The Forge session ID (for tool validation).
        transcript_context: Optional existing transcript to include.

    Returns:
        Dict with 'token', 'expires_at', and 'model' keys.

    Raises:
        ValueError: If the API key is unavailable.
        httpx.HTTPError: If the OpenAI API request fails.
    """
    api_key = _get_openai_key()

    # Build the full instructions
    instructions = system_prompt
    if transcript_context:
        instructions += (
            "\n\n## Prior Conversation\n"
            "You are resuming a conversation. Here is the transcript so far:\n\n"
            f"{transcript_context}\n\n"
            "Continue naturally from where the conversation left off. "
            "Briefly acknowledge the resumption ('Welcome back! We were discussing...')."
        )

    # The GA client_secrets endpoint creates a bare token.
    # Session config (instructions, tools, VAD) is sent via data channel after WebRTC connects.
    async with httpx.AsyncClient() as client:
        response = await client.post(
            OPENAI_REALTIME_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={},
            timeout=10.0,
        )
        response.raise_for_status()

    data = response.json()

    return {
        "token": data["value"],
        "expires_at": data.get("expires_at", ""),
        "model": OPENAI_MODEL,
        "session_id": session_id,
        "instructions": instructions,
        "tools": VOICE_TOOLS,
    }
