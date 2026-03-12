"""Tool registry: schema registration, dispatch, and execution context."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from backend.config import Settings
from backend.storage import StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    user_id: str
    session_id: str
    repos: dict = field(default_factory=dict)
    storage: StorageBackend | None = None
    config: Settings | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._schemas: list[dict] = []
        self._handlers: dict[str, Callable] = {}

    def register(self, schema: dict, handler: Callable) -> None:
        """Register a tool schema and its handler function."""
        name = schema["name"]
        self._schemas.append(schema)
        self._handlers[name] = handler
        logger.debug("Registered tool: %s", name)

    def get_schemas(self) -> list[dict]:
        """Return all tool schemas in Anthropic tool_use format."""
        return list(self._schemas)

    async def execute(self, tool_name: str, arguments: dict, context: ToolContext) -> str:
        """Execute a tool by name with the given arguments and context."""
        handler = self._handlers.get(tool_name)
        if handler is None:
            return f"Unknown tool: {tool_name}"
        try:
            return await handler(**arguments, context=context)
        except Exception:
            logger.exception("Tool '%s' raised an exception", tool_name)
            raise
