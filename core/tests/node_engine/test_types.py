"""Tests pour les types de base du Node Engine."""

import pytest

from mascarade.node_engine.types import DomainType, NodeType, PortType


def test_domain_type_valid():
    """Un DomainType valide peut être créé."""
    dt = DomainType(
        domain="cad",
        name="MeshData",
        schema={"type": "object", "properties": {"vertices": {"type": "array"}}},
    )
    assert dt.domain == "cad"
    assert dt.name == "MeshData"
    assert dt.schema["type"] == "object"


def test_domain_type_empty_domain():
    """Un DomainType sans domaine lève une ValueError."""
    with pytest.raises(ValueError, match="domain cannot be empty"):
        DomainType(domain="", name="Test", schema={"type": "object"})


def test_domain_type_empty_name():
    """Un DomainType sans nom lève une ValueError."""
    with pytest.raises(ValueError, match="name cannot be empty"):
        DomainType(domain="test", name="", schema={"type": "object"})


def test_domain_type_empty_schema():
    """Un DomainType sans schéma lève une ValueError."""
    with pytest.raises(ValueError, match="schema cannot be empty"):
        DomainType(domain="test", name="Test", schema={})


def test_domain_type_invalid_schema():
    """Un DomainType avec un schéma non-dict lève une ValueError."""
    with pytest.raises(ValueError, match="schema must be a dict"):
        DomainType(domain="test", name="Test", schema="not a dict")


def test_port_type_valid():
    """Un PortType valide peut être créé."""
    pt = PortType(name="input", type="string", required=True)
    assert pt.name == "input"
    assert pt.type == "string"
    assert pt.required is True


def test_port_type_optional():
    """Un PortType optionnel peut être créé."""
    pt = PortType(name="optional_param", type="number", required=False)
    assert pt.name == "optional_param"
    assert pt.type == "number"
    assert pt.required is False


def test_port_type_default_required():
    """Un PortType est requis par défaut."""
    pt = PortType(name="input", type="string")
    assert pt.required is True


def test_port_type_empty_name():
    """Un PortType sans nom lève une ValueError."""
    with pytest.raises(ValueError, match="name cannot be empty"):
        PortType(name="", type="string")


def test_port_type_empty_type():
    """Un PortType sans type lève une ValueError."""
    with pytest.raises(ValueError, match="type cannot be empty"):
        PortType(name="input", type="")


def test_node_type_valid():
    """Un NodeType valide peut être créé."""
    nt = NodeType(
        id="cad.freecad.create_document",
        category="CAD / FreeCAD",
        inputs=[PortType(name="name", type="string")],
        outputs=[PortType(name="document", type="cad.CADDocument")],
    )
    assert nt.id == "cad.freecad.create_document"
    assert nt.category == "CAD / FreeCAD"
    assert len(nt.inputs) == 1
    assert len(nt.outputs) == 1


def test_node_type_empty_id():
    """Un NodeType sans ID lève une ValueError."""
    with pytest.raises(ValueError, match="id cannot be empty"):
        NodeType(id="", category="Test")


def test_node_type_empty_category():
    """Un NodeType sans catégorie lève une ValueError."""
    with pytest.raises(ValueError, match="category cannot be empty"):
        NodeType(id="test.node", category="")


def test_node_type_default_ports():
    """Un NodeType peut être créé sans entrées ni sorties."""
    nt = NodeType(id="test.node", category="Test")
    assert nt.inputs == []
    assert nt.outputs == []


def test_node_type_invalid_inputs():
    """Un NodeType avec inputs non-list lève une ValueError."""
    with pytest.raises(ValueError, match="inputs must be a list"):
        NodeType(id="test.node", category="Test", inputs="not a list")


def test_node_type_invalid_outputs():
    """Un NodeType avec outputs non-list lève une ValueError."""
    with pytest.raises(ValueError, match="outputs must be a list"):
        NodeType(id="test.node", category="Test", outputs="not a list")


def test_node_type_multiple_ports():
    """Un NodeType peut avoir plusieurs entrées et sorties."""
    nt = NodeType(
        id="test.multi",
        category="Test",
        inputs=[
            PortType(name="a", type="number"),
            PortType(name="b", type="number"),
        ],
        outputs=[
            PortType(name="sum", type="number"),
            PortType(name="product", type="number"),
        ],
    )
    assert len(nt.inputs) == 2
    assert len(nt.outputs) == 2
    assert nt.inputs[0].name == "a"
    assert nt.outputs[1].name == "product"
