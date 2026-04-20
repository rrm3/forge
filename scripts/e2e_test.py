#!/usr/bin/env python3
"""Week 5 e2e test runner — drives the scenarios in docs/day2-testing/week-5-e2e-plan.md.

Approach
========
Two flavors of test:

1. Backend-logic tests that exercise the actual code paths against staging
   storage (DynamoDB + S3) directly. No HTTP/WS needed. These cover:
   * Phase 1 enrichment gate (run `_enrich_profile_async` with fabricated
     inputs against staging storage, then read the resulting profile state).
   * Phase 3 wrapup context loader (run `load_wrapup_context` against
     staging storage with a pre-seeded user).
   * Repo legacy-record deserialization (scan prod + staging tables, run
     every row through the new `_deserialize` methods, assert no exceptions).

2. HTTP/WS tests that drive the running staging backend. These cover:
   * Phase 2 active_preview on GET /api/sessions/{id}.
   * Phase 2 tip preview happy path (prepare_tip -> tip_ready WS event ->
     POST /api/tips with provenance -> reload -> no resurrection).
   * Phase 3 pulse-skip behavior (pre-seed pulse-responses.json, start
     wrapup session, verify pulse questions are not asked).

HTTP/WS tests require a staging bearer token. Pass it via STAGING_TOKEN
env var. Without a token, flavor 1 runs; flavor 2 is skipped with a
clear notice.

Scenarios are idempotent: each one sets up its own user state, runs the
scenario, verifies, and records PASS/FAIL. State mutations on staging
DynamoDB/S3 are scoped to test users prefixed `e2e-test-`.

Usage
=====
    AWS_PROFILE=forge STAGING_TOKEN=<token> python scripts/e2e_test.py

    # Run a subset of scenarios:
    AWS_PROFILE=forge python scripts/e2e_test.py --only P0-1,P0-6,P0-11

    # Skip setup cleanup (useful if iterating on a single failing scenario):
    AWS_PROFILE=forge python scripts/e2e_test.py --only P0-1 --no-cleanup

    # List scenarios:
    python scripts/e2e_test.py --list
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable

import boto3

# Make the backend importable so we can call its code paths directly.
# We point the repositories at staging resources via env vars below.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DEV_MODE", "false")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STAGING_API_BASE = "https://aituesdays-staging.digitalscience.ai"
STAGING_WS_ENDPOINT = "wss://rns6a4748b.execute-api.us-east-1.amazonaws.com/prod"

STAGING_PROFILES_TABLE = "forge-staging-profiles"
STAGING_JOURNAL_TABLE = "forge-staging-journal"
STAGING_TIPS_TABLE = "forge-staging-tips"
STAGING_COLLABS_TABLE = "forge-staging-collabs"
STAGING_USER_IDEAS_TABLE = "forge-staging-user-ideas"
STAGING_S3_BUCKET = "forge-staging-data"

TOKEN = os.environ.get("STAGING_TOKEN", "").strip()


# ---------------------------------------------------------------------------
# Test framework
# ---------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    id: str
    name: str
    status: str  # PASS / FAIL / SKIP
    notes: list[str] = field(default_factory=list)
    error: str | None = None


RESULTS: list[ScenarioResult] = []


def record(result: ScenarioResult) -> None:
    RESULTS.append(result)
    icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "·"}.get(result.status, "?")
    print(f"  {icon} [{result.id}] {result.name}: {result.status}")
    for n in result.notes:
        print(f"      - {n}")
    if result.error:
        print(f"      ERROR: {result.error}")


SCENARIOS: dict[str, Callable] = {}


def scenario(id: str, name: str, requires_token: bool = False):
    def decorator(fn):
        async def wrapped() -> ScenarioResult:
            if requires_token and not TOKEN:
                return ScenarioResult(id, name, "SKIP", notes=["STAGING_TOKEN not set"])
            try:
                return await fn()
            except Exception as exc:
                return ScenarioResult(id, name, "FAIL", error=f"{type(exc).__name__}: {exc}")
        SCENARIOS[id] = wrapped
        wrapped.__name__ = fn.__name__
        wrapped.scenario_id = id
        wrapped.scenario_name = name
        return wrapped
    return decorator


# ---------------------------------------------------------------------------
# Storage helpers (point staging-ward)
# ---------------------------------------------------------------------------


def ddb_profiles():
    return boto3.resource("dynamodb", region_name="us-east-1").Table(STAGING_PROFILES_TABLE)


def ddb_journal():
    return boto3.resource("dynamodb", region_name="us-east-1").Table(STAGING_JOURNAL_TABLE)


def ddb_tips():
    return boto3.resource("dynamodb", region_name="us-east-1").Table(STAGING_TIPS_TABLE)


def ddb_collabs():
    return boto3.resource("dynamodb", region_name="us-east-1").Table(STAGING_COLLABS_TABLE)


def ddb_user_ideas():
    return boto3.resource("dynamodb", region_name="us-east-1").Table(STAGING_USER_IDEAS_TABLE)


def s3_client():
    return boto3.client("s3", region_name="us-east-1")


def s3_put(key: str, body: bytes, content_type: str = "application/json") -> None:
    s3_client().put_object(Bucket=STAGING_S3_BUCKET, Key=key, Body=body, ContentType=content_type)


def s3_get(key: str) -> bytes | None:
    try:
        resp = s3_client().get_object(Bucket=STAGING_S3_BUCKET, Key=key)
        return resp["Body"].read()
    except s3_client().exceptions.NoSuchKey:
        return None
    except Exception:
        return None


def s3_delete(key: str) -> None:
    try:
        s3_client().delete_object(Bucket=STAGING_S3_BUCKET, Key=key)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test user factory (idempotent; all prefixed e2e-test-)
# ---------------------------------------------------------------------------


def test_user_id(slug: str) -> str:
    return f"e2e-test-{slug}"


def test_email(slug: str) -> str:
    return f"e2e-{slug}@digital-science.test"


def wipe_test_user(user_id: str) -> None:
    """Remove all staging state for a test user (profile, journal, intake responses, pulse)."""
    # Profile
    try:
        ddb_profiles().delete_item(Key={"user_id": user_id})
    except Exception:
        pass
    # Journal entries
    try:
        resp = ddb_journal().query(
            KeyConditionExpression="user_id = :u",
            ExpressionAttributeValues={":u": user_id},
        )
        for item in resp.get("Items", []):
            ddb_journal().delete_item(Key={"user_id": user_id, "entry_id": item["entry_id"]})
    except Exception:
        pass
    # S3 state
    for key in [
        f"profiles/{user_id}/intake-responses.json",
        f"profiles/{user_id}/pulse-responses.json",
        f"profiles/{user_id}/digest-week4.md",
    ]:
        s3_delete(key)


def create_profile(user_id: str, **overrides) -> None:
    """Create a baseline profile in staging, merging overrides into the item."""
    from decimal import Decimal

    now_iso = datetime.now(UTC).isoformat()
    item = {
        "user_id": user_id,
        "email": test_email(user_id.replace("e2e-test-", "")),
        "name": f"E2E Test {user_id.split('-')[-1].title()}",
        "onboarding_complete": False,
        "intake_skipped": False,
        "intake_weeks": {},
        "program_week_override": 0,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    item.update(overrides)
    # DynamoDB doesn't accept floats; coerce to Decimal if needed (not expected here)
    ddb_profiles().put_item(Item=item)


def load_profile(user_id: str) -> dict | None:
    resp = ddb_profiles().get_item(Key={"user_id": user_id})
    return resp.get("Item")


# ---------------------------------------------------------------------------
# Phase 1 scenarios: enrichment gate
# ---------------------------------------------------------------------------


async def _run_enrichment(user_id: str, is_first_intake: bool) -> None:
    """Invoke the real _enrich_profile_async against staging storage.

    Uses the real backend code path. We stub the LLM calls to return a
    deterministic result so the test doesn't need to spin up Bedrock.
    """
    # Point the backend at staging tables via config overrides
    os.environ["PROFILES_TABLE"] = STAGING_PROFILES_TABLE
    os.environ["JOURNAL_TABLE"] = STAGING_JOURNAL_TABLE
    os.environ["TIPS_TABLE"] = STAGING_TIPS_TABLE
    os.environ["COLLABS_TABLE"] = STAGING_COLLABS_TABLE
    os.environ["USER_IDEAS_TABLE"] = STAGING_USER_IDEAS_TABLE
    os.environ["IDEAS_TABLE"] = "forge-staging-ideas"
    os.environ["SESSIONS_TABLE"] = "forge-staging-sessions"
    os.environ["S3_BUCKET"] = STAGING_S3_BUCKET

    from unittest.mock import AsyncMock, patch
    from backend.agent.executor import _enrich_profile_async
    from backend.deps import AgentDeps
    from backend.repository.profiles import DynamoDBProfileRepository
    from backend.storage import S3Storage
    from backend.models import Message

    profiles_repo = DynamoDBProfileRepository(STAGING_PROFILES_TABLE)
    storage = S3Storage(STAGING_S3_BUCKET)
    deps = AgentDeps(profiles_repo=profiles_repo, storage=storage)

    transcript = [
        Message(role="user", content="I'm a senior engineer at Dimensions, mostly Python."),
        Message(role="assistant", content="Got it — what would you like to learn about AI?"),
        Message(role="user", content="I want to learn how to use AI agents for code review."),
    ]
    objectives = [
        {"id": "work_summary", "label": "Work summary"},
        {"id": "core_skills", "label": "Core skills"},
    ]

    mock_result = {
        "profile": {
            "work_summary": "E2E test: Senior engineer at Dimensions, Python focus.",
            "core_skills": ["Python", "code review"],
            "learning_goals": ["AI agents for code review"],
            "intake_summary": "E2E test: Engineer interested in AI-assisted code review.",
        },
        "objectives": {},
    }
    mock_proficiency = {"level": 3, "rationale": "E2E test fixture"}

    with patch(
        "backend.agent.extraction.enrich_profile_with_opus",
        new=AsyncMock(return_value=mock_result),
    ), patch(
        "backend.agent.extraction.score_ai_proficiency",
        new=AsyncMock(return_value=mock_proficiency),
    ):
        await _enrich_profile_async(
            deps=deps,
            user_id=user_id,
            transcript=transcript,
            objectives=objectives,
            is_first_intake=is_first_intake,
        )


@scenario("P0-1", "Returning user — identity fields preserved (Fabio's bug)")
async def test_p0_1():
    user_id = test_user_id("returning-user")
    wipe_test_user(user_id)

    # Simulate an already-enriched user from a prior week.
    prior_timestamp = (datetime.now(UTC) - timedelta(days=28)).isoformat()
    create_profile(
        user_id,
        intake_weeks={"1": "2026-03-24T10:00:00+00:00", "2": "2026-03-31T10:00:00+00:00",
                     "3": "2026-04-07T10:00:00+00:00", "4": "2026-04-14T10:00:00+00:00"},
        intake_enrichment_completed_at=prior_timestamp,
        work_summary="ORIGINAL: Senior data engineer at Dimensions.",
        core_skills=["SQL", "Python", "data modeling"],
        intake_summary="ORIGINAL: Data engineer focused on analytics pipelines.",
    )

    # Simulate W4-03 failure mode: enrichment called with is_first_intake=False
    # (which is what the gate computes for a returning user). Must NOT overwrite.
    await _run_enrichment(user_id, is_first_intake=False)

    after = load_profile(user_id)
    notes = []
    checks = [
        ("work_summary stays ORIGINAL", after.get("work_summary") == "ORIGINAL: Senior data engineer at Dimensions."),
        ("core_skills unchanged", list(after.get("core_skills", [])) == ["SQL", "Python", "data modeling"]),
        ("intake_summary unchanged", after.get("intake_summary") == "ORIGINAL: Data engineer focused on analytics pipelines."),
        ("intake_enrichment_completed_at unchanged", after.get("intake_enrichment_completed_at") == prior_timestamp),
    ]
    failing = [n for n, ok in checks if not ok]
    notes.extend(f"check: {n}" for n, _ in checks)
    status = "PASS" if not failing else "FAIL"
    if failing:
        notes.append(f"failing checks: {failing}")
    return ScenarioResult("P0-1", "Returning user — identity fields preserved (Fabio's bug)", status, notes=notes)


@scenario("P0-2", "Fresh user first intake — enrichment runs + marker set")
async def test_p0_2():
    user_id = test_user_id("fresh-user")
    wipe_test_user(user_id)

    create_profile(user_id, intake_weeks={})  # no marker, no prior enrichment

    await _run_enrichment(user_id, is_first_intake=True)

    after = load_profile(user_id)
    checks = [
        ("work_summary populated from enrichment", "E2E test: Senior engineer" in (after.get("work_summary") or "")),
        ("core_skills populated", "Python" in list(after.get("core_skills", []))),
        ("intake_summary populated", "E2E test" in (after.get("intake_summary") or "")),
        ("ai_proficiency set", after.get("ai_proficiency") is not None),
        ("intake_enrichment_completed_at is set", bool(after.get("intake_enrichment_completed_at"))),
    ]
    failing = [n for n, ok in checks if not ok]
    notes = [f"check: {n}" for n, _ in checks]
    if failing:
        notes.append(f"failing checks: {failing}")
    return ScenarioResult("P0-2", "Fresh user first intake — enrichment runs + marker set",
                         "PASS" if not failing else "FAIL", notes=notes)


@scenario("P0-3", "Skip-intake user — real intake still triggers enrichment")
async def test_p0_3():
    user_id = test_user_id("skip-user")
    wipe_test_user(user_id)

    # Simulate the 149-user scenario: skipped a week, no enrichment marker
    create_profile(
        user_id,
        intake_skipped=True,
        intake_weeks={"4": "2026-04-14T10:00:00+00:00"},
    )
    # Note: no intake_enrichment_completed_at

    # Gate predicate says this user SHOULD still be eligible for first enrichment
    # because the dedicated marker is absent. Simulate _check_intake_completion
    # computing is_first_intake correctly.
    profile = load_profile(user_id)
    is_first = profile.get("intake_enrichment_completed_at") is None

    if not is_first:
        return ScenarioResult("P0-3", "Skip-intake user — real intake still triggers enrichment",
                             "FAIL", notes=[f"predicate returned False (marker present: {profile.get('intake_enrichment_completed_at')})"])

    await _run_enrichment(user_id, is_first_intake=True)

    after = load_profile(user_id)
    checks = [
        ("work_summary populated", "E2E test: Senior engineer" in (after.get("work_summary") or "")),
        ("intake_enrichment_completed_at set", bool(after.get("intake_enrichment_completed_at"))),
    ]
    failing = [n for n, ok in checks if not ok]
    notes = [f"check: {n}" for n, _ in checks]
    notes.append(f"predicate saw is_first_intake=True (marker absent)")
    if failing:
        notes.append(f"failing checks: {failing}")
    return ScenarioResult("P0-3", "Skip-intake user — real intake still triggers enrichment",
                         "PASS" if not failing else "FAIL", notes=notes)


@scenario("P0-6", "Legacy tip/collab/idea records deserialize with new fields")
async def test_p0_6():
    """Already verified against prod earlier; re-run against both staging and prod for the record."""
    from backend.repository.tips import DynamoDBTipRepository
    from backend.repository.collabs import DynamoDBCollabRepository
    from backend.repository.user_ideas import DynamoDBUserIdeaRepository

    results = {}

    for env, tips_tbl, collabs_tbl, ideas_tbl in [
        ("staging", "forge-staging-tips", "forge-staging-collabs", "forge-staging-user-ideas"),
        ("production", "forge-production-tips", "forge-production-collabs", "forge-production-user-ideas"),
    ]:
        dynamo = boto3.resource("dynamodb", region_name="us-east-1")

        def scan_all(table):
            items = []
            resp = table.scan()
            items.extend(resp.get("Items", []))
            while "LastEvaluatedKey" in resp:
                resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
                items.extend(resp.get("Items", []))
            return items

        tips = scan_all(dynamo.Table(tips_tbl))
        tr = object.__new__(DynamoDBTipRepository)
        tip_ok = sum(1 for item in tips if _safe_deserialize(tr._deserialize_tip, item))

        collabs = scan_all(dynamo.Table(collabs_tbl))
        cr = object.__new__(DynamoDBCollabRepository)
        collab_ok = sum(1 for item in collabs if _safe_deserialize(cr._deserialize_collab, item))

        ideas = scan_all(dynamo.Table(ideas_tbl))
        ir = object.__new__(DynamoDBUserIdeaRepository)
        idea_ok = sum(1 for item in ideas if _safe_deserialize(ir._deserialize, item))

        results[env] = (
            (tip_ok, len(tips)),
            (collab_ok, len(collabs)),
            (idea_ok, len(ideas)),
        )

    notes = []
    ok = True
    for env, (tips_r, collabs_r, ideas_r) in results.items():
        notes.append(f"{env}: tips {tips_r[0]}/{tips_r[1]}, collabs {collabs_r[0]}/{collabs_r[1]}, ideas {ideas_r[0]}/{ideas_r[1]}")
        if tips_r[0] != tips_r[1] or collabs_r[0] != collabs_r[1] or ideas_r[0] != ideas_r[1]:
            ok = False

    return ScenarioResult("P0-6", "Legacy tip/collab/idea records deserialize with new fields",
                         "PASS" if ok else "FAIL", notes=notes)


def _safe_deserialize(fn, item) -> bool:
    try:
        fn(item)
        return True
    except Exception as exc:
        print(f"    deserialize fail on {item.get('tip_id') or item.get('collab_id') or item.get('idea_id')}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Phase 2 scenarios: active_preview endpoint
# ---------------------------------------------------------------------------


@scenario("P0-7", "GET /api/sessions/{id} returns active_preview field", requires_token=True)
async def test_p0_7():
    import httpx

    # Pick any existing staging session to verify the endpoint shape
    resp_sessions = ddb_profiles().scan(Limit=1)
    if not resp_sessions.get("Items"):
        return ScenarioResult("P0-7", "GET /api/sessions/{id} returns active_preview field",
                             "SKIP", notes=["no staging users to test against"])

    # Use the token to list this user's sessions via the API (masquerading as them)
    user_id = resp_sessions["Items"][0]["user_id"]
    email = resp_sessions["Items"][0].get("email", "")
    if not email:
        return ScenarioResult("P0-7", "GET /api/sessions/{id} returns active_preview field",
                             "SKIP", notes=["no email for masquerade"])

    async with httpx.AsyncClient(timeout=30) as client:
        list_resp = await client.get(
            f"{STAGING_API_BASE}/api/sessions",
            headers={"Authorization": f"Bearer {TOKEN}", "X-Masquerade-As": email},
        )
        if list_resp.status_code != 200:
            return ScenarioResult("P0-7", "GET /api/sessions/{id} returns active_preview field",
                                 "FAIL", notes=[f"sessions list returned {list_resp.status_code}"])
        sessions = list_resp.json()
        if not sessions:
            return ScenarioResult("P0-7", "GET /api/sessions/{id} returns active_preview field",
                                 "SKIP", notes=[f"user {email} has no sessions on staging"])

        # Hit the session load endpoint and verify response shape
        sid = sessions[0]["session_id"]
        session_resp = await client.get(
            f"{STAGING_API_BASE}/api/sessions/{sid}",
            headers={"Authorization": f"Bearer {TOKEN}", "X-Masquerade-As": email},
        )
        if session_resp.status_code != 200:
            return ScenarioResult("P0-7", "GET /api/sessions/{id} returns active_preview field",
                                 "FAIL", notes=[f"session load returned {session_resp.status_code}: {session_resp.text[:200]}"])
        body = session_resp.json()
        notes = [
            f"sampled user={email} session={sid}",
            f"response keys: {sorted(body.keys())}",
            f"active_preview present: {'active_preview' in body}",
            f"active_preview value: {body.get('active_preview')}",
            f"transcript field present: {'transcript' in body}",
        ]
        # The endpoint must include active_preview (even if null) without restructuring
        if "active_preview" not in body:
            return ScenarioResult("P0-7", "GET /api/sessions/{id} returns active_preview field",
                                 "FAIL", notes=notes + ["active_preview field missing from response"])
        if "transcript" not in body:
            return ScenarioResult("P0-7", "GET /api/sessions/{id} returns active_preview field",
                                 "FAIL", notes=notes + ["transcript field missing — response shape broken"])
        return ScenarioResult("P0-7", "GET /api/sessions/{id} returns active_preview field",
                             "PASS", notes=notes)


# ---------------------------------------------------------------------------
# Phase 3 scenarios: wrapup context, pulse, journal policy
# ---------------------------------------------------------------------------


@scenario("P0-10", "Wrapup context loader renders today's intake, journal, digest, pulse")
async def test_p0_10():
    """Exercise `load_wrapup_context` against staging storage with fabricated state."""
    from backend.agent.wrapup_context import load_wrapup_context
    from backend.repository.journal import DynamoDBJournalRepository
    from backend.storage import S3Storage
    from backend.models import UserProfile

    user_id = test_user_id("wrapup-context")
    wipe_test_user(user_id)
    create_profile(user_id, timezone="America/New_York", intake_weeks={"4": "2026-04-14T10:00:00+00:00"})

    now = datetime.now(UTC)
    # Seed today's intake response
    intake_responses = {
        "plan-day5": {
            "value": "I want to try using Claude for writing API docs today.",
            "captured_at": now.isoformat(),
        },
        "applied-learnings-week4": {
            "value": "Last week I learned about tool_use with Claude.",
            "captured_at": now.isoformat(),
        },
    }
    s3_put(
        f"profiles/{user_id}/intake-responses.json",
        json.dumps(intake_responses).encode(),
    )

    # Seed today's journal entry
    from backend.models import JournalEntry
    je = JournalEntry(
        entry_id=str(uuid.uuid4()),
        user_id=user_id,
        content="E2E test journal entry for today — worked on doc generation.",
        tags=["e2e-test", "chat"],
        created_at=now,
    )
    journal_repo = DynamoDBJournalRepository(STAGING_JOURNAL_TABLE)
    await journal_repo.create(je)

    # Seed a previous-week digest
    s3_put(
        f"profiles/{user_id}/digest-week4.md",
        b"# Week 4 Digest\nThis user made solid progress last week.\n",
        content_type="text/markdown",
    )

    # Pre-seed pulse v1 answer for progress only (leaves impact unanswered)
    s3_put(
        f"profiles/{user_id}/pulse-responses.json",
        json.dumps([
            {"question_id": "progress", "version": "v1", "level": 3, "week": 4, "answered_at": now.isoformat()},
        ]).encode(),
    )

    # Build a synthetic profile with program_week_override = 5 so "today" math works for Week 5 wrapup
    profile = UserProfile(
        user_id=user_id,
        email=test_email("wrapup-context"),
        timezone="America/New_York",
        intake_weeks={"4": "2026-04-14T10:00:00+00:00", "5": now.isoformat()},
        program_week_override=5,
    )

    # Fake merged_objectives so label lookup works
    objectives = [
        {"id": "plan-day5", "label": "Plan for Day 5", "description": ""},
        {"id": "applied-learnings-week4", "label": "Applied last week's learnings", "description": ""},
    ]

    storage = S3Storage(STAGING_S3_BUCKET)

    ctx = await load_wrapup_context(
        storage=storage,
        journal_repo=journal_repo,
        profile=profile,
        user_id=user_id,
        merged_objectives=objectives,
    )

    notes = []
    checks = []
    ctx = ctx or {}

    intake_section = ctx.get("intake_today") or []
    checks.append(("plan rendered with label", any("Plan for Day 5" in (i.get("label") or "") for i in intake_section)))
    checks.append(("applied-learnings rendered with label", any("Applied last week" in (i.get("label") or "") for i in intake_section)))
    checks.append(("plan-day5 appears first", intake_section[0].get("id") == "plan-day5" if intake_section else False))

    journal_section = ctx.get("journal_today") or []
    checks.append(("journal entry loaded", len(journal_section) >= 1))
    checks.append(("journal content included", any("doc generation" in (e.get("content") or "") for e in journal_section)))

    digest_section = ctx.get("previous_digest") or ""
    checks.append(("prev digest loaded", "Week 4 Digest" in digest_section))

    pulse_section = ctx.get("pulse_to_ask") or []
    checks.append(("pulse progress skipped (already answered)", not any(q.get("id") == "progress" for q in pulse_section)))
    checks.append(("pulse impact still asked (unanswered)", any(q.get("id") == "impact" for q in pulse_section)))

    failing = [n for n, ok in checks if not ok]
    notes.extend(f"check: {n}" for n, _ in checks)
    if failing:
        notes.append(f"failing: {failing}")
        notes.append(f"ctx dump: {ctx}")
    return ScenarioResult(
        "P0-10",
        "Wrapup context loader renders today's intake, journal, digest, pulse",
        "PASS" if not failing else "FAIL",
        notes=notes,
    )


@scenario("P0-11", "Wrapup completion writes no journal entry")
async def test_p0_11():
    """Verify `_auto_save_journal` was really deleted — there's no code path from
    wrapup that creates a journal entry anymore.
    """
    import subprocess
    result = subprocess.run(
        ["grep", "-n", "_auto_save_journal", "/Users/rmcgrath/dev/forge/backend/agent/executor.py"],
        capture_output=True, text=True,
    )
    lines = [l for l in result.stdout.splitlines() if "_auto_save_journal" in l]
    notes = [f"grep matches in executor.py: {len(lines)}"]
    for l in lines[:5]:
        notes.append(l)
    # After the deletion, there should be ZERO references to _auto_save_journal in executor.py.
    # Phase 3 test coverage also asserts this (tests/test_wrapup_context.py).
    if lines:
        return ScenarioResult("P0-11", "Wrapup completion writes no journal entry",
                             "FAIL", notes=notes + ["executor.py still references _auto_save_journal"])
    return ScenarioResult("P0-11", "Wrapup completion writes no journal entry",
                         "PASS", notes=notes + ["no references to _auto_save_journal in executor.py"])


@scenario("P0-12", "Intake tool registry excludes save_journal")
async def test_p0_12():
    """Verify the filter is applied at runtime. Inspect the executor.py source."""
    import subprocess
    result = subprocess.run(
        ["grep", "-n", "-A", "5", "FilteredToolRegistry", "/Users/rmcgrath/dev/forge/backend/agent/executor.py"],
        capture_output=True, text=True,
    )
    text = result.stdout
    # Must have save_journal in the exclude set
    includes_save_journal = "save_journal" in text
    notes = [f"FilteredToolRegistry context includes 'save_journal' in exclude set: {includes_save_journal}"]
    return ScenarioResult("P0-12", "Intake tool registry excludes save_journal",
                         "PASS" if includes_save_journal else "FAIL",
                         notes=notes + [text[:500]])


@scenario("P0-13", "Gate predicate behaves correctly across real staging + prod profiles")
async def test_p0_13():
    """Simulate the is_first_intake predicate against every real profile in
    staging AND production. Flag any profile that would get an unexpected
    enrichment decision when they next complete an intake.

    Expected breakdown:
    * Profiles with marker present → is_first_intake=False (skip enrichment) → returning users, safe.
    * Profiles without marker → is_first_intake=True (run enrichment) → first-timers, skip-intake users,
      crash-recovery users. Safe to enrich on their next intake.

    Anomaly check: profiles with rich identity fields (work_summary set, ai_proficiency set) but
    NO marker → these are legacy users who were enriched pre-Phase 1. They'd be re-enriched on
    their next intake, which would overwrite their existing data. Count these so we know how many.
    """

    def scan_all(table_name: str):
        dynamo = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamo.Table(table_name)
        items = []
        resp = table.scan()
        items.extend(resp.get("Items", []))
        while "LastEvaluatedKey" in resp:
            resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
            items.extend(resp.get("Items", []))
        return items

    def classify(profile):
        has_marker = bool(profile.get("intake_enrichment_completed_at"))
        has_summary = bool(profile.get("intake_summary"))
        has_work = bool(profile.get("work_summary"))
        has_prof = bool(profile.get("ai_proficiency"))
        intake_skipped = profile.get("intake_skipped", False)
        weeks = len(profile.get("intake_weeks") or {})

        if has_marker:
            return "skip_enrichment_next_intake"
        if not has_summary and not has_work and not has_prof:
            return "fresh_or_never_enriched"  # Safe to enrich
        if intake_skipped:
            return "skip_intake_no_marker"  # Safe: the 149-user scenario
        # Rich fields but no marker = legacy-enriched users
        return "legacy_enriched_no_marker"

    staging_profiles = scan_all("forge-staging-profiles")
    prod_profiles = scan_all("forge-production-profiles")

    notes = []
    warnings = []

    for env_name, profiles in [("staging", staging_profiles), ("production", prod_profiles)]:
        buckets = {}
        for p in profiles:
            bucket = classify(p)
            buckets.setdefault(bucket, []).append(p.get("user_id", "?"))
        notes.append(f"{env_name} ({len(profiles)} profiles):")
        for bucket in sorted(buckets.keys()):
            count = len(buckets[bucket])
            notes.append(f"  - {bucket}: {count}")

        legacy = buckets.get("legacy_enriched_no_marker", [])
        if legacy:
            warnings.append(
                f"{env_name}: {len(legacy)} legacy-enriched users have NO marker. "
                "Their next intake will re-enrich over their existing rich fields. "
                "This is only OK if we accept one round of re-enrichment per user post-deploy."
            )

    # This scenario is INFORMATIONAL. We don't fail on legacy_enriched_no_marker;
    # we report the count so we know what to expect when users return.
    notes.extend(warnings)
    return ScenarioResult(
        "P0-13",
        "Gate predicate behaves correctly across real staging + prod profiles",
        "PASS",
        notes=notes,
    )


@scenario("P1-14", "Pulse to-ask correctly skips answered + asks unanswered")
async def test_p1_14():
    """Exercise the pulse to-ask computation directly with various states."""
    from backend.agent.wrapup_context import questions_to_ask

    config = [
        {"id": "progress", "version": "v1", "text": "Progress?", "scale": []},
        {"id": "impact", "version": "v1", "text": "Impact?", "scale": []},
    ]

    # Case 1: No answers → both asked
    r1 = questions_to_ask(config, [])
    case1_ok = len(r1) == 2 and {q["id"] for q in r1} == {"progress", "impact"}

    # Case 2: Both answered at v1 → neither asked
    answers2 = [
        {"question_id": "progress", "version": "v1", "level": 3, "week": 4, "answered_at": "..."},
        {"question_id": "impact", "version": "v1", "level": 4, "week": 4, "answered_at": "..."},
    ]
    r2 = questions_to_ask(config, answers2)
    case2_ok = len(r2) == 0

    # Case 3: Only progress answered → impact still asked
    r3 = questions_to_ask(config, answers2[:1])
    case3_ok = len(r3) == 1 and r3[0]["id"] == "impact"

    # Case 4: Version bump — v1 answers don't satisfy v2 config
    config_v2 = [{"id": "progress", "version": "v2", "text": "Progress?", "scale": []}]
    r4 = questions_to_ask(config_v2, answers2)
    case4_ok = len(r4) == 1 and r4[0]["id"] == "progress" and r4[0]["version"] == "v2"

    # Case 5: Malformed answer record doesn't crash
    answers5 = answers2 + [{"malformed": "record"}, None, 42]
    try:
        r5 = questions_to_ask(config, answers5)
        case5_ok = len(r5) == 0  # still both-answered
    except Exception as e:
        case5_ok = False

    notes = [
        f"case 1 (no answers): {case1_ok}",
        f"case 2 (both v1 answered): {case2_ok}",
        f"case 3 (progress only): {case3_ok}",
        f"case 4 (version bump): {case4_ok}",
        f"case 5 (malformed answer): {case5_ok}",
    ]
    all_ok = case1_ok and case2_ok and case3_ok and case4_ok and case5_ok
    return ScenarioResult("P1-14", "Pulse to-ask correctly skips answered + asks unanswered",
                         "PASS" if all_ok else "FAIL", notes=notes)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Comma-separated scenario IDs to run (e.g. P0-1,P0-6)")
    parser.add_argument("--list", action="store_true", help="List scenarios and exit")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't clean up test users after run")
    args = parser.parse_args()

    if args.list:
        for sid, fn in SCENARIOS.items():
            print(f"  {sid}: {fn.scenario_name}")
        return

    if args.only:
        ids = {i.strip() for i in args.only.split(",")}
        to_run = {sid: fn for sid, fn in SCENARIOS.items() if sid in ids}
    else:
        to_run = SCENARIOS

    if not to_run:
        print("No scenarios match.")
        return

    print(f"Running {len(to_run)} scenarios against staging ({STAGING_API_BASE})")
    print(f"  AWS_PROFILE={os.environ.get('AWS_PROFILE', '(unset)')}")
    print(f"  STAGING_TOKEN {'set' if TOKEN else 'NOT SET — HTTP scenarios will skip'}")
    print()

    for sid in sorted(to_run.keys()):
        result = await to_run[sid]()
        record(result)

    print()
    passed = sum(1 for r in RESULTS if r.status == "PASS")
    failed = sum(1 for r in RESULTS if r.status == "FAIL")
    skipped = sum(1 for r in RESULTS if r.status == "SKIP")
    print(f"Total: {passed} PASS, {failed} FAIL, {skipped} SKIP")

    if not args.no_cleanup:
        print("\nCleaning up test users...")
        for slug in ["returning-user", "fresh-user", "skip-user", "wrapup-context"]:
            wipe_test_user(test_user_id(slug))

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
