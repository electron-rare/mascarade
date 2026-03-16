"""Tests pour les nœuds PCB DRC du domaine electronics."""

import pytest

from mascarade.node_engine.types import PortDirection
from mascarade.node_engine.workers.electronics.pcb_nodes import (
    DrcCheckConfig,
    DrcCheckNode,
    NodeConfig,
    RuleDefinitionConfig,
    RuleDefinitionNode,
    ViolationReporterConfig,
    ViolationReporterNode,
)


# Tests pour NodeConfig et ses sous-classes


def test_node_config_base():
    """NodeConfig de base peut être instancié."""
    config = NodeConfig()
    assert config is not None


def test_drc_check_config_defaults():
    """DrcCheckConfig a des valeurs par défaut correctes."""
    config = DrcCheckConfig()
    assert config.severity_threshold == "warning"
    assert config.kicad_cli_path == "kicad-cli"


def test_drc_check_config_custom():
    """DrcCheckConfig accepte des valeurs personnalisées."""
    config = DrcCheckConfig(
        severity_threshold="error",
        kicad_cli_path="/usr/local/bin/kicad-cli",
    )
    assert config.severity_threshold == "error"
    assert config.kicad_cli_path == "/usr/local/bin/kicad-cli"


def test_rule_definition_config_defaults():
    """RuleDefinitionConfig peut être instancié."""
    config = RuleDefinitionConfig()
    assert config is not None


def test_violation_reporter_config_defaults():
    """ViolationReporterConfig peut être instancié."""
    config = ViolationReporterConfig()
    assert config is not None


# Tests pour DrcCheckNode


def test_drc_check_node_creation():
    """DrcCheckNode peut être créé avec et sans configuration."""
    node = DrcCheckNode()
    assert node.node_type == "electronics.pcb.drc_check"
    assert isinstance(node.config, DrcCheckConfig)


def test_drc_check_node_custom_config():
    """DrcCheckNode accepte une configuration personnalisée."""
    config = DrcCheckConfig(
        severity_threshold="error",
        kicad_cli_path="/custom/path/kicad-cli",
    )
    node = DrcCheckNode(config=config)
    assert node.config is config
    assert node.config.severity_threshold == "error"
    assert node.config.kicad_cli_path == "/custom/path/kicad-cli"


def test_drc_check_node_input_ports():
    """DrcCheckNode définit les ports d'entrée corrects."""
    node = DrcCheckNode()
    assert len(node.input_ports) == 2

    # Port board_file
    board_port = node.input_ports[0]
    assert board_port.name == "board_file"
    assert board_port.direction == PortDirection.INPUT
    assert board_port.port_type == "binary"
    assert board_port.optional is False

    # Port rules
    rules_port = node.input_ports[1]
    assert rules_port.name == "rules"
    assert rules_port.direction == PortDirection.INPUT
    assert rules_port.port_type == "json"
    assert rules_port.optional is True


def test_drc_check_node_output_ports():
    """DrcCheckNode définit les ports de sortie corrects."""
    node = DrcCheckNode()
    assert len(node.output_ports) == 1

    report_port = node.output_ports[0]
    assert report_port.name == "report"
    assert report_port.direction == PortDirection.OUTPUT
    assert report_port.port_type == "electronics.DRCReport"


@pytest.mark.asyncio
async def test_drc_check_node_execute_missing_board_file():
    """DrcCheckNode lève ValueError si board_file est manquant."""
    node = DrcCheckNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "board_file" in str(exc_info.value)


@pytest.mark.asyncio
async def test_drc_check_node_execute_empty_board_file():
    """DrcCheckNode lève ValueError si board_file est vide."""
    node = DrcCheckNode()
    inputs = {"board_file": ""}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "board_file" in str(exc_info.value)


# Tests pour RuleDefinitionNode


def test_rule_definition_node_creation():
    """RuleDefinitionNode peut être créé."""
    node = RuleDefinitionNode()
    assert node.node_type == "electronics.pcb.rule_definition"
    assert isinstance(node.config, RuleDefinitionConfig)


def test_rule_definition_node_input_ports():
    """RuleDefinitionNode définit les ports d'entrée corrects."""
    node = RuleDefinitionNode()
    assert len(node.input_ports) == 2

    # Port manufacturer_preset
    preset_port = node.input_ports[0]
    assert preset_port.name == "manufacturer_preset"
    assert preset_port.direction == PortDirection.INPUT
    assert preset_port.port_type == "string"
    assert preset_port.optional is True

    # Port custom_overrides
    overrides_port = node.input_ports[1]
    assert overrides_port.name == "custom_overrides"
    assert overrides_port.direction == PortDirection.INPUT
    assert overrides_port.port_type == "json"
    assert overrides_port.optional is True


def test_rule_definition_node_output_ports():
    """RuleDefinitionNode définit les ports de sortie corrects."""
    node = RuleDefinitionNode()
    assert len(node.output_ports) == 1

    rules_port = node.output_ports[0]
    assert rules_port.name == "rules"
    assert rules_port.direction == PortDirection.OUTPUT
    assert rules_port.port_type == "json"


@pytest.mark.asyncio
async def test_rule_definition_node_execute_default():
    """RuleDefinitionNode génère des règles par défaut."""
    node = RuleDefinitionNode()
    inputs = {}

    result = await node.execute(inputs)

    assert "rules" in result
    rules = result["rules"]
    assert "min_trace_width_mm" in rules
    assert "min_clearance_mm" in rules
    assert "min_drill_mm" in rules
    assert rules["min_trace_width_mm"] == 0.15


@pytest.mark.asyncio
async def test_rule_definition_node_execute_jlcpcb_standard():
    """RuleDefinitionNode génère les règles JLCPCB standard."""
    node = RuleDefinitionNode()
    inputs = {"manufacturer_preset": "jlcpcb_standard"}

    result = await node.execute(inputs)

    rules = result["rules"]
    assert rules["min_trace_width_mm"] == 0.127
    assert rules["min_clearance_mm"] == 0.127
    assert rules["min_drill_mm"] == 0.3
    assert rules["layer_count"] == [1, 2, 4, 6]


@pytest.mark.asyncio
async def test_rule_definition_node_execute_jlcpcb_advanced():
    """RuleDefinitionNode génère les règles JLCPCB advanced."""
    node = RuleDefinitionNode()
    inputs = {"manufacturer_preset": "jlcpcb_advanced"}

    result = await node.execute(inputs)

    rules = result["rules"]
    assert rules["min_trace_width_mm"] == 0.09
    assert rules["min_clearance_mm"] == 0.09
    assert rules["min_drill_mm"] == 0.2
    assert rules["layer_count"] == [1, 2, 4, 6, 8]


@pytest.mark.asyncio
async def test_rule_definition_node_execute_oshpark():
    """RuleDefinitionNode génère les règles OSH Park."""
    node = RuleDefinitionNode()
    inputs = {"manufacturer_preset": "oshpark"}

    result = await node.execute(inputs)

    rules = result["rules"]
    assert rules["min_trace_width_mm"] == 0.152
    assert rules["min_clearance_mm"] == 0.152
    assert rules["min_drill_mm"] == 0.254
    assert rules["layer_count"] == [2, 4]


@pytest.mark.asyncio
async def test_rule_definition_node_execute_with_overrides():
    """RuleDefinitionNode applique les overrides personnalisés."""
    node = RuleDefinitionNode()
    inputs = {
        "manufacturer_preset": "jlcpcb_standard",
        "custom_overrides": {
            "min_trace_width_mm": 0.2,
            "custom_rule": "my_value",
        },
    }

    result = await node.execute(inputs)

    rules = result["rules"]
    assert rules["min_trace_width_mm"] == 0.2  # Override applied
    assert rules["min_clearance_mm"] == 0.127  # Original value
    assert rules["custom_rule"] == "my_value"  # New rule added


@pytest.mark.asyncio
async def test_rule_definition_node_execute_unknown_preset():
    """RuleDefinitionNode utilise les règles par défaut pour un preset inconnu."""
    node = RuleDefinitionNode()
    inputs = {"manufacturer_preset": "unknown_manufacturer"}

    result = await node.execute(inputs)

    rules = result["rules"]
    assert rules["min_trace_width_mm"] == 0.15  # Default value


# Tests pour ViolationReporterNode


def test_violation_reporter_node_creation():
    """ViolationReporterNode peut être créé."""
    node = ViolationReporterNode()
    assert node.node_type == "electronics.pcb.violation_reporter"
    assert isinstance(node.config, ViolationReporterConfig)


def test_violation_reporter_node_input_ports():
    """ViolationReporterNode définit les ports d'entrée corrects."""
    node = ViolationReporterNode()
    assert len(node.input_ports) == 2

    # Port report
    report_port = node.input_ports[0]
    assert report_port.name == "report"
    assert report_port.direction == PortDirection.INPUT
    assert report_port.port_type == "electronics.DRCReport"
    assert report_port.optional is False

    # Port format
    format_port = node.input_ports[1]
    assert format_port.name == "format"
    assert format_port.direction == PortDirection.INPUT
    assert format_port.port_type == "string"
    assert format_port.optional is True
    assert format_port.default_value == "markdown"


def test_violation_reporter_node_output_ports():
    """ViolationReporterNode définit les ports de sortie corrects."""
    node = ViolationReporterNode()
    assert len(node.output_ports) == 2

    # Port formatted_report
    formatted_port = node.output_ports[0]
    assert formatted_port.name == "formatted_report"
    assert formatted_port.direction == PortDirection.OUTPUT
    assert formatted_port.port_type == "string"

    # Port summary
    summary_port = node.output_ports[1]
    assert summary_port.name == "summary"
    assert summary_port.direction == PortDirection.OUTPUT
    assert summary_port.port_type == "json"


@pytest.mark.asyncio
async def test_violation_reporter_node_execute_missing_report():
    """ViolationReporterNode lève ValueError si report est manquant."""
    node = ViolationReporterNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "report" in str(exc_info.value)


@pytest.mark.asyncio
async def test_violation_reporter_node_execute_empty_report():
    """ViolationReporterNode lève ValueError si report est vide."""
    node = ViolationReporterNode()
    inputs = {"report": None}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "report" in str(exc_info.value)


@pytest.mark.asyncio
async def test_violation_reporter_node_execute_no_violations():
    """ViolationReporterNode génère un rapport pour un DRC passé."""
    node = ViolationReporterNode()
    report = {
        "passed": True,
        "violations": [],
        "rules_checked": 25,
        "board_file": "test.kicad_pcb",
    }
    inputs = {"report": report}

    result = await node.execute(inputs)

    assert "formatted_report" in result
    assert "summary" in result

    summary = result["summary"]
    assert summary["total"] == 0
    assert summary["errors"] == 0
    assert summary["warnings"] == 0
    assert summary["passed"] is True

    formatted = result["formatted_report"]
    assert "PASSED" in formatted
    assert "No violations found" in formatted


@pytest.mark.asyncio
async def test_violation_reporter_node_execute_with_violations():
    """ViolationReporterNode génère un rapport avec des violations."""
    node = ViolationReporterNode()
    report = {
        "passed": False,
        "violations": [
            {
                "rule": "min_clearance",
                "severity": "error",
                "message": "Clearance too small between traces",
                "location": {"x": 10.5, "y": 20.3, "layer": "F.Cu"},
            },
            {
                "rule": "min_trace_width",
                "severity": "warning",
                "message": "Trace width below recommended minimum",
                "location": {"x": 15.2, "y": 25.7, "layer": "B.Cu"},
            },
        ],
        "rules_checked": 25,
        "board_file": "test.kicad_pcb",
    }
    inputs = {"report": report}

    result = await node.execute(inputs)

    summary = result["summary"]
    assert summary["total"] == 2
    assert summary["errors"] == 1
    assert summary["warnings"] == 1
    assert summary["passed"] is False

    formatted = result["formatted_report"]
    assert "FAILED" in formatted
    assert "min_clearance" in formatted
    assert "min_trace_width" in formatted


@pytest.mark.asyncio
async def test_violation_reporter_node_execute_markdown_format():
    """ViolationReporterNode génère un rapport au format markdown."""
    node = ViolationReporterNode()
    report = {
        "passed": False,
        "violations": [
            {
                "rule": "test_rule",
                "severity": "error",
                "message": "Test violation",
                "location": {"x": 0, "y": 0, "layer": "F.Cu"},
            }
        ],
        "rules_checked": 10,
        "board_file": "test.kicad_pcb",
    }
    inputs = {"report": report, "format": "markdown"}

    result = await node.execute(inputs)

    formatted = result["formatted_report"]
    assert "# PCB Design Rule Check Report" in formatted
    assert "## Summary" in formatted
    assert "## Violations" in formatted
    assert "🔴" in formatted  # Error emoji


@pytest.mark.asyncio
async def test_violation_reporter_node_execute_csv_format():
    """ViolationReporterNode génère un rapport au format CSV."""
    node = ViolationReporterNode()
    report = {
        "passed": False,
        "violations": [
            {
                "rule": "test_rule",
                "severity": "error",
                "message": "Test violation",
                "location": {"x": 10.5, "y": 20.3, "layer": "F.Cu"},
            }
        ],
        "rules_checked": 10,
        "board_file": "test.kicad_pcb",
    }
    inputs = {"report": report, "format": "csv"}

    result = await node.execute(inputs)

    formatted = result["formatted_report"]
    assert "Rule,Severity,Message,X,Y,Layer" in formatted
    assert "test_rule" in formatted
    assert "error" in formatted
    assert "10.5" in formatted


@pytest.mark.asyncio
async def test_violation_reporter_node_execute_json_format():
    """ViolationReporterNode génère un rapport au format JSON."""
    node = ViolationReporterNode()
    report = {
        "passed": False,
        "violations": [
            {
                "rule": "test_rule",
                "severity": "error",
                "message": "Test violation",
                "location": {"x": 0, "y": 0, "layer": "F.Cu"},
            }
        ],
        "rules_checked": 10,
        "board_file": "test.kicad_pcb",
    }
    inputs = {"report": report, "format": "json"}

    result = await node.execute(inputs)

    formatted = result["formatted_report"]
    # Should be valid JSON
    import json

    parsed = json.loads(formatted)
    assert parsed["passed"] is False
    assert len(parsed["violations"]) == 1


@pytest.mark.asyncio
async def test_violation_reporter_node_execute_unknown_format():
    """ViolationReporterNode utilise markdown pour un format inconnu."""
    node = ViolationReporterNode()
    report = {
        "passed": True,
        "violations": [],
        "rules_checked": 10,
        "board_file": "test.kicad_pcb",
    }
    inputs = {"report": report, "format": "unknown_format"}

    result = await node.execute(inputs)

    formatted = result["formatted_report"]
    # Should default to markdown
    assert "# PCB Design Rule Check Report" in formatted
