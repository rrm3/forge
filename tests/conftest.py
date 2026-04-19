"""Root conftest - ensure DEV_MODE is set before any backend imports."""

import os

os.environ.setdefault("DEV_MODE", "true")

from unittest.mock import patch
import pytest

_TEST_MODELS = {
    "opus": "anthropic/claude-test-opus",
    "sonnet": "anthropic/claude-test-sonnet",
    "haiku": "anthropic/claude-test-haiku",
}


@pytest.fixture(autouse=True)
def _mock_model_config():
    """Provide test model IDs so tests don't need S3."""
    with patch("backend.model_config.get_model", side_effect=lambda slot: _TEST_MODELS[slot]):
        yield
