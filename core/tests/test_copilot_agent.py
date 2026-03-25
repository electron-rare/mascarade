"""Tests for mascarade.copilot_agent — Copilot MCP integration and skill export."""

from __future__ import annotations

from mascarade.copilot_agent import (
    _default_agents,
    _render_skill_md,
    export_agent_skills,
    generate_copilot_instructions,
    generate_copilot_mcp_config,
)

# ---------------------------------------------------------------------------
# export_agent_skills
# ---------------------------------------------------------------------------


class TestExportAgentSkills:
    def test_creates_skill_files(self, tmp_path):
        created = export_agent_skills(output_dir=tmp_path)
        assert len(created) > 0
        for p in created:
            assert p.exists()
            assert p.name == "SKILL.md"

    def test_writes_to_correct_subdirs(self, tmp_path):
        agents = [{"name": "test-agent", "description": "A test", "category": "test"}]
        created = export_agent_skills(output_dir=tmp_path, agents=agents)
        assert len(created) == 1
        assert created[0].parent.name == "test-agent"

    def test_creates_readme_index(self, tmp_path):
        export_agent_skills(output_dir=tmp_path)
        readme = tmp_path / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert "skills exported" in content

    def test_skill_md_content(self, tmp_path):
        agents = [{"name": "coder", "description": "Code gen", "category": "code"}]
        created = export_agent_skills(output_dir=tmp_path, agents=agents)
        content = created[0].read_text()
        assert "mascarade-coder" in content
        assert "Code gen" in content

    def test_default_agents_used_when_none(self, tmp_path):
        created = export_agent_skills(output_dir=tmp_path, agents=None)
        # Should match _default_agents() count
        assert len(created) == len(_default_agents())

    def test_creates_parent_dirs(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        created = export_agent_skills(output_dir=deep)
        assert deep.exists()
        assert len(created) > 0

    def test_overwrites_existing(self, tmp_path):
        agents = [{"name": "x", "description": "v1", "category": "test"}]
        export_agent_skills(output_dir=tmp_path, agents=agents)
        agents[0]["description"] = "v2"
        created = export_agent_skills(output_dir=tmp_path, agents=agents)
        content = created[0].read_text()
        assert "v2" in content


# ---------------------------------------------------------------------------
# generate_copilot_mcp_config
# ---------------------------------------------------------------------------


class TestGenerateCopilotMcpConfig:
    def test_returns_valid_config(self):
        config = generate_copilot_mcp_config()
        assert "mcp" in config
        assert "servers" in config["mcp"]
        assert "mascarade" in config["mcp"]["servers"]

    def test_custom_base_url(self):
        config = generate_copilot_mcp_config(base_url="http://192.168.0.119:8100")
        url = config["mcp"]["servers"]["mascarade"]["url"]
        assert "192.168.0.119" in url

    def test_custom_api_key(self):
        config = generate_copilot_mcp_config(api_key="sk-test-123")
        headers = config["mcp"]["servers"]["mascarade"]["headers"]
        assert "sk-test-123" in headers["Authorization"]

    def test_type_is_http(self):
        config = generate_copilot_mcp_config()
        srv = config["mcp"]["servers"]["mascarade"]
        assert srv["type"] == "http"

    def test_url_ends_with_mcp(self):
        config = generate_copilot_mcp_config()
        assert config["mcp"]["servers"]["mascarade"]["url"].endswith("/mcp")


# ---------------------------------------------------------------------------
# generate_copilot_instructions
# ---------------------------------------------------------------------------


class TestGenerateCopilotInstructions:
    def test_returns_markdown(self):
        md = generate_copilot_instructions()
        assert md.startswith("# Copilot Instructions")

    def test_contains_agent_list(self):
        md = generate_copilot_instructions()
        for agent in _default_agents():
            assert agent["name"] in md

    def test_custom_agents(self):
        agents = [{"name": "custom", "description": "A custom agent"}]
        md = generate_copilot_instructions(agents=agents)
        assert "custom" in md
        assert "A custom agent" in md

    def test_contains_usage_section(self):
        md = generate_copilot_instructions()
        assert "## Usage" in md
        assert "run_agent" in md

    def test_contains_routing_section(self):
        md = generate_copilot_instructions()
        assert "## Routing" in md


# ---------------------------------------------------------------------------
# _default_agents
# ---------------------------------------------------------------------------


class TestDefaultAgents:
    def test_returns_list(self):
        agents = _default_agents()
        assert isinstance(agents, list)
        assert len(agents) == 6

    def test_expected_agents_present(self):
        names = {a["name"] for a in _default_agents()}
        assert "coder" in names
        assert "kicad-designer" in names
        assert "planner" in names

    def test_all_have_required_keys(self):
        for agent in _default_agents():
            assert "name" in agent
            assert "description" in agent
            assert "category" in agent


# ---------------------------------------------------------------------------
# _render_skill_md
# ---------------------------------------------------------------------------


class TestRenderSkillMd:
    def test_frontmatter(self):
        md = _render_skill_md({"name": "test", "description": "Test agent", "category": "general"})
        assert "---" in md
        assert "mascarade-test" in md

    def test_contains_instructions(self):
        md = _render_skill_md({"name": "test", "description": "Desc", "category": "code"})
        assert "run_agent" in md
        assert 'agent="test"' in md
