"""SSE formatting helper."""

import json


def format_sse(event_type: str, data: dict) -> str:
    """Format as SSE: event: {type}\\ndata: {json}\\n\\n"""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
