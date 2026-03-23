"""Tests pour les nœuds SPICE du domaine electronics."""

import pytest

from mascarade.node_engine.types import PortDirection
from mascarade.node_engine.workers.electronics.spice_nodes import (
    AnalyzeConfig,
    AnalyzeNode,
    DebugConvergenceConfig,
    DebugConvergenceNode,
    NetlistGeneratorConfig,
    NetlistGeneratorNode,
    NodeConfig,
    SimulateConfig,
    SimulateNode,
)

# Tests pour NodeConfig et ses sous-classes


def test_node_config_base():
    """NodeConfig de base peut être instancié."""
    config = NodeConfig()
    assert config is not None


def test_netlist_generator_config_defaults():
    """NetlistGeneratorConfig a des valeurs par défaut correctes."""
    config = NetlistGeneratorConfig()
    assert config.include_control_section is True
    assert config.default_analyses == ["op"]


def test_netlist_generator_config_custom():
    """NetlistGeneratorConfig accepte des valeurs personnalisées."""
    config = NetlistGeneratorConfig(
        include_control_section=False,
        default_analyses=["dc", "ac"],
    )
    assert config.include_control_section is False
    assert config.default_analyses == ["dc", "ac"]


def test_simulate_config_defaults():
    """SimulateConfig a des valeurs par défaut correctes."""
    config = SimulateConfig()
    assert config.ngspice_path == "ngspice"
    assert config.timeout_seconds == 300
    assert config.batch_mode is True
    assert config.capture_raw_output is False


def test_simulate_config_custom():
    """SimulateConfig accepte des valeurs personnalisées."""
    config = SimulateConfig(
        ngspice_path="/usr/local/bin/ngspice",
        timeout_seconds=600,
        batch_mode=False,
        capture_raw_output=True,
    )
    assert config.ngspice_path == "/usr/local/bin/ngspice"
    assert config.timeout_seconds == 600
    assert config.batch_mode is False
    assert config.capture_raw_output is True


def test_analyze_config_defaults():
    """AnalyzeConfig a des valeurs par défaut correctes."""
    config = AnalyzeConfig()
    assert config.include_measurements is True
    assert config.suggest_improvements is True


def test_analyze_config_custom():
    """AnalyzeConfig accepte des valeurs personnalisées."""
    config = AnalyzeConfig(
        include_measurements=False,
        suggest_improvements=False,
    )
    assert config.include_measurements is False
    assert config.suggest_improvements is False


def test_debug_convergence_config_defaults():
    """DebugConvergenceConfig a des valeurs par défaut correctes."""
    config = DebugConvergenceConfig()
    assert config.include_fixes is True
    assert config.include_prevention_tips is True


def test_debug_convergence_config_custom():
    """DebugConvergenceConfig accepte des valeurs personnalisées."""
    config = DebugConvergenceConfig(
        include_fixes=False,
        include_prevention_tips=False,
    )
    assert config.include_fixes is False
    assert config.include_prevention_tips is False


# Tests pour NetlistGeneratorNode


def test_netlist_generator_node_creation():
    """NetlistGeneratorNode peut être créé avec et sans configuration."""
    node = NetlistGeneratorNode()
    assert node.node_type == "electronics.spice.netlist_generator"
    assert isinstance(node.config, NetlistGeneratorConfig)


def test_netlist_generator_node_custom_config():
    """NetlistGeneratorNode accepte une configuration personnalisée."""
    config = NetlistGeneratorConfig(
        include_control_section=False,
        default_analyses=["tran"],
    )
    node = NetlistGeneratorNode(config=config)
    assert node.config is config
    assert node.config.include_control_section is False
    assert node.config.default_analyses == ["tran"]


def test_netlist_generator_node_input_ports():
    """NetlistGeneratorNode définit les ports d'entrée corrects."""
    node = NetlistGeneratorNode()
    assert len(node.input_ports) == 3

    # Port circuit_description
    circuit_port = node.input_ports[0]
    assert circuit_port.name == "circuit_description"
    assert circuit_port.direction == PortDirection.INPUT
    assert circuit_port.port_type == "string"
    assert circuit_port.optional is False

    # Port device_models
    models_port = node.input_ports[1]
    assert models_port.name == "device_models"
    assert models_port.direction == PortDirection.INPUT
    assert models_port.port_type == "string"
    assert models_port.optional is True

    # Port target_simulator
    sim_port = node.input_ports[2]
    assert sim_port.name == "target_simulator"
    assert sim_port.direction == PortDirection.INPUT
    assert sim_port.port_type == "string"
    assert sim_port.optional is True
    assert sim_port.default_value == "ngspice"


def test_netlist_generator_node_output_ports():
    """NetlistGeneratorNode définit les ports de sortie corrects."""
    node = NetlistGeneratorNode()
    assert len(node.output_ports) == 1

    netlist_port = node.output_ports[0]
    assert netlist_port.name == "netlist"
    assert netlist_port.direction == PortDirection.OUTPUT
    assert netlist_port.port_type == "electronics.Netlist"


@pytest.mark.asyncio
async def test_netlist_generator_node_execute_basic():
    """NetlistGeneratorNode génère un netlist basique."""
    node = NetlistGeneratorNode()
    inputs = {
        "circuit_description": "Simple RC circuit with R=1k and C=1uF",
    }

    result = await node.execute(inputs)

    assert "netlist" in result
    netlist = result["netlist"]
    assert netlist["format"] == "spice"
    assert "content" in netlist
    assert ".end" in netlist["content"]


@pytest.mark.asyncio
async def test_netlist_generator_node_execute_with_models():
    """NetlistGeneratorNode inclut les modèles de dispositifs."""
    node = NetlistGeneratorNode()
    inputs = {
        "circuit_description": "Transistor amplifier",
        "device_models": ".model mymodel NPN(Is=1e-14 Bf=100)",
    }

    result = await node.execute(inputs)

    assert "netlist" in result
    netlist = result["netlist"]
    assert ".model mymodel NPN" in netlist["content"]


@pytest.mark.asyncio
async def test_netlist_generator_node_execute_with_control_section():
    """NetlistGeneratorNode inclut la section .control."""
    config = NetlistGeneratorConfig(
        include_control_section=True,
        default_analyses=["op", "dc"],
    )
    node = NetlistGeneratorNode(config=config)
    inputs = {
        "circuit_description": "Test circuit",
    }

    result = await node.execute(inputs)

    netlist = result["netlist"]
    assert ".control" in netlist["content"]
    assert ".endc" in netlist["content"]
    assert "op" in netlist["content"]
    assert "dc" in netlist["content"]


@pytest.mark.asyncio
async def test_netlist_generator_node_execute_without_control_section():
    """NetlistGeneratorNode exclut la section .control si configuré."""
    config = NetlistGeneratorConfig(include_control_section=False)
    node = NetlistGeneratorNode(config=config)
    inputs = {
        "circuit_description": "Test circuit",
    }

    result = await node.execute(inputs)

    netlist = result["netlist"]
    assert ".control" not in netlist["content"]


@pytest.mark.asyncio
async def test_netlist_generator_node_execute_missing_description():
    """NetlistGeneratorNode lève ValueError si circuit_description est manquant."""
    node = NetlistGeneratorNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "circuit_description" in str(exc_info.value)


@pytest.mark.asyncio
async def test_netlist_generator_node_execute_empty_description():
    """NetlistGeneratorNode lève ValueError si circuit_description est vide."""
    node = NetlistGeneratorNode()
    inputs = {"circuit_description": ""}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "circuit_description" in str(exc_info.value)


# Tests pour SimulateNode


def test_simulate_node_creation():
    """SimulateNode peut être créé avec et sans configuration."""
    node = SimulateNode()
    assert node.node_type == "electronics.spice.simulate"
    assert isinstance(node.config, SimulateConfig)


def test_simulate_node_custom_config():
    """SimulateNode accepte une configuration personnalisée."""
    config = SimulateConfig(
        ngspice_path="/custom/ngspice",
        timeout_seconds=600,
    )
    node = SimulateNode(config=config)
    assert node.config is config
    assert node.config.ngspice_path == "/custom/ngspice"
    assert node.config.timeout_seconds == 600


def test_simulate_node_input_ports():
    """SimulateNode définit les ports d'entrée corrects."""
    node = SimulateNode()
    assert len(node.input_ports) == 3

    # Port netlist
    netlist_port = node.input_ports[0]
    assert netlist_port.name == "netlist"
    assert netlist_port.direction == PortDirection.INPUT
    assert netlist_port.port_type == "electronics.Netlist"
    assert netlist_port.optional is True

    # Port netlist_content
    content_port = node.input_ports[1]
    assert content_port.name == "netlist_content"
    assert content_port.direction == PortDirection.INPUT
    assert content_port.port_type == "string"
    assert content_port.optional is True

    # Port extra_directives
    directives_port = node.input_ports[2]
    assert directives_port.name == "extra_directives"
    assert directives_port.direction == PortDirection.INPUT
    assert directives_port.port_type == "string"
    assert directives_port.optional is True


def test_simulate_node_output_ports():
    """SimulateNode définit les ports de sortie corrects."""
    node = SimulateNode()
    assert len(node.output_ports) == 5

    # Vérifier les ports de sortie
    port_names = [p.name for p in node.output_ports]
    assert "results" in port_names
    assert "stdout" in port_names
    assert "stderr" in port_names
    assert "success" in port_names
    assert "exit_code" in port_names


@pytest.mark.asyncio
async def test_simulate_node_execute_with_netlist_object():
    """SimulateNode accepte un objet netlist."""
    node = SimulateNode()
    netlist = {
        "format": "spice",
        "content": "* Test\nR1 1 0 1k\n.end",
    }
    inputs = {"netlist": netlist}

    result = await node.execute(inputs)

    assert "success" in result
    assert "stdout" in result
    assert "stderr" in result
    assert "exit_code" in result


@pytest.mark.asyncio
async def test_simulate_node_execute_with_netlist_content():
    """SimulateNode accepte un contenu netlist brut."""
    node = SimulateNode()
    inputs = {"netlist_content": "* Test\nR1 1 0 1k\n.end"}

    result = await node.execute(inputs)

    assert "success" in result
    assert "stdout" in result
    assert "stderr" in result
    assert "exit_code" in result


@pytest.mark.asyncio
async def test_simulate_node_execute_missing_input():
    """SimulateNode lève ValueError si aucun netlist n'est fourni."""
    node = SimulateNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "netlist" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_simulate_node_execute_with_extra_directives():
    """SimulateNode inclut les directives supplémentaires."""
    node = SimulateNode()
    inputs = {
        "netlist_content": "* Test\nR1 1 0 1k\n.end",
        "extra_directives": ".option method=gear",
    }

    result = await node.execute(inputs)

    assert "success" in result


# Tests pour AnalyzeNode


def test_analyze_node_creation():
    """AnalyzeNode peut être créé avec et sans configuration."""
    node = AnalyzeNode()
    assert node.node_type == "electronics.spice.analyze"
    assert isinstance(node.config, AnalyzeConfig)


def test_analyze_node_custom_config():
    """AnalyzeNode accepte une configuration personnalisée."""
    config = AnalyzeConfig(
        include_measurements=False,
        suggest_improvements=False,
    )
    node = AnalyzeNode(config=config)
    assert node.config is config
    assert node.config.include_measurements is False


def test_analyze_node_input_ports():
    """AnalyzeNode définit les ports d'entrée corrects."""
    node = AnalyzeNode()
    assert len(node.input_ports) == 3

    # Port netlist
    netlist_port = node.input_ports[0]
    assert netlist_port.name == "netlist"
    assert netlist_port.direction == PortDirection.INPUT
    assert netlist_port.port_type == "electronics.Netlist"
    assert netlist_port.optional is True

    # Port netlist_content
    content_port = node.input_ports[1]
    assert content_port.name == "netlist_content"
    assert content_port.direction == PortDirection.INPUT
    assert content_port.port_type == "string"
    assert content_port.optional is True

    # Port analysis_type
    type_port = node.input_ports[2]
    assert type_port.name == "analysis_type"
    assert type_port.direction == PortDirection.INPUT
    assert type_port.port_type == "string"
    assert type_port.optional is True


def test_analyze_node_output_ports():
    """AnalyzeNode définit les ports de sortie corrects."""
    node = AnalyzeNode()
    assert len(node.output_ports) == 3

    # Port analysis_report
    report_port = node.output_ports[0]
    assert report_port.name == "analysis_report"
    assert report_port.direction == PortDirection.OUTPUT
    assert report_port.port_type == "string"

    # Port characteristics
    char_port = node.output_ports[1]
    assert char_port.name == "characteristics"
    assert char_port.direction == PortDirection.OUTPUT
    assert char_port.port_type == "object"

    # Port recommendations
    rec_port = node.output_ports[2]
    assert rec_port.name == "recommendations"
    assert rec_port.direction == PortDirection.OUTPUT
    assert rec_port.port_type == "array"


@pytest.mark.asyncio
async def test_analyze_node_execute_basic():
    """AnalyzeNode analyse un netlist."""
    node = AnalyzeNode()
    inputs = {
        "netlist_content": "* Test circuit\nR1 1 0 1k\n.op\n.end",
    }

    result = await node.execute(inputs)

    assert "analysis_report" in result
    assert "characteristics" in result
    assert "recommendations" in result
    assert isinstance(result["analysis_report"], str)
    assert isinstance(result["characteristics"], dict)
    assert isinstance(result["recommendations"], list)


@pytest.mark.asyncio
async def test_analyze_node_execute_with_measurements():
    """AnalyzeNode inclut les mesures si configuré."""
    config = AnalyzeConfig(include_measurements=True)
    node = AnalyzeNode(config=config)
    inputs = {
        "netlist_content": "* Test\nR1 1 0 1k\n.ac dec 10 1 100k\n.end",
    }

    result = await node.execute(inputs)

    assert "analysis_report" in result
    assert "Suggested Measurements" in result["analysis_report"]


@pytest.mark.asyncio
async def test_analyze_node_execute_with_improvements():
    """AnalyzeNode suggère des améliorations si configuré."""
    config = AnalyzeConfig(suggest_improvements=True)
    node = AnalyzeNode(config=config)
    inputs = {
        "netlist_content": "* Test\nR1 1 0 1k\n.end",
    }

    result = await node.execute(inputs)

    assert "analysis_report" in result
    assert "Potential Improvements" in result["analysis_report"]


@pytest.mark.asyncio
async def test_analyze_node_execute_missing_netlist():
    """AnalyzeNode lève ValueError si netlist est manquant."""
    node = AnalyzeNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "netlist" in str(exc_info.value).lower()


# Tests pour DebugConvergenceNode


def test_debug_convergence_node_creation():
    """DebugConvergenceNode peut être créé avec et sans configuration."""
    node = DebugConvergenceNode()
    assert node.node_type == "electronics.spice.debug_convergence"
    assert isinstance(node.config, DebugConvergenceConfig)


def test_debug_convergence_node_custom_config():
    """DebugConvergenceNode accepte une configuration personnalisée."""
    config = DebugConvergenceConfig(
        include_fixes=False,
        include_prevention_tips=False,
    )
    node = DebugConvergenceNode(config=config)
    assert node.config is config
    assert node.config.include_fixes is False


def test_debug_convergence_node_input_ports():
    """DebugConvergenceNode définit les ports d'entrée corrects."""
    node = DebugConvergenceNode()
    assert len(node.input_ports) == 4

    # Port error_message
    error_port = node.input_ports[0]
    assert error_port.name == "error_message"
    assert error_port.direction == PortDirection.INPUT
    assert error_port.port_type == "string"
    assert error_port.optional is False

    # Port netlist
    netlist_port = node.input_ports[1]
    assert netlist_port.name == "netlist"
    assert netlist_port.direction == PortDirection.INPUT
    assert netlist_port.port_type == "electronics.Netlist"
    assert netlist_port.optional is True

    # Port netlist_content
    content_port = node.input_ports[2]
    assert content_port.name == "netlist_content"
    assert content_port.direction == PortDirection.INPUT
    assert content_port.port_type == "string"
    assert content_port.optional is True

    # Port simulation_output
    output_port = node.input_ports[3]
    assert output_port.name == "simulation_output"
    assert output_port.direction == PortDirection.INPUT
    assert output_port.port_type == "string"
    assert output_port.optional is True


def test_debug_convergence_node_output_ports():
    """DebugConvergenceNode définit les ports de sortie corrects."""
    node = DebugConvergenceNode()
    assert len(node.output_ports) == 4

    # Port diagnosis
    diag_port = node.output_ports[0]
    assert diag_port.name == "diagnosis"
    assert diag_port.direction == PortDirection.OUTPUT
    assert diag_port.port_type == "string"

    # Port solutions
    sol_port = node.output_ports[1]
    assert sol_port.name == "solutions"
    assert sol_port.direction == PortDirection.OUTPUT
    assert sol_port.port_type == "array"

    # Port fixed_netlist
    fixed_port = node.output_ports[2]
    assert fixed_port.name == "fixed_netlist"
    assert fixed_port.direction == PortDirection.OUTPUT
    assert fixed_port.port_type == "string"

    # Port prevention_tips
    tips_port = node.output_ports[3]
    assert tips_port.name == "prevention_tips"
    assert tips_port.direction == PortDirection.OUTPUT
    assert tips_port.port_type == "array"


@pytest.mark.asyncio
async def test_debug_convergence_node_execute_basic():
    """DebugConvergenceNode génère un rapport de débogage."""
    node = DebugConvergenceNode()
    inputs = {
        "error_message": "doAnalyses: iteration limit reached",
        "netlist_content": "* Test\nR1 1 0 1k\n.end",
    }

    result = await node.execute(inputs)

    assert "diagnosis" in result
    assert "solutions" in result
    assert "fixed_netlist" in result
    assert "prevention_tips" in result
    assert isinstance(result["diagnosis"], str)
    assert isinstance(result["solutions"], list)
    assert isinstance(result["fixed_netlist"], str)
    assert isinstance(result["prevention_tips"], list)


@pytest.mark.asyncio
async def test_debug_convergence_node_execute_with_fixes():
    """DebugConvergenceNode inclut les corrections si configuré."""
    config = DebugConvergenceConfig(include_fixes=True)
    node = DebugConvergenceNode(config=config)
    inputs = {
        "error_message": "convergence error",
        "netlist_content": "* Test\nR1 1 0 1k\n.end",
    }

    result = await node.execute(inputs)

    assert "fixed_netlist" in result
    assert result["fixed_netlist"]  # Should not be empty
    assert ".options" in result["fixed_netlist"]


@pytest.mark.asyncio
async def test_debug_convergence_node_execute_with_prevention():
    """DebugConvergenceNode inclut les conseils de prévention si configuré."""
    config = DebugConvergenceConfig(include_prevention_tips=True)
    node = DebugConvergenceNode(config=config)
    inputs = {
        "error_message": "convergence error",
        "netlist_content": "* Test\nR1 1 0 1k\n.end",
    }

    result = await node.execute(inputs)

    assert "prevention_tips" in result
    assert len(result["prevention_tips"]) > 0


@pytest.mark.asyncio
async def test_debug_convergence_node_execute_missing_error():
    """DebugConvergenceNode lève ValueError si error_message est manquant."""
    node = DebugConvergenceNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "error_message" in str(exc_info.value)


@pytest.mark.asyncio
async def test_debug_convergence_node_execute_empty_error():
    """DebugConvergenceNode lève ValueError si error_message est vide."""
    node = DebugConvergenceNode()
    inputs = {"error_message": ""}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "error_message" in str(exc_info.value)
