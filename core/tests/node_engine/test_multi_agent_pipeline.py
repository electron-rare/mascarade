"""E2E tests for multi-agent pipeline scenarios.

Tests the Kill_LIFE-style pipeline: PM -> Architect -> Firmware -> QA
using the Agent dataclass with the new Kill_LIFE fields.
"""

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.router.router import Strategy


class TestAgentKillLIFEFields:
    """Test new Kill_LIFE fields on Agent dataclass."""

    def test_category_field(self):
        agent = Agent(
            name="test", description="test", system_prompt="test", category="firmware"
        )
        assert agent.category == "firmware"

    def test_enabled_default_true(self):
        agent = Agent(name="test", description="test", system_prompt="test")
        assert agent.enabled is True

    def test_gate_fields(self):
        agent = Agent(
            name="qa-agent",
            description="QA",
            system_prompt="test",
            gate_before="S0_spec_validation",
            gate_after="S1_test_coverage",
        )
        assert agent.gate_before == "S0_spec_validation"
        assert agent.gate_after == "S1_test_coverage"

    def test_evidence_refs(self):
        agent = Agent(
            name="test",
            description="test",
            system_prompt="test",
            evidence_refs=["artifacts/arch/02_arch.md", "artifacts/QA/report.json"],
        )
        assert len(agent.evidence_refs) == 2

    def test_skills_list(self):
        agent = Agent(
            name="test",
            description="test",
            system_prompt="test",
            skills=["code-review", "safety-review", "electronics-domain"],
        )
        assert "code-review" in agent.skills

    def test_examples_few_shot(self):
        agent = Agent(
            name="test",
            description="test",
            system_prompt="test",
            examples=[
                {"input": "Design a voltage regulator", "output": "Use LM7805..."}
            ],
        )
        assert len(agent.examples) == 1


class TestKillLIFEAgentPipeline:
    """Test Kill_LIFE agent definitions and pipeline structure."""

    def setup_method(self):
        self.registry = AgentRegistry()
        self.agents = {
            "pm": Agent(
                name="pm-agent",
                description="Project manager",
                system_prompt="Orchestrate backlog and gates",
                category="coordination",
                strategy=Strategy.BEST,
                gate_after="S0_spec_complete",
            ),
            "architect": Agent(
                name="architect-agent",
                description="System architect",
                system_prompt="Produce architecture docs",
                category="architecture",
                strategy=Strategy.BEST,
                gate_before="S0_spec_complete",
                gate_after="S1_arch_reviewed",
            ),
            "firmware": Agent(
                name="firmware-agent",
                description="Firmware engineer",
                system_prompt="Implement firmware with Unity tests",
                category="firmware",
                strategy=Strategy.BEST,
                gate_before="S1_arch_reviewed",
                skills=["code-review", "safety-review"],
            ),
            "qa": Agent(
                name="qa-agent",
                description="QA engineer",
                system_prompt="Run tests and generate evidence packs",
                category="qa",
                strategy=Strategy.BEST,
                gate_before="S1_arch_reviewed",
                gate_after="S2_tests_passed",
            ),
            "doc": Agent(
                name="doc-agent",
                description="Documentation maintainer",
                system_prompt="Maintain README and guides",
                category="documentation",
                strategy=Strategy.CHEAPEST,
            ),
        }
        for agent in self.agents.values():
            self.registry.register(agent)

    def test_all_agents_registered(self):
        assert len(self.registry.list()) >= 5

    def test_pipeline_gate_chain(self):
        """Verify gates form a valid chain: PM -> Architect -> Firmware/QA."""
        pm = self.registry.get("pm-agent")
        arch = self.registry.get("architect-agent")
        fw = self.registry.get("firmware-agent")
        qa = self.registry.get("qa-agent")

        # PM produces S0_spec_complete
        assert pm.gate_after == "S0_spec_complete"
        # Architect requires S0, produces S1
        assert arch.gate_before == "S0_spec_complete"
        assert arch.gate_after == "S1_arch_reviewed"
        # Firmware and QA require S1
        assert fw.gate_before == "S1_arch_reviewed"
        assert qa.gate_before == "S1_arch_reviewed"

    def test_filter_by_category(self):
        agents = self.registry.list()
        firmware_agents = [a for a in agents if a.category == "firmware"]
        assert len(firmware_agents) == 1
        assert firmware_agents[0].name == "firmware-agent"

    def test_filter_enabled_agents(self):
        # Disable one agent
        doc = self.registry.get("doc-agent")
        doc.enabled = False
        agents = self.registry.list()
        enabled = [a for a in agents if a.enabled]
        assert len(enabled) == 4

    def test_agent_skills(self):
        fw = self.registry.get("firmware-agent")
        assert "code-review" in fw.skills
        assert "safety-review" in fw.skills

    def test_build_send_payload_includes_system(self):
        pm = self.registry.get("pm-agent")
        payload = pm.build_send_payload("Analyze the spec")
        assert payload["system"] == "Orchestrate backlog and gates"
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"

    def test_build_send_payload_with_context(self):
        arch = self.registry.get("architect-agent")
        context = [{"role": "system", "content": "Previous gate passed"}]
        payload = arch.build_send_payload("Design the architecture", context=context)
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"

    def test_pipeline_order_by_gates(self):
        """Build execution order from gate dependencies."""
        agents = self.registry.list()

        # Agents with no gate_before go first
        first_wave = [a for a in agents if not a.gate_before]
        assert any(a.name == "pm-agent" for a in first_wave)
        assert any(a.name == "doc-agent" for a in first_wave)

        # Agents requiring S0 go second
        second_wave = [a for a in agents if a.gate_before == "S0_spec_complete"]
        assert any(a.name == "architect-agent" for a in second_wave)

        # Agents requiring S1 go third
        third_wave = [a for a in agents if a.gate_before == "S1_arch_reviewed"]
        assert any(a.name == "firmware-agent" for a in third_wave)
        assert any(a.name == "qa-agent" for a in third_wave)
