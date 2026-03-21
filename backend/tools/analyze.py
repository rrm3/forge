"""Analyze and advise tool: routes complex analysis to Claude Opus.

Used during voice intake to get deeper analytical work done by a more
capable model. In text mode (already on Claude), this is less necessary
but still available for explicit analytical routing.
"""

import json
import logging

from backend.config import settings
from backend.llm import call_llm
from backend.storage import load_transcript
from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

ANALYZE_AND_ADVISE_SCHEMA = {
    "name": "analyze_and_advise",
    "description": (
        "Route a complex analytical question to Claude Opus for deeper analysis. "
        "The tool reads the full session transcript from storage and sends it "
        "along with the question to Opus. Use for proficiency scoring, "
        "generating personalized insights, or creating first-day suggestions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Current session ID (transcript is loaded from storage)",
            },
            "question": {
                "type": "string",
                "description": (
                    "What to analyze. Examples: "
                    "'Score the user\\'s AI proficiency dimensions based on this conversation', "
                    "'Generate 3-4 personalized first-day suggestions based on the intake'"
                ),
            },
        },
        "required": ["session_id", "question"],
    },
}


async def analyze_and_advise(
    session_id: str,
    question: str,
    context: ToolContext,
) -> str:
    """Route an analytical question to Claude Opus with full transcript context.

    Reads the session transcript from S3, sends it to Opus along with
    the question, and returns the analysis.
    """
    if context.storage is None:
        return "Storage backend not available."

    # Load the session transcript
    transcript = await load_transcript(context.storage, context.user_id, session_id)
    if not transcript:
        return "No transcript found for this session. Continue the conversation first."

    # Format transcript for analysis
    transcript_text = ""
    for msg in transcript:
        transcript_text += f"{msg.role}: {msg.content}\n\n"

    # Build the analysis prompt
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert AI coach and organizational psychologist analyzing "
                "an intake conversation for Digital Science's AI Tuesdays program. "
                "Provide thoughtful, specific analysis based on the conversation transcript."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Here is the full intake conversation transcript:\n\n"
                f"---\n{transcript_text}\n---\n\n"
                f"Based on this conversation, {question}\n\n"
                "Be specific and reference what the user actually said. "
                "If scoring proficiency dimensions (1-5), explain your reasoning briefly."
            ),
        },
    ]

    # Use Opus for deeper analysis (or Sonnet in dev)
    model = settings.llm_model
    # In production, prefer Opus for analytical tasks
    if "sonnet" in model.lower():
        opus_model = model.replace("sonnet", "opus").replace("Sonnet", "Opus")
        # Only use Opus if it looks like a valid model string
        if "opus" in opus_model.lower():
            model = opus_model

    try:
        response = await call_llm(messages, model=model)
        return response.content or "Analysis completed but no content returned."
    except Exception as e:
        logger.exception("analyze_and_advise failed")
        return f"Analysis failed: {e}"


def register_analyze_tools(registry) -> None:
    """Register the analyze_and_advise tool."""
    registry.register(ANALYZE_AND_ADVISE_SCHEMA, analyze_and_advise)
