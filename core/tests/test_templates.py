"""Unit tests for workflow template system"""

import json
import tempfile
from pathlib import Path

import pytest

from mascarade.orchestrator.templates import (
    BUILTIN_TEMPLATES,
    ExecutionMode,
    TemplateRegistry,
    WorkflowTemplate,
    register_builtin_templates,
)


class TestWorkflowTemplate:
    """Test WorkflowTemplate Pydantic model"""

    def test_valid_template_creation(self):
        """Test creating a valid template"""
        template = WorkflowTemplate(
            id="test-template",
            name="Test Template",
            description="A test template for unit testing",
            agent_names=["agent1", "agent2"],
            mode=ExecutionMode.PIPELINE,
            documentation="This is test documentation explaining the workflow.",
        )
        assert template.id == "test-template"
        assert template.name == "Test Template"
        assert len(template.agent_names) == 2
        assert template.mode == ExecutionMode.PIPELINE
        assert len(template.documentation) > 0

    def test_template_validation_min_length(self):
        """Test template ID validation (min_length=1)"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            WorkflowTemplate(
                id="",  # Invalid: empty string
                name="Test",
                description="Test",
                agent_names=["agent1"],
                mode=ExecutionMode.SEQUENTIAL,
                documentation="Test",
            )

    def test_template_with_routing_overrides(self):
        """Test template with routing overrides"""
        template = WorkflowTemplate(
            id="test-override",
            name="Test Override",
            description="Test with overrides",
            agent_names=["agent1"],
            mode=ExecutionMode.SEQUENTIAL,
            routing_overrides={"agent1": {"strategy": "fastest"}},
            documentation="Test documentation",
        )
        assert template.routing_overrides is not None
        assert "agent1" in template.routing_overrides


class TestTemplateRegistry:
    """Test TemplateRegistry functionality"""

    def test_register_and_get_template(self):
        """Test registering and retrieving a template"""
        registry = TemplateRegistry(storage_path=None)
        template = WorkflowTemplate(
            id="test-reg",
            name="Test Registry",
            description="Test",
            agent_names=["agent1"],
            mode=ExecutionMode.SEQUENTIAL,
            documentation="Test documentation",
        )
        registry.register(template)
        retrieved = registry.get("test-reg")
        assert retrieved.id == template.id
        assert retrieved.name == template.name

    def test_get_missing_template_raises_keyerror(self):
        """Test that getting a non-existent template raises KeyError"""
        registry = TemplateRegistry(storage_path=None)
        with pytest.raises(KeyError, match="Template 'nonexistent' non trouvé"):
            registry.get("nonexistent")

    def test_list_templates(self):
        """Test listing all templates"""
        registry = TemplateRegistry(storage_path=None)
        template1 = WorkflowTemplate(
            id="test1",
            name="Test 1",
            description="Test",
            agent_names=["agent1"],
            mode=ExecutionMode.SEQUENTIAL,
            documentation="Test",
        )
        template2 = WorkflowTemplate(
            id="test2",
            name="Test 2",
            description="Test",
            agent_names=["agent2"],
            mode=ExecutionMode.PIPELINE,
            documentation="Test",
        )
        registry.register(template1)
        registry.register(template2)

        templates = registry.list()
        assert len(templates) == 2
        assert any(t.id == "test1" for t in templates)
        assert any(t.id == "test2" for t in templates)

    def test_contains_and_len(self):
        """Test __contains__ and __len__ methods"""
        registry = TemplateRegistry(storage_path=None)
        template = WorkflowTemplate(
            id="test-contains",
            name="Test",
            description="Test",
            agent_names=["agent1"],
            mode=ExecutionMode.SEQUENTIAL,
            documentation="Test",
        )
        registry.register(template)

        assert "test-contains" in registry
        assert "nonexistent" not in registry
        assert len(registry) == 1

    def test_builtin_flag(self):
        """Test builtin template tracking"""
        registry = TemplateRegistry(storage_path=None)
        template = WorkflowTemplate(
            id="builtin-test",
            name="Builtin Test",
            description="Test",
            agent_names=["agent1"],
            mode=ExecutionMode.SEQUENTIAL,
            documentation="Test",
        )
        registry.register(template, builtin=True)

        assert registry.is_builtin("builtin-test")
        assert len(registry.list()) == 1

    def test_remove_template(self):
        """Test removing a template"""
        registry = TemplateRegistry(storage_path=None)
        template = WorkflowTemplate(
            id="test-remove",
            name="Test Remove",
            description="Test",
            agent_names=["agent1"],
            mode=ExecutionMode.SEQUENTIAL,
            documentation="Test",
        )
        registry.register(template)
        assert "test-remove" in registry

        registry.remove("test-remove")
        assert "test-remove" not in registry

    def test_save_and_load_persistence(self):
        """Test saving and loading templates to/from JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "templates.json"
            registry = TemplateRegistry(storage_path=storage_path)

            # Create and register a dynamic template
            template = WorkflowTemplate(
                id="dynamic-template",
                name="Dynamic Template",
                description="A dynamic template for testing persistence",
                agent_names=["agent1", "agent2"],
                mode=ExecutionMode.PIPELINE,
                documentation="Test documentation for persistence",
            )
            registry.register(template, builtin=False)

            # Save to file
            registry.save()
            assert storage_path.exists()

            # Create a new registry and load
            new_registry = TemplateRegistry(storage_path=storage_path)
            new_registry.load()

            # Verify loaded template matches
            loaded = new_registry.get("dynamic-template")
            assert loaded.id == template.id
            assert loaded.name == template.name
            assert loaded.agent_names == template.agent_names
            assert loaded.mode == template.mode

    def test_builtin_templates_not_persisted(self):
        """Test that builtin templates are not saved to JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "templates.json"
            registry = TemplateRegistry(storage_path=storage_path)

            # Register a builtin template
            builtin = WorkflowTemplate(
                id="builtin",
                name="Builtin",
                description="Builtin template",
                agent_names=["agent1"],
                mode=ExecutionMode.SEQUENTIAL,
                documentation="Builtin doc",
            )
            registry.register(builtin, builtin=True)

            # Save and check file content
            registry.save()
            with open(storage_path) as f:
                data = json.load(f)

            # Builtin templates should not be in the saved file
            assert len(data) == 0


class TestBuiltinTemplates:
    """Test the built-in templates"""

    def test_builtin_templates_count(self):
        """Test that we have at least 4 builtin templates (spec requirement)"""
        assert len(BUILTIN_TEMPLATES) >= 4

    def test_all_builtin_templates_valid(self):
        """Test that all builtin templates have valid structure"""
        for template in BUILTIN_TEMPLATES:
            # ID should be non-empty
            assert len(template.id) > 0

            # Name should be non-empty
            assert len(template.name) > 0

            # Description should be non-empty
            assert len(template.description) > 0

            # Should have at least one agent
            assert len(template.agent_names) > 0

            # Documentation should be non-empty
            assert len(template.documentation) > 0

            # Mode should be valid
            assert template.mode in [
                ExecutionMode.SEQUENTIAL,
                ExecutionMode.PARALLEL,
                ExecutionMode.PIPELINE,
            ]

    def test_required_templates_present(self):
        """Test that required templates are present (spec requirement)"""
        template_ids = [t.id for t in BUILTIN_TEMPLATES]

        # Spec requires: code review, research, translation, electronics
        assert "code-review-workflow" in template_ids
        assert "research-report" in template_ids
        assert "translate-and-polish" in template_ids
        assert "electronics-pipeline" in template_ids

    def test_electronics_template_agents(self):
        """Test that electronics template uses correct agents (spec requirement)"""
        electronics = next(
            t for t in BUILTIN_TEMPLATES if t.id == "electronics-pipeline"
        )

        # Spec requires: kicad-designer, spice-expert, components-expert
        expected_agents = {"kicad-designer", "spice-expert", "components-expert"}
        actual_agents = set(electronics.agent_names)

        assert (
            expected_agents == actual_agents
        ), f"Electronics template agents mismatch. Expected: {expected_agents}, Got: {actual_agents}"

    def test_all_templates_have_documentation(self):
        """Test that all templates have documentation (spec requirement)"""
        for template in BUILTIN_TEMPLATES:
            assert (
                len(template.documentation) > 0
            ), f"Template {template.id} is missing documentation"


class TestRegisterBuiltinTemplates:
    """Test the builtin template registration function"""

    def test_register_builtin_templates(self):
        """Test that register_builtin_templates() works correctly"""
        registry = TemplateRegistry(storage_path=None)
        register_builtin_templates(registry)

        # Should have all builtin templates registered
        assert len(registry.list()) == len(BUILTIN_TEMPLATES)

        # All should be marked as builtin
        for template in BUILTIN_TEMPLATES:
            assert registry.is_builtin(
                template.id
            ), f"Template {template.id} not marked as builtin"

        # Should be able to retrieve each template
        for template in BUILTIN_TEMPLATES:
            retrieved = registry.get(template.id)
            assert retrieved.id == template.id
