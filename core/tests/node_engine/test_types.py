"""Tests pour les types de domaine et les ports."""

from mascarade.node_engine.types import DomainType, PortDirection, PortType


def test_domain_type_full_name():
    """Le nom complet combine le domaine et le nom."""
    dt = DomainType(
        domain="electronics",
        name="Netlist",
        schema={"type": "object"},
    )
    assert dt.full_name == "electronics.Netlist"


def test_domain_type_validate_schema_object_valid():
    """Validation réussie pour un objet conforme au schéma."""
    dt = DomainType(
        domain="electronics",
        name="Netlist",
        schema={
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["spice", "kicad"]},
                "content": {"type": "string"},
            },
            "required": ["format", "content"],
        },
    )
    data = {"format": "spice", "content": "* SPICE netlist\n.end"}
    valid, error = dt.validate_schema(data)
    assert valid is True
    assert error is None


def test_domain_type_validate_schema_missing_required():
    """Validation échoue si un champ requis manque."""
    dt = DomainType(
        domain="electronics",
        name="Netlist",
        schema={
            "type": "object",
            "properties": {
                "format": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["format", "content"],
        },
    )
    data = {"format": "spice"}
    valid, error = dt.validate_schema(data)
    assert valid is False
    assert "content" in error


def test_domain_type_validate_schema_wrong_type():
    """Validation échoue si le type de données est incorrect."""
    dt = DomainType(
        domain="test",
        name="Example",
        schema={"type": "object"},
    )
    valid, error = dt.validate_schema("not an object")
    assert valid is False
    assert "Expected object" in error


def test_domain_type_validate_schema_enum_violation():
    """Validation échoue si une valeur enum est invalide."""
    dt = DomainType(
        domain="electronics",
        name="Netlist",
        schema={
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["spice", "kicad"]},
            },
            "required": ["format"],
        },
    )
    data = {"format": "invalid"}
    valid, error = dt.validate_schema(data)
    assert valid is False
    assert "enum" in error


def test_domain_type_validate_schema_union_type():
    """Validation réussie pour les types union (ex: string|null)."""
    dt = DomainType(
        domain="test",
        name="Optional",
        schema={
            "type": "object",
            "properties": {
                "value": {"type": ["string", "null"]},
            },
        },
    )
    valid_str, _ = dt.validate_schema({"value": "hello"})
    valid_null, _ = dt.validate_schema({"value": None})
    assert valid_str is True
    assert valid_null is True


def test_domain_type_validate_schema_primitive_types():
    """Validation des types primitifs."""
    string_type = DomainType(domain="test", name="String", schema={"type": "string"})
    valid, _ = string_type.validate_schema("hello")
    assert valid is True
    valid, error = string_type.validate_schema(123)
    assert valid is False

    int_type = DomainType(domain="test", name="Integer", schema={"type": "integer"})
    valid, _ = int_type.validate_schema(42)
    assert valid is True
    valid, error = int_type.validate_schema("42")
    assert valid is False

    bool_type = DomainType(domain="test", name="Boolean", schema={"type": "boolean"})
    valid, _ = bool_type.validate_schema(True)
    assert valid is True
    valid, error = bool_type.validate_schema(1)
    assert valid is False

    array_type = DomainType(domain="test", name="Array", schema={"type": "array"})
    valid, _ = array_type.validate_schema([1, 2, 3])
    assert valid is True
    valid, error = array_type.validate_schema("not array")
    assert valid is False


def test_port_type_is_compatible_with():
    """Deux ports sont compatibles si directions opposées et même type."""
    input_port = PortType(
        name="input",
        direction=PortDirection.INPUT,
        port_type="string",
    )
    output_port = PortType(
        name="output",
        direction=PortDirection.OUTPUT,
        port_type="string",
    )
    assert input_port.is_compatible_with(output_port) is True
    assert output_port.is_compatible_with(input_port) is True


def test_port_type_incompatible_same_direction():
    """Deux ports de même direction ne sont pas compatibles."""
    port1 = PortType(name="a", direction=PortDirection.INPUT, port_type="string")
    port2 = PortType(name="b", direction=PortDirection.INPUT, port_type="string")
    assert port1.is_compatible_with(port2) is False


def test_port_type_incompatible_different_types():
    """Deux ports de types différents ne sont pas compatibles."""
    input_port = PortType(
        name="input",
        direction=PortDirection.INPUT,
        port_type="string",
    )
    output_port = PortType(
        name="output",
        direction=PortDirection.OUTPUT,
        port_type="integer",
    )
    assert input_port.is_compatible_with(output_port) is False


def test_port_type_validate_value_builtin_types():
    """Validation des valeurs pour les types intégrés."""
    string_port = PortType(name="s", direction=PortDirection.INPUT, port_type="string")
    valid, _ = string_port.validate_value("hello")
    assert valid is True
    valid, error = string_port.validate_value(123)
    assert valid is False
    assert "string" in error

    int_port = PortType(name="i", direction=PortDirection.INPUT, port_type="integer")
    valid, _ = int_port.validate_value(42)
    assert valid is True
    valid, error = int_port.validate_value("42")
    assert valid is False

    bool_port = PortType(name="b", direction=PortDirection.INPUT, port_type="boolean")
    valid, _ = bool_port.validate_value(True)
    assert valid is True
    valid, error = bool_port.validate_value(1)
    assert valid is False

    json_port = PortType(name="j", direction=PortDirection.INPUT, port_type="json")
    valid, _ = json_port.validate_value({"key": "value"})
    assert valid is True
    valid, _ = json_port.validate_value([1, 2, 3])
    assert valid is True
    valid, error = json_port.validate_value("not json")
    assert valid is False

    binary_port = PortType(name="bin", direction=PortDirection.INPUT, port_type="binary")
    valid, _ = binary_port.validate_value(b"binary data")
    assert valid is True
    valid, error = binary_port.validate_value("not binary")
    assert valid is False


def test_port_type_validate_value_optional():
    """Les ports optionnels acceptent None."""
    optional_port = PortType(
        name="opt",
        direction=PortDirection.INPUT,
        port_type="string",
        optional=True,
    )
    valid, _ = optional_port.validate_value(None)
    assert valid is True

    required_port = PortType(
        name="req",
        direction=PortDirection.INPUT,
        port_type="string",
        optional=False,
    )
    valid, error = required_port.validate_value(None)
    assert valid is False
    assert "required" in error


def test_port_type_validate_value_with_domain_type():
    """Validation d'un port avec type de domaine personnalisé."""
    domain_type = DomainType(
        domain="electronics",
        name="Netlist",
        schema={
            "type": "object",
            "properties": {"format": {"type": "string"}},
            "required": ["format"],
        },
    )
    port = PortType(
        name="netlist",
        direction=PortDirection.OUTPUT,
        port_type="electronics.Netlist",
    )

    domain_types = {"electronics.Netlist": domain_type}
    valid, _ = port.validate_value({"format": "spice"}, domain_types)
    assert valid is True

    valid, error = port.validate_value({"wrong": "data"}, domain_types)
    assert valid is False


def test_port_type_validate_value_array_type():
    """Validation basique des types array."""
    array_port = PortType(
        name="items",
        direction=PortDirection.INPUT,
        port_type="array<string>",
    )
    valid, _ = array_port.validate_value(["a", "b", "c"])
    assert valid is True
    valid, error = array_port.validate_value("not array")
    assert valid is False


def test_port_direction_enum():
    """PortDirection enum a les valeurs correctes."""
    assert PortDirection.INPUT.value == "input"
    assert PortDirection.OUTPUT.value == "output"
