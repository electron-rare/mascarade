"""Tests pour les nœuds de composants du domaine electronics."""

import pytest

from mascarade.node_engine.types import PortDirection
from mascarade.node_engine.workers.electronics.component_nodes import (
    AvailabilityCheckConfig,
    AvailabilityCheckNode,
    BomGeneratorConfig,
    BomGeneratorNode,
    CplGeneratorConfig,
    CplGeneratorNode,
    DatasheetConfig,
    DatasheetNode,
    FindAlternativesConfig,
    FindAlternativesNode,
    JlcpcbOptimizationConfig,
    JlcpcbOptimizationNode,
    LookupConfig,
    LookupNode,
    NodeConfig,
)

# Tests pour NodeConfig et ses sous-classes


def test_node_config_base():
    """NodeConfig de base peut être instancié."""
    config = NodeConfig()
    assert config is not None


def test_lookup_config_defaults():
    """LookupConfig a des valeurs par défaut correctes."""
    config = LookupConfig()
    assert config.include_alternatives is True
    assert config.include_availability is True


def test_lookup_config_custom():
    """LookupConfig accepte des valeurs personnalisées."""
    config = LookupConfig(
        include_alternatives=False,
        include_availability=False,
    )
    assert config.include_alternatives is False
    assert config.include_availability is False


def test_jlcpcb_optimization_config_defaults():
    """JlcpcbOptimizationConfig a des valeurs par défaut correctes."""
    config = JlcpcbOptimizationConfig()
    assert config.prefer_basic_parts is True
    assert config.max_extended_parts == 5


def test_jlcpcb_optimization_config_custom():
    """JlcpcbOptimizationConfig accepte des valeurs personnalisées."""
    config = JlcpcbOptimizationConfig(
        prefer_basic_parts=False,
        max_extended_parts=10,
    )
    assert config.prefer_basic_parts is False
    assert config.max_extended_parts == 10


def test_bom_generator_config_defaults():
    """BomGeneratorConfig a des valeurs par défaut correctes."""
    config = BomGeneratorConfig()
    assert config.format == "jlcpcb"
    assert config.include_cost_estimates is True


def test_bom_generator_config_custom():
    """BomGeneratorConfig accepte des valeurs personnalisées."""
    config = BomGeneratorConfig(
        format="csv",
        include_cost_estimates=False,
    )
    assert config.format == "csv"
    assert config.include_cost_estimates is False


def test_cpl_generator_config_defaults():
    """CplGeneratorConfig a des valeurs par défaut correctes."""
    config = CplGeneratorConfig()
    assert config.coordinate_units == "mm"
    assert config.rotation_standard == "jlcpcb"


def test_availability_check_config_defaults():
    """AvailabilityCheckConfig a des valeurs par défaut correctes."""
    config = AvailabilityCheckConfig()
    assert config.check_stock is True
    assert config.check_lead_time is True


def test_datasheet_config_defaults():
    """DatasheetConfig a des valeurs par défaut correctes."""
    config = DatasheetConfig()
    assert config.include_parameters is True
    assert config.include_diagrams is False


def test_find_alternatives_config_defaults():
    """FindAlternativesConfig a des valeurs par défaut correctes."""
    config = FindAlternativesConfig()
    assert config.include_pin_compatible is True
    assert config.include_functional_equiv is True
    assert config.max_alternatives == 10


# Tests pour LookupNode


def test_lookup_node_creation():
    """LookupNode peut être créé avec et sans configuration."""
    node = LookupNode()
    assert node.node_type == "electronics.component.lookup"
    assert isinstance(node.config, LookupConfig)


def test_lookup_node_custom_config():
    """LookupNode accepte une configuration personnalisée."""
    config = LookupConfig(
        include_alternatives=False,
        include_availability=False,
    )
    node = LookupNode(config=config)
    assert node.config is config
    assert node.config.include_alternatives is False


def test_lookup_node_input_ports():
    """LookupNode définit les ports d'entrée corrects."""
    node = LookupNode()
    assert len(node.input_ports) == 2

    # Port component_spec
    spec_port = node.input_ports[0]
    assert spec_port.name == "component_spec"
    assert spec_port.direction == PortDirection.INPUT
    assert spec_port.port_type == "string"
    assert spec_port.optional is False

    # Port requirements
    req_port = node.input_ports[1]
    assert req_port.name == "requirements"
    assert req_port.direction == PortDirection.INPUT
    assert req_port.port_type == "json"
    assert req_port.optional is True


def test_lookup_node_output_ports():
    """LookupNode définit les ports de sortie corrects."""
    node = LookupNode()
    assert len(node.output_ports) == 2

    # Port alternatives
    alt_port = node.output_ports[0]
    assert alt_port.name == "alternatives"
    assert alt_port.direction == PortDirection.OUTPUT
    assert alt_port.port_type == "json"

    # Port best_match
    match_port = node.output_ports[1]
    assert match_port.name == "best_match"
    assert match_port.direction == PortDirection.OUTPUT
    assert match_port.port_type == "json"


@pytest.mark.asyncio
async def test_lookup_node_execute_missing_component_spec():
    """LookupNode lève ValueError si component_spec est manquant."""
    node = LookupNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "component_spec" in str(exc_info.value)


@pytest.mark.asyncio
async def test_lookup_node_execute_empty_component_spec():
    """LookupNode lève ValueError si component_spec est vide."""
    node = LookupNode()
    inputs = {"component_spec": ""}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "component_spec" in str(exc_info.value)


@pytest.mark.asyncio
async def test_lookup_node_execute_basic():
    """LookupNode exécute une recherche de composant basique."""
    node = LookupNode()
    inputs = {"component_spec": "10kΩ resistor 0805"}

    result = await node.execute(inputs)

    assert "alternatives" in result
    assert "best_match" in result
    assert isinstance(result["alternatives"], list)
    assert len(result["alternatives"]) > 0
    assert isinstance(result["best_match"], dict)


@pytest.mark.asyncio
async def test_lookup_node_execute_with_requirements():
    """LookupNode accepte des requirements optionnels."""
    node = LookupNode()
    inputs = {
        "component_spec": "10kΩ resistor 0805",
        "requirements": {"tolerance": "1%", "voltage": "50V"},
    }

    result = await node.execute(inputs)

    assert "alternatives" in result
    assert "best_match" in result


@pytest.mark.asyncio
async def test_lookup_node_execute_without_alternatives():
    """LookupNode peut désactiver les alternatives."""
    config = LookupConfig(include_alternatives=False)
    node = LookupNode(config=config)
    inputs = {"component_spec": "10kΩ resistor 0805"}

    result = await node.execute(inputs)

    assert "alternatives" in result
    assert "best_match" in result


# Tests pour JlcpcbOptimizationNode


def test_jlcpcb_optimization_node_creation():
    """JlcpcbOptimizationNode peut être créé."""
    node = JlcpcbOptimizationNode()
    assert node.node_type == "electronics.component.jlcpcb_optimization"
    assert isinstance(node.config, JlcpcbOptimizationConfig)


def test_jlcpcb_optimization_node_input_ports():
    """JlcpcbOptimizationNode définit les ports d'entrée corrects."""
    node = JlcpcbOptimizationNode()
    assert len(node.input_ports) == 2

    # Port requirements
    req_port = node.input_ports[0]
    assert req_port.name == "requirements"
    assert req_port.direction == PortDirection.INPUT
    assert req_port.port_type == "json"
    assert req_port.optional is False

    # Port prefer_basic
    basic_port = node.input_ports[1]
    assert basic_port.name == "prefer_basic"
    assert basic_port.direction == PortDirection.INPUT
    assert basic_port.port_type == "boolean"
    assert basic_port.optional is True
    assert basic_port.default_value is True


def test_jlcpcb_optimization_node_output_ports():
    """JlcpcbOptimizationNode définit les ports de sortie corrects."""
    node = JlcpcbOptimizationNode()
    assert len(node.output_ports) == 2

    # Port optimized_bom
    bom_port = node.output_ports[0]
    assert bom_port.name == "optimized_bom"
    assert bom_port.direction == PortDirection.OUTPUT
    assert bom_port.port_type == "json"

    # Port summary
    summary_port = node.output_ports[1]
    assert summary_port.name == "summary"
    assert summary_port.direction == PortDirection.OUTPUT
    assert summary_port.port_type == "json"


@pytest.mark.asyncio
async def test_jlcpcb_optimization_node_execute_missing_requirements():
    """JlcpcbOptimizationNode lève ValueError si requirements est manquant."""
    node = JlcpcbOptimizationNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "requirements" in str(exc_info.value)


@pytest.mark.asyncio
async def test_jlcpcb_optimization_node_execute_basic():
    """JlcpcbOptimizationNode optimise la sélection des composants."""
    node = JlcpcbOptimizationNode()
    inputs = {
        "requirements": {
            "resistors": [{"value": "10k", "quantity": 3}],
            "capacitors": [{"value": "100nF", "quantity": 2}],
        }
    }

    result = await node.execute(inputs)

    assert "optimized_bom" in result
    assert "summary" in result
    assert isinstance(result["optimized_bom"], list)
    assert len(result["optimized_bom"]) > 0

    summary = result["summary"]
    assert "total_components" in summary
    assert "basic_parts" in summary
    assert "extended_parts" in summary
    assert "estimated_cost" in summary


@pytest.mark.asyncio
async def test_jlcpcb_optimization_node_execute_prefer_basic():
    """JlcpcbOptimizationNode préfère les pièces basiques."""
    node = JlcpcbOptimizationNode()
    inputs = {
        "requirements": {"resistors": [{"value": "10k", "quantity": 3}]},
        "prefer_basic": True,
    }

    result = await node.execute(inputs)

    summary = result["summary"]
    assert summary["basic_parts"] > 0


# Tests pour BomGeneratorNode


def test_bom_generator_node_creation():
    """BomGeneratorNode peut être créé."""
    node = BomGeneratorNode()
    assert node.node_type == "electronics.component.bom_generator"
    assert isinstance(node.config, BomGeneratorConfig)


def test_bom_generator_node_input_ports():
    """BomGeneratorNode définit les ports d'entrée corrects."""
    node = BomGeneratorNode()
    assert len(node.input_ports) == 2

    # Port circuit_description
    desc_port = node.input_ports[0]
    assert desc_port.name == "circuit_description"
    assert desc_port.direction == PortDirection.INPUT
    assert desc_port.port_type == "string"
    assert desc_port.optional is False

    # Port components
    comp_port = node.input_ports[1]
    assert comp_port.name == "components"
    assert comp_port.direction == PortDirection.INPUT
    assert comp_port.port_type == "json"
    assert comp_port.optional is True


def test_bom_generator_node_output_ports():
    """BomGeneratorNode définit les ports de sortie corrects."""
    node = BomGeneratorNode()
    assert len(node.output_ports) == 2

    # Port bom
    bom_port = node.output_ports[0]
    assert bom_port.name == "bom"
    assert bom_port.direction == PortDirection.OUTPUT
    assert bom_port.port_type == "string"

    # Port bom_json
    json_port = node.output_ports[1]
    assert json_port.name == "bom_json"
    assert json_port.direction == PortDirection.OUTPUT
    assert json_port.port_type == "json"


@pytest.mark.asyncio
async def test_bom_generator_node_execute_missing_circuit_description():
    """BomGeneratorNode lève ValueError si circuit_description est manquant."""
    node = BomGeneratorNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "circuit_description" in str(exc_info.value)


@pytest.mark.asyncio
async def test_bom_generator_node_execute_empty_circuit_description():
    """BomGeneratorNode lève ValueError si circuit_description est vide."""
    node = BomGeneratorNode()
    inputs = {"circuit_description": ""}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "circuit_description" in str(exc_info.value)


@pytest.mark.asyncio
async def test_bom_generator_node_execute_basic():
    """BomGeneratorNode génère un BOM de base."""
    node = BomGeneratorNode()
    inputs = {"circuit_description": "Simple LED circuit with 3 resistors and 2 capacitors"}

    result = await node.execute(inputs)

    assert "bom" in result
    assert "bom_json" in result
    assert isinstance(result["bom"], str)
    assert isinstance(result["bom_json"], list)
    assert len(result["bom"]) > 0
    assert len(result["bom_json"]) > 0


@pytest.mark.asyncio
async def test_bom_generator_node_execute_with_components():
    """BomGeneratorNode accepte des composants pré-sélectionnés."""
    node = BomGeneratorNode()
    inputs = {
        "circuit_description": "Custom circuit",
        "components": [
            {"lcsc_part_number": "C17414", "quantity": 3},
            {"lcsc_part_number": "C49678", "quantity": 2},
        ],
    }

    result = await node.execute(inputs)

    assert "bom" in result
    assert "bom_json" in result


@pytest.mark.asyncio
async def test_bom_generator_node_execute_csv_format():
    """BomGeneratorNode génère un BOM au format CSV."""
    config = BomGeneratorConfig(format="csv")
    node = BomGeneratorNode(config=config)
    inputs = {"circuit_description": "Test circuit"}

    result = await node.execute(inputs)

    bom_csv = result["bom"]
    assert isinstance(bom_csv, str)
    assert len(bom_csv) > 0


# Tests pour CplGeneratorNode


def test_cpl_generator_node_creation():
    """CplGeneratorNode peut être créé."""
    node = CplGeneratorNode()
    assert node.node_type == "electronics.component.cpl_generator"
    assert isinstance(node.config, CplGeneratorConfig)


def test_cpl_generator_node_input_ports():
    """CplGeneratorNode définit les ports d'entrée corrects."""
    node = CplGeneratorNode()
    assert len(node.input_ports) == 2

    # Port pcb_description
    desc_port = node.input_ports[0]
    assert desc_port.name == "pcb_description"
    assert desc_port.direction == PortDirection.INPUT
    assert desc_port.port_type == "string"
    assert desc_port.optional is False

    # Port components
    comp_port = node.input_ports[1]
    assert comp_port.name == "components"
    assert comp_port.direction == PortDirection.INPUT
    assert comp_port.port_type == "json"
    assert comp_port.optional is False


def test_cpl_generator_node_output_ports():
    """CplGeneratorNode définit les ports de sortie corrects."""
    node = CplGeneratorNode()
    assert len(node.output_ports) == 2

    # Port cpl
    cpl_port = node.output_ports[0]
    assert cpl_port.name == "cpl"
    assert cpl_port.direction == PortDirection.OUTPUT
    assert cpl_port.port_type == "string"

    # Port cpl_json
    json_port = node.output_ports[1]
    assert json_port.name == "cpl_json"
    assert json_port.direction == PortDirection.OUTPUT
    assert json_port.port_type == "json"


@pytest.mark.asyncio
async def test_cpl_generator_node_execute_missing_pcb_description():
    """CplGeneratorNode lève ValueError si pcb_description est manquant."""
    node = CplGeneratorNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "pcb_description" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cpl_generator_node_execute_empty_pcb_description():
    """CplGeneratorNode lève ValueError si pcb_description est vide."""
    node = CplGeneratorNode()
    inputs = {"pcb_description": ""}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "pcb_description" in str(exc_info.value)


# Tests pour AvailabilityCheckNode


def test_availability_check_node_creation():
    """AvailabilityCheckNode peut être créé."""
    node = AvailabilityCheckNode()
    assert node.node_type == "electronics.component.availability_check"
    assert isinstance(node.config, AvailabilityCheckConfig)


def test_availability_check_node_input_ports():
    """AvailabilityCheckNode définit les ports d'entrée corrects."""
    node = AvailabilityCheckNode()
    assert len(node.input_ports) == 2

    # Port part_numbers
    parts_port = node.input_ports[0]
    assert parts_port.name == "part_numbers"
    assert parts_port.direction == PortDirection.INPUT
    assert parts_port.port_type == "json"
    assert parts_port.optional is False

    # Port check_alternatives
    alt_port = node.input_ports[1]
    assert alt_port.name == "check_alternatives"
    assert alt_port.direction == PortDirection.INPUT
    assert alt_port.port_type == "boolean"
    assert alt_port.optional is True


def test_availability_check_node_output_ports():
    """AvailabilityCheckNode définit les ports de sortie corrects."""
    node = AvailabilityCheckNode()
    assert len(node.output_ports) == 2

    # Port availability
    avail_port = node.output_ports[0]
    assert avail_port.name == "availability"
    assert avail_port.direction == PortDirection.OUTPUT
    assert avail_port.port_type == "json"

    # Port recommendations
    rec_port = node.output_ports[1]
    assert rec_port.name == "recommendations"
    assert rec_port.direction == PortDirection.OUTPUT
    assert rec_port.port_type == "json"


@pytest.mark.asyncio
async def test_availability_check_node_execute_missing_part_numbers():
    """AvailabilityCheckNode lève ValueError si part_numbers est manquant."""
    node = AvailabilityCheckNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "part_numbers" in str(exc_info.value)


@pytest.mark.asyncio
async def test_availability_check_node_execute_empty_part_numbers():
    """AvailabilityCheckNode lève ValueError si part_numbers est vide."""
    node = AvailabilityCheckNode()
    inputs = {"part_numbers": None}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "part_numbers" in str(exc_info.value)


# Tests pour DatasheetNode


def test_datasheet_node_creation():
    """DatasheetNode peut être créé."""
    node = DatasheetNode()
    assert node.node_type == "electronics.component.datasheet"
    assert isinstance(node.config, DatasheetConfig)


def test_datasheet_node_input_ports():
    """DatasheetNode définit les ports d'entrée corrects."""
    node = DatasheetNode()
    assert len(node.input_ports) == 2

    # Port component
    comp_port = node.input_ports[0]
    assert comp_port.name == "component"
    assert comp_port.direction == PortDirection.INPUT
    assert comp_port.port_type == "string"
    assert comp_port.optional is False

    # Port include_diagrams
    diag_port = node.input_ports[1]
    assert diag_port.name == "include_diagrams"
    assert diag_port.direction == PortDirection.INPUT
    assert diag_port.port_type == "boolean"
    assert diag_port.optional is True


def test_datasheet_node_output_ports():
    """DatasheetNode définit les ports de sortie corrects."""
    node = DatasheetNode()
    assert len(node.output_ports) == 3

    # Port datasheet_url
    url_port = node.output_ports[0]
    assert url_port.name == "datasheet_url"
    assert url_port.direction == PortDirection.OUTPUT
    assert url_port.port_type == "string"

    # Port parameters
    params_port = node.output_ports[1]
    assert params_port.name == "parameters"
    assert params_port.direction == PortDirection.OUTPUT
    assert params_port.port_type == "json"

    # Port summary
    summary_port = node.output_ports[2]
    assert summary_port.name == "summary"
    assert summary_port.direction == PortDirection.OUTPUT
    assert summary_port.port_type == "string"


@pytest.mark.asyncio
async def test_datasheet_node_execute_missing_component():
    """DatasheetNode lève ValueError si component est manquant."""
    node = DatasheetNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "component" in str(exc_info.value)


@pytest.mark.asyncio
async def test_datasheet_node_execute_empty_component():
    """DatasheetNode lève ValueError si component est vide."""
    node = DatasheetNode()
    inputs = {"component": None}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "component" in str(exc_info.value)


# Tests pour FindAlternativesNode


def test_find_alternatives_node_creation():
    """FindAlternativesNode peut être créé."""
    node = FindAlternativesNode()
    assert node.node_type == "electronics.component.find_alternatives"
    assert isinstance(node.config, FindAlternativesConfig)


def test_find_alternatives_node_input_ports():
    """FindAlternativesNode définit les ports d'entrée corrects."""
    node = FindAlternativesNode()
    assert len(node.input_ports) == 3

    # Port component_spec
    spec_port = node.input_ports[0]
    assert spec_port.name == "component_spec"
    assert spec_port.direction == PortDirection.INPUT
    assert spec_port.port_type == "string"
    assert spec_port.optional is False

    # Port requirements
    req_port = node.input_ports[1]
    assert req_port.name == "requirements"
    assert req_port.direction == PortDirection.INPUT
    assert req_port.port_type == "json"
    assert req_port.optional is True

    # Port max_results
    max_port = node.input_ports[2]
    assert max_port.name == "max_results"
    assert max_port.direction == PortDirection.INPUT
    assert max_port.port_type == "number"
    assert max_port.optional is True


def test_find_alternatives_node_output_ports():
    """FindAlternativesNode définit les ports de sortie corrects."""
    node = FindAlternativesNode()
    assert len(node.output_ports) == 3

    # Port alternatives
    alt_port = node.output_ports[0]
    assert alt_port.name == "alternatives"
    assert alt_port.direction == PortDirection.OUTPUT
    assert alt_port.port_type == "json"

    # Port pin_compatible
    pin_port = node.output_ports[1]
    assert pin_port.name == "pin_compatible"
    assert pin_port.direction == PortDirection.OUTPUT
    assert pin_port.port_type == "json"

    # Port functional_equiv
    func_port = node.output_ports[2]
    assert func_port.name == "functional_equiv"
    assert func_port.direction == PortDirection.OUTPUT
    assert func_port.port_type == "json"


@pytest.mark.asyncio
async def test_find_alternatives_node_execute_missing_component_spec():
    """FindAlternativesNode lève ValueError si component_spec est manquant."""
    node = FindAlternativesNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "component_spec" in str(exc_info.value)


@pytest.mark.asyncio
async def test_find_alternatives_node_execute_empty_component_spec():
    """FindAlternativesNode lève ValueError si component_spec est vide."""
    node = FindAlternativesNode()
    inputs = {"component_spec": ""}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "component_spec" in str(exc_info.value)
