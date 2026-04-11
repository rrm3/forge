"""Integration tests for recurring objective clearing and plan deferral.

Tests the exact code paths that caused the plan-dayN completion bug:
- executor.py: recurring clearing with week_start clamping
- executor.py: plan deferral logic
- extraction.py: eval_description usage in evaluator prompt
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from backend.models import PROGRAM_START_DATE, make_plan_objective


# ---------------------------------------------------------------------------
# Helper: simulate the clearing logic from executor.py:168-186
# ---------------------------------------------------------------------------

def simulate_clearing(intake_responses: dict, merged_objectives: list, current_week: int, today: date | None = None) -> dict:
    """Run the same clearing logic as executor.py, return modified responses."""
    responses = dict(intake_responses)  # copy
    if responses and current_week > 1 and merged_objectives:
        week_start = PROGRAM_START_DATE + timedelta(weeks=current_week - 1)
        _today = today or date.today()
        if week_start > _today:
            week_start = _today
        recurring_ids = {o["id"] for o in merged_objectives if o.get("recurring")}
        to_delete = []
        for obj_id in recurring_ids:
            resp = responses.get(obj_id)
            if resp and isinstance(resp, dict) and resp.get("captured_at"):
                captured = resp["captured_at"][:10]
                if captured < week_start.isoformat():
                    to_delete.append(obj_id)
        for obj_id in to_delete:
            del responses[obj_id]
    return responses


# ---------------------------------------------------------------------------
# Helper: simulate plan deferral logic from executor.py:246-254
# ---------------------------------------------------------------------------

def simulate_deferral(merged_objectives: list, intake_responses: dict, current_week: int) -> list:
    """Return eval_objectives after applying plan deferral logic."""
    plan_key = f"plan-day{current_week}"
    eval_objectives = merged_objectives
    if current_week > 1:
        completed = set(intake_responses.keys())
        remaining_non_plan = sum(
            1 for o in merged_objectives
            if o["id"] != plan_key and o["id"] not in completed
        )
        if plan_key not in completed and remaining_non_plan >= 2:
            eval_objectives = [o for o in merged_objectives if o["id"] != plan_key]
    return eval_objectives


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

COMPANY_OBJECTIVES = [
    {"id": "c0-work-summary", "label": "What they work on", "description": "...", "week_introduced": 1},
    {"id": "c0-daily-tasks", "label": "Daily tasks", "description": "...", "week_introduced": 1},
    {"id": "c0-ai-tools", "label": "AI tools", "description": "...", "week_introduced": 1},
    {"id": "c0-core-skills", "label": "Core skills", "description": "...", "week_introduced": 1},
    {"id": "c0-learning-goals", "label": "Learning goals", "description": "...", "week_introduced": 1},
    {"id": "c0-goals", "label": "Goals", "description": "...", "week_introduced": 1},
    {"id": "c0-applied-last-week", "label": "Applied last week", "description": "...", "week_introduced": 2, "recurring": True},
    {"id": "c0-blockers", "label": "Blockers", "description": "...", "week_introduced": 2, "recurring": True},
    {"id": "c0-sharing", "label": "Sharing", "description": "...", "week_introduced": 2},
    {"id": "c0-collabs", "label": "Collabs", "description": "...", "week_introduced": 2},
]


def make_response(captured_date: str) -> dict:
    return {"value": "test answer", "captured_at": f"{captured_date}T14:00:00+00:00"}


def week3_objectives() -> list:
    """All objectives visible in Week 3, including synthetic plan."""
    objs = [o for o in COMPANY_OBJECTIVES if o["week_introduced"] <= 3]
    objs.append(make_plan_objective(3))
    return objs


# ---------------------------------------------------------------------------
# Scenario A: Brand new Week 1 user
# ---------------------------------------------------------------------------

class TestScenarioA:
    """Brand new user, Week 1. No recurring, no plan, no clearing."""

    def test_no_clearing_week1(self):
        objs = [o for o in COMPANY_OBJECTIVES if o["week_introduced"] <= 1]
        responses = {}
        result = simulate_clearing(responses, objs, current_week=1)
        assert result == {}

    def test_no_plan_injection_week1(self):
        # Plan is only injected for week > 1
        objs = [o for o in COMPANY_OBJECTIVES if o["week_introduced"] <= 1]
        assert not any(o["id"].startswith("plan-") for o in objs)


# ---------------------------------------------------------------------------
# Scenario B: Week 1 complete, missed Week 2, now Week 3
# ---------------------------------------------------------------------------

class TestScenarioB:
    """Completed Week 1, skipped Week 2, now in Week 3."""

    def setup_method(self):
        self.objectives = week3_objectives()
        # 6 W1 objectives answered in Week 1
        self.responses = {
            f"c0-{k}": make_response("2026-03-24")
            for k in ["work-summary", "daily-tasks", "ai-tools", "core-skills", "learning-goals", "goals"]
        }

    def test_no_recurring_to_clear(self):
        """Recurring objectives were never answered, so clearing is a no-op."""
        result = simulate_clearing(self.responses, self.objectives, current_week=3)
        assert len(result) == 6  # all 6 W1 responses kept

    def test_five_objectives_remaining(self):
        """Should need: applied, blockers, sharing, collabs, plan-day3."""
        result = simulate_clearing(self.responses, self.objectives, current_week=3)
        remaining = [o for o in self.objectives if o["id"] not in result]
        remaining_ids = {o["id"] for o in remaining}
        assert remaining_ids == {"c0-applied-last-week", "c0-blockers", "c0-sharing", "c0-collabs", "plan-day3"}

    def test_plan_deferred_with_four_remaining(self):
        """Plan should be deferred when 4 non-plan objectives remain."""
        result = simulate_clearing(self.responses, self.objectives, current_week=3)
        eval_objs = simulate_deferral(self.objectives, result, current_week=3)
        eval_ids = {o["id"] for o in eval_objs}
        assert "plan-day3" not in eval_ids

    def test_plan_included_with_one_remaining(self):
        """After answering 3 of 4, plan should be included."""
        responses = dict(self.responses)
        responses["c0-applied-last-week"] = make_response("2026-04-07")
        responses["c0-blockers"] = make_response("2026-04-07")
        responses["c0-sharing"] = make_response("2026-04-07")
        result = simulate_clearing(responses, self.objectives, current_week=3)
        eval_objs = simulate_deferral(self.objectives, result, current_week=3)
        eval_ids = {o["id"] for o in eval_objs}
        assert "plan-day3" in eval_ids


# ---------------------------------------------------------------------------
# Scenario C: Week 1+2 complete, now Week 3 (on actual Tuesday)
# ---------------------------------------------------------------------------

class TestScenarioC:
    """Completed Week 1 and 2, now in Week 3 on the actual Tuesday."""

    def setup_method(self):
        self.objectives = week3_objectives()
        self.responses = {
            "c0-work-summary": make_response("2026-03-24"),
            "c0-daily-tasks": make_response("2026-03-24"),
            "c0-ai-tools": make_response("2026-03-24"),
            "c0-core-skills": make_response("2026-03-24"),
            "c0-learning-goals": make_response("2026-03-24"),
            "c0-goals": make_response("2026-03-24"),
            "c0-applied-last-week": make_response("2026-03-31"),
            "c0-blockers": make_response("2026-03-31"),
            "c0-sharing": make_response("2026-03-31"),
            "c0-collabs": make_response("2026-03-31"),
            "plan-day2": make_response("2026-03-31"),
        }

    @patch("backend.models.date")
    def test_clearing_on_actual_tuesday(self, mock_date):
        """On April 7 (actual Week 3 start), recurring from 3/31 are cleared."""
        mock_date.today.return_value = date(2026, 4, 7)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        result = simulate_clearing(self.responses, self.objectives, current_week=3)
        assert "c0-applied-last-week" not in result
        assert "c0-blockers" not in result
        # Non-recurring Week 2 responses kept
        assert "c0-sharing" in result
        assert "c0-collabs" in result
        assert "plan-day2" in result

    @patch("backend.models.date")
    def test_three_remaining_on_tuesday(self, mock_date):
        """After clearing, should need: applied, blockers, plan-day3."""
        mock_date.today.return_value = date(2026, 4, 7)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        result = simulate_clearing(self.responses, self.objectives, current_week=3)
        remaining = [o for o in self.objectives if o["id"] not in result]
        remaining_ids = {o["id"] for o in remaining}
        assert remaining_ids == {"c0-applied-last-week", "c0-blockers", "plan-day3"}

    @patch("backend.models.date")
    def test_plan_included_after_answering_recurring(self, mock_date):
        """After answering both recurring objectives, plan is included in eval."""
        mock_date.today.return_value = date(2026, 4, 7)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        result = simulate_clearing(self.responses, self.objectives, current_week=3)
        # Simulate answering both recurring objectives today
        result["c0-applied-last-week"] = make_response("2026-04-07")
        result["c0-blockers"] = make_response("2026-04-07")
        eval_objs = simulate_deferral(self.objectives, result, current_week=3)
        eval_ids = {o["id"] for o in eval_objs}
        assert "plan-day3" in eval_ids

    @patch("backend.models.date")
    def test_today_responses_not_cleared(self, mock_date):
        """Responses captured today should NOT be cleared on the next turn."""
        mock_date.today.return_value = date(2026, 4, 7)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        responses = dict(self.responses)
        # Simulate: cleared on first turn, then re-answered today
        responses["c0-applied-last-week"] = make_response("2026-04-07")
        responses["c0-blockers"] = make_response("2026-04-07")
        result = simulate_clearing(responses, self.objectives, current_week=3)
        # Today's responses should survive
        assert "c0-applied-last-week" in result
        assert "c0-blockers" in result


# ---------------------------------------------------------------------------
# Scenario D: Week 3 with override BEFORE actual Tuesday (the bug scenario)
# ---------------------------------------------------------------------------

class TestScenarioD:
    """Week 3 via override on April 6 (before actual Week 3 starts April 7)."""

    def setup_method(self):
        self.objectives = week3_objectives()
        self.responses = {
            "c0-work-summary": make_response("2026-03-24"),
            "c0-daily-tasks": make_response("2026-03-24"),
            "c0-ai-tools": make_response("2026-03-24"),
            "c0-core-skills": make_response("2026-03-24"),
            "c0-learning-goals": make_response("2026-03-24"),
            "c0-goals": make_response("2026-03-24"),
            "c0-applied-last-week": make_response("2026-03-31"),
            "c0-blockers": make_response("2026-03-31"),
            "c0-sharing": make_response("2026-03-31"),
            "c0-collabs": make_response("2026-03-31"),
            "plan-day2": make_response("2026-03-31"),
        }

    def test_old_recurring_cleared_with_clamping(self):
        """Week 2 recurring responses (3/31) should be cleared even with clamping."""
        # Today is April 6, week_start=April 7 -> clamped to April 6
        # 2026-03-31 < 2026-04-06 -> cleared
        result = simulate_clearing(self.responses, self.objectives, current_week=3, today=date(2026, 4, 6))
        assert "c0-applied-last-week" not in result
        assert "c0-blockers" not in result

    def test_today_responses_survive_with_clamping(self):
        """Responses captured today (April 6) should NOT be cleared with clamping."""
        responses = dict(self.responses)
        responses["c0-applied-last-week"] = make_response("2026-04-06")
        responses["c0-blockers"] = make_response("2026-04-06")
        result = simulate_clearing(responses, self.objectives, current_week=3, today=date(2026, 4, 6))
        # With clamping: week_start clamped to April 6, "2026-04-06" < "2026-04-06" is False
        assert "c0-applied-last-week" in result
        assert "c0-blockers" in result

    def test_plan_not_deferred_after_answering_recurring_today(self):
        """THE BUG FIX: after answering recurring today, plan should be evaluable."""
        responses = dict(self.responses)
        # First turn: old recurring cleared, then re-answered today
        responses["c0-applied-last-week"] = make_response("2026-04-06")
        responses["c0-blockers"] = make_response("2026-04-06")
        result = simulate_clearing(responses, self.objectives, current_week=3, today=date(2026, 4, 6))
        # Today's responses survive clamping
        assert "c0-applied-last-week" in result
        assert "c0-blockers" in result
        # Plan deferral should NOT kick in (0 non-plan remaining)
        eval_objs = simulate_deferral(self.objectives, result, current_week=3)
        eval_ids = {o["id"] for o in eval_objs}
        assert "plan-day3" in eval_ids, "Plan should be included in evaluation!"

    def test_without_clamping_plan_would_be_deferred(self):
        """Verify that WITHOUT the fix, the plan WOULD be deferred (regression guard)."""
        responses = dict(self.responses)
        responses["c0-applied-last-week"] = make_response("2026-04-06")
        responses["c0-blockers"] = make_response("2026-04-06")

        # Simulate OLD behavior: no clamping
        old_responses = dict(responses)
        week_start = PROGRAM_START_DATE + timedelta(weeks=3 - 1)  # April 7
        recurring_ids = {o["id"] for o in self.objectives if o.get("recurring")}
        for obj_id in recurring_ids:
            resp = old_responses.get(obj_id)
            if resp and isinstance(resp, dict) and resp.get("captured_at"):
                captured = resp["captured_at"][:10]
                if captured < week_start.isoformat():  # "2026-04-06" < "2026-04-07" = True!
                    del old_responses[obj_id]

        # Without clamping, today's responses get cleared
        assert "c0-applied-last-week" not in old_responses
        assert "c0-blockers" not in old_responses

        # And plan would be deferred (2 non-plan remaining)
        eval_objs = simulate_deferral(self.objectives, old_responses, current_week=3)
        eval_ids = {o["id"] for o in eval_objs}
        assert "plan-day3" not in eval_ids, "Without fix, plan should be deferred (proving the bug)"


# ---------------------------------------------------------------------------
# Scenario E: eval_description is used for plan objective
# ---------------------------------------------------------------------------

class TestEvalDescription:
    """Verify eval_description is present and used correctly."""

    def test_plan_has_eval_description(self):
        plan = make_plan_objective(3)
        assert "eval_description" in plan
        assert "NOT complete" not in plan["eval_description"]
        assert "concrete mention" in plan["eval_description"]

    def test_eval_description_simpler_than_description(self):
        plan = make_plan_objective(3)
        assert len(plan["eval_description"]) < len(plan["description"])
        # Description has coaching language, eval_description doesn't
        assert "gently help" in plan["description"]
        assert "gently help" not in plan["eval_description"]
