"""Tests for session-type prompt loading."""

import pytest
from backend.agent.skills import load_skill


class TestSessionTypePrompts:
    """Verify all session-type prompts load correctly."""

    def test_load_tip_prompt(self):
        content = load_skill("tip")
        assert content is not None
        assert "Tip" in content
        assert "prepare_tip" in content

    def test_load_stuck_prompt(self):
        content = load_skill("stuck")
        assert content is not None
        assert "Stuck" in content
        assert "read_profile" in content

    def test_load_brainstorm_prompt(self):
        content = load_skill("brainstorm")
        assert content is not None
        assert "Brainstorm" in content
        assert "propose_idea" in content

    def test_load_wrapup_prompt(self):
        content = load_skill("wrapup")
        assert content is not None
        assert "Wrap-up" in content
        assert "save_journal" in content

    def test_load_nonexistent_type(self):
        """Unknown session types should return None."""
        assert load_skill("nonexistent_type") is None

    def test_chat_type_has_no_prompt(self):
        """The 'chat' session type has no dedicated prompt file."""
        assert load_skill("chat") is None

    def test_all_prompts_have_tone_section(self):
        """Every session-type prompt should include a Tone section."""
        for session_type in ["tip", "stuck", "brainstorm", "wrapup"]:
            content = load_skill(session_type)
            assert content is not None, f"Failed to load {session_type}"
            assert "## Tone" in content, f"{session_type} prompt missing Tone section"

    def test_all_prompts_have_flow_section(self):
        """Every session-type prompt should include a flow/process section."""
        for session_type in ["tip", "stuck", "brainstorm", "wrapup"]:
            content = load_skill(session_type)
            assert content is not None, f"Failed to load {session_type}"
            has_flow = (
                "## Conversation Flow" in content
                or "## The Process" in content
            )
            assert has_flow, f"{session_type} prompt missing flow/process section"
