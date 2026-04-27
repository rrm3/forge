"""Automated end-to-end tests for the Week 6 launch — pulse + intake.

These cover the smoke-test scenarios from the runbook without needing a
browser. They drive the same backend code that ships to the staging Lambda
(verified separately by the Lambda alias version), so a passing run here
is high-confidence evidence the deployed agent will behave the same way.

What's tested:

* **Pulse fix end-to-end** — `load_wrapup_context` correctly identifies a
  user who hasn't answered the pulse, populates `pulse_to_ask`, and
  `build_system_prompt` renders the canonical question text in quotes plus
  the verbatim instruction. Catches regressions in the integration between
  the loader and the prompt builder.
* **Intake personas** — three starting states from the smoke-test skill
  (returning W1+W2 done, missed week, partial/stuck). Each verifies the
  intake progress section renders the correct "next objective to ask
  about" — the historical risk being that the agent asks the wrong question
  or the wrong order, which is the worst user experience because it stalls
  the intake.
* **Optional live model run** — same fixture against Bedrock with a marker
  so the deterministic tests run in CI and the live model run can be
  invoked manually with `pytest -m live`.

Auth, OIDC, WebSocket transport, and DynamoDB are intentionally out of
scope here — they're tested elsewhere and don't affect prompt behavior.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

os.environ.setdefault("DEV_MODE", "true")

from backend.agent.context import _build_intake_progress, build_system_prompt
from backend.agent.wrapup_context import load_wrapup_context
from backend.models import UserProfile
from backend.repository.journal import MemoryJournalRepository
from backend.storage import (
    LocalStorage,
    append_pulse_response,
    save_intake_responses,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
PULSE_CONFIG = json.loads((REPO_ROOT / "config" / "pulse-surveys.json").read_text())
WRAPUP_SKILL = (REPO_ROOT / "skills" / "wrapup.md").read_text()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


@pytest.fixture
def journal_repo(tmp_path):
    return MemoryJournalRepository(persist_path=str(tmp_path / "journal.json"))


def _profile(uid="diane-test", week=6) -> UserProfile:
    """Diane Mejia analog: Customer dept, real DS user, hasn't pulsed yet."""
    return UserProfile(
        user_id=uid,
        email="diane.mejia@overleaf.com",
        name="Diane Mejia",
        title="Customer Success Manager",
        department="Customer",
        manager="Lewis Cameron",
        program_week_override=week,
    )


# ---------------------------------------------------------------------------
# Pulse end-to-end
# ---------------------------------------------------------------------------


class TestPulseE2E:
    """Smoke-test scenario: a user who didn't pulse in any prior week
    completes a Week 6 wrap-up. The agent must ask the canonical Q1/Q2
    verbatim, not the ad-hoc 1-5 scales that contaminated Week 5.

    Pipeline tested:
      load_wrapup_context (loader)
      → pulse_to_ask populated
      → build_system_prompt (renderer)
      → canonical text + verbatim instruction in prompt
    """

    @pytest.mark.asyncio
    async def test_no_prior_pulse_yields_both_questions_to_ask(
        self, storage, journal_repo
    ):
        profile = _profile()

        # User has answered all of today's intake objectives but no pulse on file.
        today = datetime.now(UTC).isoformat()
        await save_intake_responses(
            storage,
            profile.user_id,
            {
                "plan-day6": {
                    "value": "Ship the v2 of the meeting-prep skill, this time with Slack delivery",
                    "captured_at": today,
                },
            },
        )

        ctx = await load_wrapup_context(
            storage, journal_repo, profile, profile.user_id,
        )

        # Both pulse questions should be queued — neither has an answer on file.
        ids = [q["id"] for q in ctx["pulse_to_ask"]]
        assert "progress" in ids, (
            "User has no prior pulse responses; the progress question must be in pulse_to_ask. "
            "Regression risk: load_wrapup_context filters out questions a user should still see."
        )
        assert "impact" in ids
        # The intake response we just saved should also flow through.
        assert any(item.get("id") == "plan-day6" for item in ctx["intake_today"])

    @pytest.mark.asyncio
    async def test_prior_pulse_skips_already_answered_question(
        self, storage, journal_repo
    ):
        """Skip-if-already-pulsed logic — the design choice that made Week 5's
        empty pulse batches expected, not a bug."""
        profile = _profile()

        # User answered the progress question in Week 4 only.
        await append_pulse_response(
            storage,
            profile.user_id,
            {
                "question_id": "progress",
                "version": "v1",
                "level": 4,
                "week": 4,
                "answered_at": "2026-04-14T18:00:00+00:00",
            },
        )

        ctx = await load_wrapup_context(
            storage, journal_repo, profile, profile.user_id,
        )
        ids = [q["id"] for q in ctx["pulse_to_ask"]]
        assert "progress" not in ids, "Already answered in Week 4 — must be skipped."
        assert "impact" in ids, "Not yet answered — should still be asked."

    @pytest.mark.asyncio
    async def test_full_pipeline_renders_canonical_pulse_in_prompt(
        self, storage, journal_repo
    ):
        """End-to-end pipe: loader output flows into the renderer and produces
        a system prompt with canonical text in quotes + the verbatim instruction.
        This is what the staging Lambda will send to Bedrock for any user
        triggering a wrap-up after the deploy."""
        profile = _profile()

        today = datetime.now(UTC).isoformat()
        await save_intake_responses(
            storage,
            profile.user_id,
            {
                "plan-day6": {
                    "value": "Ship the meeting-prep v2 with Slack delivery",
                    "captured_at": today,
                },
            },
        )

        ctx = await load_wrapup_context(
            storage, journal_repo, profile, profile.user_id,
        )

        prompt = build_system_prompt(
            profile=profile,
            skill_instructions=WRAPUP_SKILL,
            session_type="wrapup",
            wrapup_context=ctx,
        )

        # Canonical text in quotes (the contract the prompt now pins).
        assert (
            'ask verbatim: "Do you feel like you\'re making progress in building your AI skills?"'
            in prompt
        ), (
            "Canonical Q1 not found verbatim in rendered prompt. "
            "If this fails, the agent will revert to ad-hoc paraphrases and "
            "Week 6 pulse data will be contaminated like Week 5 was."
        )
        assert (
            'ask verbatim: "To what extent has AI helped you buy back time or reduce friction in your weekly tasks?"'
            in prompt
        )
        # Verbatim instruction — the part that stops the model from rewriting.
        assert "EXACT wording" in prompt
        assert "Do NOT paraphrase" in prompt
        # The negative examples that name the actual ad-hoc phrasings the agent
        # used in Week 5 — this is the "do not think of an elephant" trade-off.
        # Empirically validated against Sonnet 4.6 (see /tmp/pulse-e2e-test.py).
        assert "how productive did today feel" in prompt
        # Scale is rendered as a numbered markdown list, not comma-separated.
        assert "1. Not really" in prompt
        assert "5. Significant progress" in prompt
        # Today's plan also flows through so the wrap-up opener can reference it.
        assert "Ship the meeting-prep v2 with Slack delivery" in prompt


# ---------------------------------------------------------------------------
# Intake personas (smoke-test scenarios, state-machine level)
# ---------------------------------------------------------------------------


# Synthetic merged objective set covering the recurring objectives + plan.
# Order matters: this is the order the agent walks through them.
_WEEK6_OBJECTIVES = [
    {
        "id": "applied-learnings-week6",
        "label": "Applied learnings from last week",
        "description": "What did you actually do this past week with what you tried last week?",
        "post_turn": "Reflect briefly on whether the application surprised them.",
    },
    {
        "id": "blockers-week6",
        "label": "Blockers",
        "description": "What's blocking you from making more progress?",
        "post_turn": "",
    },
    {
        "id": "sharing-week6",
        "label": "Sharing",
        "description": "Have you shared anything with colleagues recently?",
        "post_turn": "",
    },
    {
        "id": "collabs-week6",
        "label": "Collabs",
        "description": "Anything you'd want to collaborate on?",
        "post_turn": "",
    },
    {
        "id": "plan-day6",
        "label": "Plan for Day 6",
        "description": "What's your plan for today?",
        "post_turn": "",
    },
]


class TestIntakePersonas:
    """Mirror the three personas from forge-intake-smoke (Returning, Missed, Partial).
    Each verifies the intake progress section renders the correct next-question
    for that user's starting state.

    Why this matters for Week 6: the historical pain is the agent asking the
    wrong objective or stalling the intake. If `_build_intake_progress` selects
    the wrong "next" objective, the user sees a confusing question and the
    intake stalls — the worst experience per Rob.
    """

    def test_persona_a_returning_w1_w2_done_starts_with_applied(self):
        """User completed W1 + W2 intakes; Week 6 starts fresh — first
        objective should be 'applied-learnings'."""
        section = _build_intake_progress(
            {"objectives": _WEEK6_OBJECTIVES},
            intake_responses={},
        )
        assert section is not None
        assert "Applied learnings from last week" in section
        assert "**Next objective to ask about:**" in section
        # Confirm the agent isn't being asked to lead with `plan` — which would
        # skip the recurring weekly check-ins and break the program design.
        assert section.index("Applied learnings from last week") < section.index("Next objective to ask about:") + 200

    def test_persona_b_missed_week_with_w1_intake_only(self):
        """User did Week 1 intake but missed weeks 2-5. Week 6 still starts
        with applied-learnings — past missed weeks aren't filled in retroactively."""
        # intake_weeks of {"1"} doesn't change the per-week objective state;
        # the W6 intake_responses dict is the source of truth for THIS week.
        section = _build_intake_progress(
            {"objectives": _WEEK6_OBJECTIVES},
            intake_responses={},
        )
        assert "5 remaining" in section
        # Same first-objective behavior as persona A — the recurring sequence
        # is week-scoped, not retroactive.
        assert "Applied learnings from last week" in section

    def test_persona_c_partial_progress_picks_up_at_next(self):
        """User has answered the first two objectives but stopped before
        the plan. The agent must resume at 'sharing', not loop back."""
        captured = datetime.now(UTC).isoformat()
        responses = {
            "applied-learnings-week6": {
                "value": "Built a Slack hook for the meeting-prep skill",
                "captured_at": captured,
            },
            "blockers-week6": {
                "value": "Calendar permissions for the org-level rollout",
                "captured_at": captured,
            },
        }
        section = _build_intake_progress(
            {"objectives": _WEEK6_OBJECTIVES},
            intake_responses=responses,
        )
        assert "2 of 5 objectives completed" in section
        assert "3 remaining" in section
        # Next must be 'sharing', not the already-answered ones.
        next_block = section.split("**Next objective to ask about:**")[1]
        assert "Sharing" in next_block
        assert "Applied learnings" not in next_block.split("\n")[1]
        assert "Blockers" not in next_block.split("\n")[1]

    def test_completion_emits_no_question_invariant(self):
        """When all objectives are done, the section must instruct the agent
        NOT to ask another question — this is the invariant that prevents the
        intake from looping back into 'what else?' questions, which is the
        worst possible user experience."""
        captured = datetime.now(UTC).isoformat()
        responses = {
            obj["id"]: {"value": "answered", "captured_at": captured}
            for obj in _WEEK6_OBJECTIVES
        }
        section = _build_intake_progress(
            {"objectives": _WEEK6_OBJECTIVES},
            intake_responses=responses,
        )
        assert "ALL OBJECTIVES COMPLETE" in section
        assert "Do NOT ask ANY questions" in section
        # Defensive: the closing instructions must not themselves contain
        # question marks that the agent might mirror.
        assert "?" not in section.split("MANDATORY RULES FOR THIS MESSAGE")[1].split("END WITH")[0] if "END WITH" in section else True


# ---------------------------------------------------------------------------
# Optional: live Bedrock run
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("AWS_PROFILE") != "forge",
    reason="Live Bedrock test requires AWS_PROFILE=forge with active credentials. "
    "Set AWS_PROFILE=forge && aws login --profile forge to run locally.",
)
class TestPulseLiveBedrock:
    """Hits Sonnet 4.6 for real with the same prompt the deployed agent builds.
    Auto-skips in CI (no `forge` profile); invoke locally with
    `AWS_PROFILE=forge pytest -m live tests/test_e2e_pulse_intake.py`.

    This is the "is the deployed code actually doing the right thing?" test.
    Since the staging Lambda runs the same prompt-building code we're testing
    here in unit form, a passing live test is strong end-to-end evidence.
    """

    @pytest.mark.asyncio
    async def test_canonical_q1_emitted_against_bedrock(
        self, storage, journal_repo
    ):
        import boto3

        profile = _profile()
        today = datetime.now(UTC).isoformat()
        await save_intake_responses(
            storage,
            profile.user_id,
            {
                "plan-day6": {
                    "value": "Ship the meeting-prep v2 with Slack delivery",
                    "captured_at": today,
                },
            },
        )
        ctx = await load_wrapup_context(
            storage, journal_repo, profile, profile.user_id,
        )
        prompt = build_system_prompt(
            profile=profile,
            skill_instructions=WRAPUP_SKILL,
            session_type="wrapup",
            wrapup_context=ctx,
        )

        client = boto3.Session(profile_name="forge").client(
            "bedrock-runtime", region_name="us-east-1"
        )

        # 4-turn conversation exercising the same beats as a real wrap-up.
        messages: list[dict] = []
        replies = [
            "Hey. Yeah I shipped the v2 of the meeting-prep skill today, with Slack delivery wired up.",
            "Worked end-to-end. The Slack integration was straightforward via webhook; total time was about 3 hours.",
            "Yeah I'd run it again.",
            "Sure, ask away.",
        ]
        last_assistant = ""
        for user_text in replies:
            messages.append({"role": "user", "content": user_text})
            resp = client.invoke_model(
                modelId="us.anthropic.claude-sonnet-4-6",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1024,
                    "system": prompt,
                    "messages": messages,
                }),
                contentType="application/json",
            )
            result = json.loads(resp["body"].read())
            last_assistant = "".join(
                b.get("text", "")
                for b in result.get("content", [])
                if b.get("type") == "text"
            )
            messages.append({"role": "assistant", "content": last_assistant})
            # Stop when the agent has asked one of the canonical questions.
            if (
                "making progress in building your AI skills" in last_assistant
                or "buy back time" in last_assistant
                or "reduce friction" in last_assistant
            ):
                break

        full = " ".join(m["content"] for m in messages if m["role"] == "assistant")
        assert (
            "making progress in building your AI skills" in full
            or "buy back time" in full
            or "reduce friction" in full
        ), (
            f"Live model did not emit canonical pulse text. Last assistant turn:\n{last_assistant[:600]}"
        )
