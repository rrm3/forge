"""Runtime model configuration loaded from S3 with TTL cache.

Reads config/models.json from the app's S3 bucket. Falls back to hardcoded
defaults if S3 is unavailable. Re-reads every 5 minutes without requiring
Lambda restart.

Usage:
    from backend.model_config import get_model

    model = get_model("opus")   # returns current Bedrock model ID
    model = get_model("sonnet")
    model = get_model("haiku")
"""

import json
import logging
import time

logger = logging.getLogger(__name__)

MODELS_KEY = "config/models.json"
CACHE_TTL = 300  # 5 minutes

DEFAULTS = {
    "opus": "bedrock/global.anthropic.claude-opus-4-7",
    "sonnet": "bedrock/global.anthropic.claude-sonnet-4-6",
    "haiku": "bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0",
}

_storage = None
_cache: dict | None = None
_cache_time: float = 0


def set_model_config_storage(storage):
    """Wire the storage backend. Called once at startup from main.py."""
    global _storage
    _storage = storage


def _load_from_storage() -> dict | None:
    """Synchronous read from storage. Returns parsed dict or None."""
    if _storage is None:
        return None
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _storage.read(MODELS_KEY))
                raw = future.result(timeout=5)
        else:
            raw = loop.run_until_complete(_storage.read(MODELS_KEY))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.warning("Failed to load models config from S3", exc_info=True)
        return None


async def _async_load_from_storage() -> dict | None:
    """Async read from storage."""
    if _storage is None:
        return None
    try:
        raw = await _storage.read(MODELS_KEY)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.warning("Failed to load models config from S3", exc_info=True)
        return None


def _refresh_if_stale():
    """Refresh the cache if TTL has expired."""
    global _cache, _cache_time
    now = time.time()
    if _cache is not None and (now - _cache_time) < CACHE_TTL:
        return
    loaded = _load_from_storage()
    if loaded is not None:
        _cache = loaded
        _cache_time = now
        logger.info("Models config loaded: %s", {k: v for k, v in loaded.items() if k in DEFAULTS})


async def _async_refresh_if_stale():
    """Async refresh the cache if TTL has expired."""
    global _cache, _cache_time
    now = time.time()
    if _cache is not None and (now - _cache_time) < CACHE_TTL:
        return
    loaded = await _async_load_from_storage()
    if loaded is not None:
        _cache = loaded
        _cache_time = now
        logger.info("Models config loaded: %s", {k: v for k, v in loaded.items() if k in DEFAULTS})


def get_model(slot: str) -> str:
    """Get the current model ID for a logical slot (opus/sonnet/haiku).

    Reads from S3-cached config, falls back to hardcoded defaults.
    Safe to call from sync code (agent loop, extraction).
    """
    _refresh_if_stale()
    if _cache and slot in _cache:
        return _cache[slot]
    return DEFAULTS.get(slot, DEFAULTS["opus"])


async def async_get_model(slot: str) -> str:
    """Async version of get_model. Preferred in async endpoints."""
    await _async_refresh_if_stale()
    if _cache and slot in _cache:
        return _cache[slot]
    return DEFAULTS.get(slot, DEFAULTS["opus"])


def reload_cache():
    """Force-clear the cache so next get_model() re-reads from S3."""
    global _cache, _cache_time
    _cache = None
    _cache_time = 0
    logger.info("Models config cache cleared")
