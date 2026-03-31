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

    def _get_schema(self, tool_name: str) -> dict | None:
        for s in self._schemas:
            if s["name"] == tool_name:
                return s
        return None

    async def execute(self, tool_name: str, arguments: dict, context: ToolContext) -> str:
        """Execute a tool by name with the given arguments and context.

        Strips unknown kwargs that the LLM might hallucinate, preventing
        'unexpected keyword argument' errors.  Also validates required args
        from the schema before calling the handler.
        """
        handler = self._handlers.get(tool_name)
        if handler is None:
            return f"Unknown tool: {tool_name}"

        # Validate required arguments from schema before calling handler
        schema = self._get_schema(tool_name)
        if schema:
            required = schema.get("input_schema", {}).get("required", [])
            missing = [r for r in required if r not in arguments]
            if missing:
                logger.warning("Tool '%s': missing required args %s", tool_name, missing)
                return f"Error: missing required argument(s): {', '.join(missing)}. Please provide all required arguments."

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
        except TypeError as exc:
            # Missing required args - return a clean message to the LLM
            # so it can retry, instead of a raw Python traceback
            logger.warning("Tool '%s' called with bad arguments: %s", tool_name, exc)
            return f"Error: {exc}. Please provide all required arguments."
        except Exception:
            logger.exception("Tool '%s' raised an exception", tool_name)
            raise


class FilteredToolRegistry:
    """Wraps a ToolRegistry, hiding specific tools from the schema list."""

    def __init__(self, registry: ToolRegistry, exclude: set[str]) -> None:
        self._registry = registry
        self._exclude = exclude

    def get_schemas(self) -> list[dict]:
        return [s for s in self._registry.get_schemas() if s["name"] not in self._exclude]

    async def execute(self, tool_name: str, arguments: dict, context: ToolContext) -> str:
        return await self._registry.execute(tool_name, arguments, context)
