"""Tests for node engine core type system."""

import pytest
from pydantic import ValidationError

from mascarade.node_engine.types import DomainType, PortType


def test_domain_type_creation():
    """Test basic DomainType creation."""
    domain_type = DomainType(
        domain="ai",
        name="LLMResponse",
        schema={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "model": {"type": "string"},
            },
            "required": ["content", "model"],
        },
    )
    assert domain_type.domain == "ai"
    assert domain_type.name == "LLMResponse"
    assert domain_type.qualified_name == "ai.LLMResponse"
    assert domain_type.schema["type"] == "object"


def test_domain_type_qualified_name():
    """Test qualified name property."""
    domain_type = DomainType(
        domain="cad",
        name="Sketch",
        schema={"type": "object", "properties": {}},
    )
    assert domain_type.qualified_name == "cad.Sketch"


def test_domain_type_validation_missing_type():
    """Test schema validation requires 'type' field."""
    with pytest.raises(ValidationError) as exc_info:
        DomainType(
            domain="ai",
            name="Invalid",
            schema={"properties": {}},  # Missing 'type'
        )
    assert "schema must include a 'type' field" in str(exc_info.value)


def test_domain_type_validation_empty_domain():
    """Test validation rejects empty domain."""
    with pytest.raises(ValidationError):
        DomainType(
            domain="",
            name="Test",
            schema={"type": "object"},
        )


def test_domain_type_validation_empty_name():
    """Test validation rejects empty name."""
    with pytest.raises(ValidationError):
        DomainType(
            domain="ai",
            name="",
            schema={"type": "object"},
        )


def test_domain_type_immutable():
    """Test that DomainType instances are immutable."""
    domain_type = DomainType(
        domain="ai",
        name="Test",
        schema={"type": "object"},
    )
    with pytest.raises(ValidationError):
        domain_type.domain = "cad"


def test_port_type_creation():
    """Test basic PortType creation."""
    port = PortType(
        name="prompt",
        type="string",
        required=True,
        description="The user prompt",
    )
    assert port.name == "prompt"
    assert port.type == "string"
    assert port.required is True
    assert port.description == "The user prompt"


def test_port_type_defaults():
    """Test PortType default values."""
    port = PortType(name="output", type="string")
    assert port.required is True
    assert port.description is None


def test_port_type_validation_empty_name():
    """Test validation rejects empty port name."""
    with pytest.raises(ValidationError):
        PortType(name="", type="string")


def test_port_type_validation_empty_type():
    """Test validation rejects empty type."""
    with pytest.raises(ValidationError):
        PortType(name="test", type="")


def test_port_type_is_primitive():
    """Test primitive type detection."""
    assert PortType(name="p1", type="string").is_primitive is True
    assert PortType(name="p2", type="number").is_primitive is True
    assert PortType(name="p3", type="boolean").is_primitive is True
    assert PortType(name="p4", type="json").is_primitive is True
    assert PortType(name="p5", type="void").is_primitive is True
    assert PortType(name="p6", type="ai.LLMResponse").is_primitive is False
    assert PortType(name="p7", type="cad.Sketch").is_primitive is False


def test_port_type_is_stream():
    """Test stream type detection."""
    assert PortType(name="p1", type="stream<string>").is_stream is True
    assert PortType(name="p2", type="stream<ai.LLMResponse>").is_stream is True
    assert PortType(name="p3", type="string").is_stream is False
    assert PortType(name="p4", type="ai.LLMResponse").is_stream is False


def test_port_type_is_array():
    """Test array type detection."""
    assert PortType(name="p1", type="array<string>").is_array is True
    assert PortType(name="p2", type="array<ai.LLMResponse>").is_array is True
    assert PortType(name="p3", type="string").is_array is False
    assert PortType(name="p4", type="ai.LLMResponse").is_array is False


def test_port_type_is_map():
    """Test map type detection."""
    assert PortType(name="p1", type="map<string,number>").is_map is True
    assert PortType(name="p2", type="map<string,ai.LLMResponse>").is_map is True
    assert PortType(name="p3", type="string").is_map is False
    assert PortType(name="p4", type="ai.LLMResponse").is_map is False


def test_port_type_immutable():
    """Test that PortType instances are immutable."""
    port = PortType(name="test", type="string")
    with pytest.raises(ValidationError):
        port.name = "changed"


def test_port_type_with_domain_specific_type():
    """Test PortType with domain-specific types."""
    port = PortType(
        name="response",
        type="ai.LLMResponse",
        required=True,
        description="LLM response object",
    )
    assert port.type == "ai.LLMResponse"
    assert port.is_primitive is False


def test_port_type_with_generic_types():
    """Test PortType with generic types like array<T> and map<K,V>."""
    array_port = PortType(name="messages", type="array<string>")
    assert array_port.is_array is True
    assert array_port.is_primitive is False

    map_port = PortType(name="metadata", type="map<string,string>")
    assert map_port.is_map is True
    assert map_port.is_primitive is False

    stream_port = PortType(name="tokens", type="stream<string>")
    assert stream_port.is_stream is True
    assert stream_port.is_primitive is False
