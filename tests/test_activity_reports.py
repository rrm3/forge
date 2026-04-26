"""Regression tests for scripts/generate-activity-reports.py.

These tests lock in the behavior of `build_user_report` for the data-integrity
fixes shipped after the Week 5 incidents:

* `--user X --week N` must merge into the existing per-user report, not wipe
  weeks 1..N-1 (the bug that trashed 291 users on 2026-04-23).
* Full regen (target_week=None) must prune weeks the existing report has but
  current participation no longer covers, so deleted sessions can't leave
  zombie summaries on S3.
* The preflight digest helpers must distinguish per-user checks from the
  coarser directory-level check used for full-population batch runs.

Bedrock is mocked — these tests are pure logic, no LLM calls.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


# Load the script as a module. It lives in scripts/ which isn't a package.
_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate-activity-reports.py"
_spec = importlib.util.spec_from_file_location("generate_activity_reports", _SCRIPT_PATH)
generate_activity_reports = importlib.util.module_from_spec(_spec)
sys.modules["generate_activity_reports"] = generate_activity_reports
_spec.loader.exec_module(generate_activity_reports)


class _FakeBedrock:
    """Stub Bedrock client. Returns a canned JSON summary; never makes a network call."""

    def __init__(self, plan="planned X", accomplished="did Y", insights=None):
        self.plan = plan
        self.accomplished = accomplished
        self.insights = insights or []
        self.calls = 0

    def invoke_model(self, **_kwargs):
        self.calls += 1
        body = json.dumps({
            "plan": self.plan,
            "accomplished": self.accomplished,
            "insights": self.insights,
        })
        payload = {"content": [{"text": body}]}
        # Mimic the real Bedrock response shape: an object with .read().
        class _Body:
            def __init__(self, data):
                self._data = data

            def read(self):
                return self._data.encode()

        return {"body": _Body(json.dumps(payload))}


def _profile(uid="u-1"):
    return {
        "user_id": uid,
        "name": "Test User",
        "title": "Engineer",
        "department": "Tech",
        "team": "",
        "manager": "",
        "avatar_url": "",
        "intake_weeks": {},
    }


def _session(week: int, type_: str = "wrapup", count: int = 5):
    """Build a session dict that extract_participation will see as 'in week W'."""
    # Week N runs from PROGRAM_START_DATE + (N-1)*7 days. Pick a date inside the window.
    start = generate_activity_reports.PROGRAM_START_DATE
    from datetime import timedelta
    day = start + timedelta(weeks=week - 1, days=2)
    return {
        "type": type_,
        "program_week": week,
        "created_at": day.isoformat(),
        "updated_at": day.isoformat() + "T12:00:00",
        "message_count": count,
    }


# ---------------------------------------------------------------------------
# Existing-report merge: target_week MUST preserve weeks 1..N-1
# ---------------------------------------------------------------------------


class TestExistingReportMerge:
    """The 2026-04-23 incident: --week 5 silently wiped weeks 1-4 from S3 for 291 users.

    Root cause: existing report was only loaded when --incremental was set.
    Calling with --user X --week 5 (no --incremental) rebuilt the report
    starting from {} and wrote only week 5. Fix: load existing whenever the
    file is on disk, regardless of flags. These tests pin that behavior.
    """

    def test_target_week_preserves_prior_weeks(self):
        existing = {
            "user_id": "u-1",
            "name": "Test User",
            "weeks": {
                "1": {"plan": "wk1 plan", "accomplished": "wk1 acc", "insights": [],
                      "intake_completed": True, "wrapup_completed": True,
                      "session_count": 1, "other_session_count": 0, "message_count": 5,
                      "ideas_count": 0, "tips_shared": 0, "collabs_started": 0,
                      "tip_titles": [], "idea_titles": [], "collab_titles": []},
                "2": {"plan": "wk2 plan", "accomplished": "wk2 acc", "insights": [],
                      "intake_completed": True, "wrapup_completed": True,
                      "session_count": 1, "other_session_count": 0, "message_count": 5,
                      "ideas_count": 0, "tips_shared": 0, "collabs_started": 0,
                      "tip_titles": [], "idea_titles": [], "collab_titles": []},
            },
        }

        sessions = [_session(1), _session(2), _session(5)]

        report = generate_activity_reports.build_user_report(
            _FakeBedrock(plan="wk5 plan", accomplished="wk5 acc"),
            "u-1",
            _profile(),
            sessions,
            ideas=[],
            tips=[],
            collabs=[],
            max_week=5,
            target_week=5,
            existing_report=existing,
        )

        assert report is not None
        assert set(report["weeks"].keys()) == {"1", "2", "5"}, (
            "Partial regen must preserve weeks not being recomputed. "
            "If this fails, the existing-report-merge fix has regressed and "
            "we are about to trash users' historical activity."
        )
        # Prior weeks unchanged
        assert report["weeks"]["1"]["plan"] == "wk1 plan"
        assert report["weeks"]["2"]["plan"] == "wk2 plan"
        # Target week recomputed
        assert report["weeks"]["5"]["plan"] == "wk5 plan"

    def test_target_week_starts_fresh_when_no_existing_report(self):
        sessions = [_session(1), _session(2), _session(5)]

        report = generate_activity_reports.build_user_report(
            _FakeBedrock(),
            "u-1",
            _profile(),
            sessions,
            ideas=[],
            tips=[],
            collabs=[],
            max_week=5,
            target_week=5,
            existing_report=None,
        )

        # No existing report -> only the target week populates. (Other weeks
        # are not synthesized from sessions in target-week mode.)
        assert set(report["weeks"].keys()) == {"5"}


# ---------------------------------------------------------------------------
# Full-regen mode: prune weeks the existing report has but participation lost
# ---------------------------------------------------------------------------


class TestFullRegenPrune:
    """If a user's week-3 sessions get deleted (or the week falls out of
    participation for any other reason), a full regen must drop the stale
    week-3 summary instead of carrying it forward forever."""

    def test_full_regen_prunes_stale_weeks(self):
        existing = {
            "user_id": "u-1",
            "name": "Test User",
            "weeks": {
                "1": {"plan": "wk1", "accomplished": "wk1", "insights": [],
                      "intake_completed": True, "wrapup_completed": True,
                      "session_count": 1, "other_session_count": 0, "message_count": 5,
                      "ideas_count": 0, "tips_shared": 0, "collabs_started": 0,
                      "tip_titles": [], "idea_titles": [], "collab_titles": []},
                "3": {"plan": "stale", "accomplished": "stale", "insights": [],
                      "intake_completed": True, "wrapup_completed": True,
                      "session_count": 1, "other_session_count": 0, "message_count": 5,
                      "ideas_count": 0, "tips_shared": 0, "collabs_started": 0,
                      "tip_titles": [], "idea_titles": [], "collab_titles": []},
            },
        }

        # Live participation has weeks 1 and 5 — week 3 is gone.
        sessions = [_session(1), _session(5)]

        report = generate_activity_reports.build_user_report(
            _FakeBedrock(),
            "u-1",
            _profile(),
            sessions,
            ideas=[],
            tips=[],
            collabs=[],
            max_week=5,
            target_week=None,  # full regen
            existing_report=existing,
        )

        assert "3" not in report["weeks"], (
            "Full regen with no target_week must prune weeks not in current "
            "participation. Otherwise deleted-session zombies persist on S3."
        )
        assert set(report["weeks"].keys()) == {"1", "5"}

    def test_partial_regen_does_not_prune_other_weeks(self):
        """Conversely, target_week=5 should NOT prune week 3 from existing.
        Surgical mode trusts the operator's scope."""
        existing = {
            "user_id": "u-1",
            "name": "Test User",
            "weeks": {
                "3": {"plan": "stale", "accomplished": "stale", "insights": [],
                      "intake_completed": True, "wrapup_completed": True,
                      "session_count": 1, "other_session_count": 0, "message_count": 5,
                      "ideas_count": 0, "tips_shared": 0, "collabs_started": 0,
                      "tip_titles": [], "idea_titles": [], "collab_titles": []},
            },
        }

        # Live participation has only week 5.
        sessions = [_session(5)]

        report = generate_activity_reports.build_user_report(
            _FakeBedrock(),
            "u-1",
            _profile(),
            sessions,
            ideas=[],
            tips=[],
            collabs=[],
            max_week=5,
            target_week=5,
            existing_report=existing,
        )

        # Both weeks survive: 3 because partial-regen preserves it, 5 because
        # it was just computed.
        assert set(report["weeks"].keys()) == {"3", "5"}


# ---------------------------------------------------------------------------
# Preflight digest existence check
# ---------------------------------------------------------------------------


class TestDigestPreflight:
    """The preflight that aborts with exit 2 when digests are missing — and
    which must distinguish per-user checks from the directory-level check so
    a partial digest population can't pass the preflight just because the
    directory is non-empty."""

    def test_directory_check_detects_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(generate_activity_reports, "DATA_DIR", str(tmp_path))
        # Directory missing entirely.
        assert not generate_activity_reports._digest_exists_for_week(5)
        # Directory present but empty.
        (tmp_path / "digests" / "digest-week5").mkdir(parents=True)
        assert not generate_activity_reports._digest_exists_for_week(5)
        # One .md present -> passes.
        (tmp_path / "digests" / "digest-week5" / "any.md").write_text("# digest")
        assert generate_activity_reports._digest_exists_for_week(5)

    def test_per_user_check_narrows_to_specific_file(self, tmp_path, monkeypatch):
        """Critical adversarial finding #5: a partial-population digest dir
        (10 users digested of 291) must not pass the per-user preflight just
        because *someone else's* .md happens to exist."""
        monkeypatch.setattr(generate_activity_reports, "DATA_DIR", str(tmp_path))
        digest_dir = tmp_path / "digests" / "digest-week5"
        digest_dir.mkdir(parents=True)
        (digest_dir / "other-user.md").write_text("# other")

        # Specific user has no digest -> per-user preflight fails.
        assert not generate_activity_reports._digest_exists_for_week(5, user_id="me")
        # But the directory-level check passes (because some .md exists).
        assert generate_activity_reports._digest_exists_for_week(5)

        # Once the user's own digest exists, per-user preflight passes.
        (digest_dir / "me.md").write_text("# me")
        assert generate_activity_reports._digest_exists_for_week(5, user_id="me")

    def test_per_user_check_falls_back_to_s3_path(self, tmp_path, monkeypatch):
        """Adversarial finding #6: load_digest reads from two paths
        (digests/ and s3/profiles/). The preflight must mirror that fallback,
        otherwise we fail-closed when digests are present in the secondary
        path that the LLM would actually consume."""
        monkeypatch.setattr(generate_activity_reports, "DATA_DIR", str(tmp_path))
        s3_path = tmp_path / "s3" / "profiles" / "me" / "digest-week5.md"
        s3_path.parent.mkdir(parents=True)
        s3_path.write_text("# from s3 fallback")

        assert generate_activity_reports._digest_exists_for_week(5, user_id="me")
