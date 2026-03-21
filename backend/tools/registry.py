"""Tool registry: schema registration, dispatch, and execution context."""

import inspect
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
        """Execute a tool by name with the given arguments and context.

        Strips unknown kwargs that the LLM might hallucinate, preventing
        'unexpected keyword argument' errors.
        """
        handler = self._handlers.get(tool_name)
        if handler is None:
            return f"Unknown tool: {tool_name}"
        try:
            # Filter arguments to only those the handler accepts
            sig = inspect.signature(handler)
            params = sig.parameters
            has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

            if has_kwargs:
                # Handler accepts **kwargs, pass everything
                filtered_args = arguments
            else:
                # Only pass arguments the handler explicitly accepts
                accepted = {
                    name for name, p in params.items()
                    if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
                    and name != 'context'
                }
                filtered_args = {k: v for k, v in arguments.items() if k in accepted}

                dropped = set(arguments) - set(filtered_args)
                if dropped:
                    logger.debug("Tool '%s': dropped unknown args %s", tool_name, dropped)

            return await handler(**filtered_args, context=context)
        except Exception:
            logger.exception("Tool '%s' raised an exception", tool_name)
            raise
