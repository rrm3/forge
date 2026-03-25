"""Tests for backend/allowed_domains.py."""

import json
from unittest.mock import patch

from backend.allowed_domains import (
    _load_from_local,
    get_allowed_domains,
    is_domain_allowed,
)
import backend.allowed_domains as mod


def _reset_cache():
    """Clear the module-level cache between tests."""
    mod._cached_domains = set()
    mod._cache_expires_at = 0


class TestLoadFromLocal:
    def test_loads_domains_from_json(self, tmp_path):
        f = tmp_path / "domains.json"
        f.write_text(json.dumps({"domains": ["example.com", "Corp.Net"]}))
        result = _load_from_local(str(f))
        assert result == {"example.com", "corp.net"}

    def test_missing_file_returns_empty(self, tmp_path):
        result = _load_from_local(str(tmp_path / "nope.json"))
        assert result == set()

    def test_empty_domains_skipped(self, tmp_path):
        f = tmp_path / "domains.json"
        f.write_text(json.dumps({"domains": ["ok.com", "", "  "]}))
        result = _load_from_local(str(f))
        assert result == {"ok.com"}


class TestIsDomainAllowed:
    def test_allowed_domain(self):
        with patch.object(mod, "get_allowed_domains", return_value={"digital-science.com", "readcube.com"}):
            assert is_domain_allowed("rob@digital-science.com") is True

    def test_disallowed_domain(self):
        with patch.object(mod, "get_allowed_domains", return_value={"digital-science.com"}):
            assert is_domain_allowed("hacker@evil.com") is False

    def test_case_insensitive(self):
        with patch.object(mod, "get_allowed_domains", return_value={"digital-science.com"}):
            assert is_domain_allowed("Rob@Digital-Science.COM") is True

    def test_no_at_sign_rejected(self):
        with patch.object(mod, "get_allowed_domains", return_value={"digital-science.com"}):
            assert is_domain_allowed("notanemail") is False

    def test_empty_allowlist_rejects_all(self):
        with patch.object(mod, "get_allowed_domains", return_value=set()):
            assert is_domain_allowed("user@digital-science.com") is False


class TestGetAllowedDomains:
    def test_caches_result(self):
        _reset_cache()
        domains = {"a.com", "b.com"}
        with patch.object(mod, "_load_domains", return_value=domains) as mock_load:
            result1 = get_allowed_domains()
            result2 = get_allowed_domains()
        assert result1 == domains
        assert mock_load.call_count == 1  # second call used cache
        _reset_cache()

    def test_first_load_failure_returns_empty(self):
        _reset_cache()
        with patch.object(mod, "_load_domains", return_value=set()):
            result = get_allowed_domains()
        assert result == set()  # fail-closed: no fallback on cold cache
        _reset_cache()

    def test_keeps_stale_cache_on_load_failure(self):
        _reset_cache()
        # First load succeeds
        with patch.object(mod, "_load_domains", return_value={"ok.com"}):
            get_allowed_domains()

        # Force cache expiry
        mod._cache_expires_at = 0

        # Second load fails (returns empty)
        with patch.object(mod, "_load_domains", return_value=set()):
            result = get_allowed_domains()

        assert result == {"ok.com"}  # kept stale cache
        _reset_cache()
