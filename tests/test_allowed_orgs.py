"""Tests for backend/allowed_orgs.py."""

import json
from unittest.mock import patch

from backend.allowed_orgs import (
    _load_from_local,
    get_allowed_org_ids,
    is_org_allowed,
)
import backend.allowed_orgs as mod


def _reset_cache():
    """Clear the module-level cache between tests."""
    mod._cached_org_ids = set()
    mod._cache_expires_at = 0


class TestLoadFromLocal:
    def test_loads_org_ids_from_json(self, tmp_path):
        f = tmp_path / "orgs.json"
        f.write_text(json.dumps({"organizations": [
            {"org_id": "abc-123", "name": "Org A"},
            {"org_id": "def-456", "name": "Org B"},
        ]}))
        result = _load_from_local(str(f))
        assert result == {"abc-123", "def-456"}

    def test_missing_file_returns_empty(self, tmp_path):
        result = _load_from_local(str(tmp_path / "nope.json"))
        assert result == set()

    def test_entries_without_org_id_skipped(self, tmp_path):
        f = tmp_path / "orgs.json"
        f.write_text(json.dumps({"organizations": [
            {"org_id": "abc-123", "name": "Org A"},
            {"name": "No ID"},
            {"org_id": "", "name": "Empty ID"},
        ]}))
        result = _load_from_local(str(f))
        assert result == {"abc-123"}


class TestIsOrgAllowed:
    def test_allowed_org(self):
        with patch.object(mod, "get_allowed_org_ids", return_value={"abc-123", "def-456"}):
            assert is_org_allowed("abc-123") is True

    def test_disallowed_org(self):
        with patch.object(mod, "get_allowed_org_ids", return_value={"abc-123"}):
            assert is_org_allowed("other-org") is False

    def test_none_org_id_rejected(self):
        with patch.object(mod, "get_allowed_org_ids", return_value={"abc-123"}):
            assert is_org_allowed(None) is False

    def test_empty_org_id_rejected(self):
        with patch.object(mod, "get_allowed_org_ids", return_value={"abc-123"}):
            assert is_org_allowed("") is False

    def test_empty_allowlist_rejects_all(self):
        with patch.object(mod, "get_allowed_org_ids", return_value=set()):
            assert is_org_allowed("abc-123") is False


class TestGetAllowedOrgIds:
    def test_caches_result(self):
        _reset_cache()
        org_ids = {"abc-123", "def-456"}
        with patch.object(mod, "_load_org_ids", return_value=org_ids) as mock_load:
            result1 = get_allowed_org_ids()
            result2 = get_allowed_org_ids()
        assert result1 == org_ids
        assert mock_load.call_count == 1  # second call used cache
        _reset_cache()

    def test_first_load_failure_returns_empty(self):
        _reset_cache()
        with patch.object(mod, "_load_org_ids", return_value=set()):
            result = get_allowed_org_ids()
        assert result == set()  # fail-closed: no fallback on cold cache
        _reset_cache()

    def test_keeps_stale_cache_on_load_failure(self):
        _reset_cache()
        # First load succeeds
        with patch.object(mod, "_load_org_ids", return_value={"abc-123"}):
            get_allowed_org_ids()

        # Force cache expiry
        mod._cache_expires_at = 0

        # Second load fails (returns empty)
        with patch.object(mod, "_load_org_ids", return_value=set()):
            result = get_allowed_org_ids()

        assert result == {"abc-123"}  # kept stale cache
        _reset_cache()
