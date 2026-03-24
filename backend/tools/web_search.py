"""Web search tool using Google Grounding (Gemini + Google Search)."""

import logging

from backend.config import settings
from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

WEB_SEARCH_SCHEMA = {
    "name": "search_web",
    "description": (
        "Search the public internet using Google Search. Use this for questions about "
        "current events, public company information, industry trends, competitor news, "
        "technology documentation, or anything that requires up-to-date web information. "
        "Do NOT use this for internal Digital Science information - use the 'search_internal' tool instead."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to look up on the web",
            },
        },
        "required": ["query"],
    },
}


async def web_search_tool(query: str, context: ToolContext) -> str:
    """Execute a web search using Google Grounding via Gemini."""
    from google import genai
    from google.genai import types

    if not settings.gemini_api_key:
        return "Web search unavailable: Gemini API key not configured."

    try:
        client = genai.Client(api_key=settings.gemini_api_key)

        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=query,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        parts = []

        # Extract the grounded text response
        if response.text:
            parts.append(response.text.strip())

        # Extract grounding sources for citation
        grounding = getattr(response.candidates[0], "grounding_metadata", None)
        if grounding:
            chunks = getattr(grounding, "grounding_chunks", None)
            if chunks:
                sources = []
                seen = set()
                for chunk in chunks:
                    web = getattr(chunk, "web", None)
                    if web:
                        uri = getattr(web, "uri", "")
                        title = getattr(web, "title", "")
                        if uri and uri not in seen:
                            seen.add(uri)
                            sources.append(f"* {title}: {uri}" if title else f"* {uri}")
                if sources:
                    parts.append("\nSources:")
                    parts.extend(sources)

        if not parts:
            return f"No web results found for '{query}'."

        return "\n".join(parts)

    except Exception:
        logger.exception("Web search failed for query: %s", query)
        return f"Web search failed for '{query}'. Please try again."


def register_web_search_tools(registry) -> None:
    """Register the web search tool."""
    registry.register(WEB_SEARCH_SCHEMA, web_search_tool)
