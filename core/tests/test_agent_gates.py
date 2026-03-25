"""Tests for Agent gate system and evidence tracking."""
from __future__ import annotations

from mascarade.agents.base import Agent, EvidenceRecord, Gate, GateStatus
from mascarade.router.router import Strategy


def _make_agent(**overrides) -> Agent:
    defaults = {
        "name": "test-agent",
        "description": "A test agent",
        "system_prompt": "You are helpful.",
        "strategy": Strategy.BEST,
    }
    defaults.update(overrides)
    return Agent(**defaults)


class TestGateChecking:
    def test_no_gates_passes(self):
        agent = _make_agent()
        passed, failed = agent.check_gates("pre")
        assert passed is True
        assert failed == []

    def test_gate_with_no_check_auto_passes(self):
        agent = _make_agent(gates=[
            Gate(name="approval", phase="pre", required=True),
        ])
        passed, failed = agent.check_gates("pre")
        assert passed is True
        assert agent.gates[0].status == GateStatus.PASSED

    def test_gate_has_system_prompt_passes(self):
        agent = _make_agent(
            system_prompt="You are an expert.",
            gates=[Gate(name="prompt-check", phase="pre", check="has_system_prompt")],
        )
        passed, failed = agent.check_gates("pre")
        assert passed is True

    def test_gate_has_system_prompt_fails_when_empty(self):
        agent = _make_agent(
            system_prompt="",
            gates=[Gate(name="prompt-check", phase="pre", check="has_system_prompt")],
        )
        passed, failed = agent.check_gates("pre")
        assert passed is False
        assert "prompt-check" in failed

    def test_gate_has_skills_passes(self):
        agent = _make_agent(
            skills=["code-review"],
            gates=[Gate(name="skill-check", phase="pre", check="has_skills")],
        )
        passed, failed = agent.check_gates("pre")
        assert passed is True

    def test_gate_has_skills_fails(self):
        agent = _make_agent(
            skills=[],
            gates=[Gate(name="skill-check", phase="pre", check="has_skills")],
        )
        passed, failed = agent.check_gates("pre")
        assert passed is False

    def test_gate_has_tools_passes(self):
        agent = _make_agent(
            tools=["python", "bash"],
            gates=[Gate(name="tool-check", phase="pre", check="has_tools")],
        )
        passed, failed = agent.check_gates("pre")
        assert passed is True

    def test_gate_is_configured_passes(self):
        agent = _make_agent(
            preferred_provider="claude",
            gates=[Gate(name="config-check", phase="pre", check="is_configured")],
        )
        passed, failed = agent.check_gates("pre")
        assert passed is True

    def test_gate_is_configured_fails(self):
        agent = _make_agent(
            preferred_provider=None,
            gates=[Gate(name="config-check", phase="pre", check="is_configured")],
        )
        passed, failed = agent.check_gates("pre")
        assert passed is False

    def test_optional_gate_failure_does_not_block(self):
        agent = _make_agent(
            system_prompt="",
            gates=[
                Gate(name="optional-check", phase="pre", check="has_system_prompt", required=False),
            ],
        )
        passed, failed = agent.check_gates("pre")
        assert passed is True  # optional gate failure doesn't block
        assert failed == []
        assert agent.gates[0].status == GateStatus.FAILED

    def test_phase_filtering(self):
        agent = _make_agent(gates=[
            Gate(name="pre-gate", phase="pre", check="has_system_prompt"),
            Gate(name="post-gate", phase="post", check="has_tools"),
        ])
        # Check pre gates — system_prompt exists, so passes
        passed, _ = agent.check_gates("pre")
        assert passed is True
        # Post gate not checked yet
        assert agent.gates[1].status == GateStatus.PENDING

    def test_multiple_gates_mixed(self):
        agent = _make_agent(
            system_prompt="ok",
            preferred_provider=None,
            gates=[
                Gate(name="prompt-ok", phase="pre", check="has_system_prompt"),
                Gate(name="config-fail", phase="pre", check="is_configured"),
            ],
        )
        passed, failed = agent.check_gates("pre")
        assert passed is False
        assert "config-fail" in failed
        assert "prompt-ok" not in failed

    def test_unknown_check_passes(self):
        agent = _make_agent(gates=[
            Gate(name="custom", phase="pre", check="unknown_check_name"),
        ])
        passed, failed = agent.check_gates("pre")
        assert passed is True

    def test_reset_gates(self):
        agent = _make_agent(gates=[
            Gate(name="g1", phase="pre", status=GateStatus.PASSED),
            Gate(name="g2", phase="post", status=GateStatus.FAILED),
        ])
        agent.reset_gates()
        assert all(g.status == GateStatus.PENDING for g in agent.gates)


class TestEvidenceRecord:
    def test_create_evidence(self):
        agent = _make_agent(gates=[
            Gate(name="g1", phase="pre", status=GateStatus.PASSED),
            Gate(name="g2", phase="post", status=GateStatus.FAILED),
        ])
        # Manually set statuses
        agent.gates[0].status = GateStatus.PASSED
        agent.gates[1].status = GateStatus.FAILED

        evidence = agent.create_evidence(
            run_id="run-001",
            duration_ms=123.4,
            model="claude-sonnet-4-6",
        )

        assert isinstance(evidence, EvidenceRecord)
        assert evidence.run_id == "run-001"
        assert evidence.agent_name == "test-agent"
        assert evidence.duration_ms == 123.4
        assert "g1" in evidence.gates_passed
        assert "g2" in evidence.gates_failed
        assert evidence.metadata["model"] == "claude-sonnet-4-6"
        assert evidence.timestamp  # non-empty

    def test_evidence_with_no_gates(self):
        agent = _make_agent()
        evidence = agent.create_evidence(run_id="run-002")
        assert evidence.gates_passed == []
        assert evidence.gates_failed == []


class TestAgentGateIntegration:
    def test_agent_with_gates_and_skills(self):
        agent = _make_agent(
            skills=["code-review", "safety-review"],
            tools=["python"],
            preferred_provider="claude",
            gates=[
                Gate(name="has-skills", phase="pre", check="has_skills"),
                Gate(name="has-tools", phase="pre", check="has_tools"),
                Gate(name="is-configured", phase="pre", check="is_configured"),
            ],
        )
        passed, failed = agent.check_gates("pre")
        assert passed is True
        assert all(g.status == GateStatus.PASSED for g in agent.gates)

        evidence = agent.create_evidence(run_id="integration-001", duration_ms=50.0)
        assert len(evidence.gates_passed) == 3
        assert len(evidence.gates_failed) == 0
