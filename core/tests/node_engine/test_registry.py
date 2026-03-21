"""Tests pour le registre de types de nœuds."""

import pytest

from mascarade.node_engine.registry import NodeTypeRegistry
from mascarade.node_engine.types import DomainType, NodeType, PortType


def test_registry_register_and_get_node():
    """Enregistrer et récupérer un type de nœud."""
    reg = NodeTypeRegistry(storage_path=None)
    node = NodeType(id="test.node", category="Test")
    reg.register_node(node)
    assert reg.get_node("test.node") is node


def test_registry_list_nodes():
    """Lister tous les types de nœuds."""
    reg = NodeTypeRegistry(storage_path=None)
    reg.register_node(NodeType(id="test.a", category="Test"))
    reg.register_node(NodeType(id="test.b", category="Test"))
    assert len(reg.list_nodes()) == 2


def test_registry_list_nodes_by_category():
    """Lister les types de nœuds filtrés par catégorie."""
    reg = NodeTypeRegistry(storage_path=None)
    reg.register_node(NodeType(id="cad.a", category="CAD"))
    reg.register_node(NodeType(id="cad.b", category="CAD"))
    reg.register_node(NodeType(id="data.a", category="Data"))
    cad_nodes = reg.list_nodes(category="CAD")
    assert len(cad_nodes) == 2
    assert all(n.category == "CAD" for n in cad_nodes)


def test_registry_remove_node():
    """Supprimer un type de nœud."""
    reg = NodeTypeRegistry(storage_path=None)
    reg.register_node(NodeType(id="test.remove", category="Test"))
    reg.remove_node("test.remove")
    with pytest.raises(KeyError):
        reg.get_node("test.remove")


def test_registry_get_missing_node():
    """Récupérer un type de nœud inexistant lève une KeyError."""
    reg = NodeTypeRegistry(storage_path=None)
    with pytest.raises(KeyError, match="Node type 'missing' non trouvé"):
        reg.get_node("missing")


def test_registry_is_builtin_node():
    """Vérifier si un type de nœud est builtin."""
    reg = NodeTypeRegistry(storage_path=None)
    reg.register_node(NodeType(id="builtin", category="Test"), builtin=True)
    reg.register_node(NodeType(id="dynamic", category="Test"))
    assert reg.is_builtin_node("builtin") is True
    assert reg.is_builtin_node("dynamic") is False


def test_registry_register_and_get_domain_type():
    """Enregistrer et récupérer un type de domaine."""
    reg = NodeTypeRegistry(storage_path=None)
    domain_type = DomainType(domain="cad", name="MeshData", schema={"type": "object"})
    reg.register_domain_type(domain_type)
    retrieved = reg.get_domain_type("cad", "MeshData")
    assert retrieved is domain_type


def test_registry_list_domain_types():
    """Lister tous les types de domaine."""
    reg = NodeTypeRegistry(storage_path=None)
    reg.register_domain_type(
        DomainType(domain="cad", name="MeshData", schema={"type": "object"})
    )
    reg.register_domain_type(
        DomainType(domain="cad", name="Toolpath", schema={"type": "object"})
    )
    assert len(reg.list_domain_types()) == 2


def test_registry_list_domain_types_by_domain():
    """Lister les types de domaine filtrés par domaine."""
    reg = NodeTypeRegistry(storage_path=None)
    reg.register_domain_type(
        DomainType(domain="cad", name="MeshData", schema={"type": "object"})
    )
    reg.register_domain_type(
        DomainType(domain="data", name="DataFrame", schema={"type": "object"})
    )
    cad_types = reg.list_domain_types(domain="cad")
    assert len(cad_types) == 1
    assert cad_types[0].domain == "cad"


def test_registry_remove_domain_type():
    """Supprimer un type de domaine."""
    reg = NodeTypeRegistry(storage_path=None)
    reg.register_domain_type(
        DomainType(domain="test", name="Remove", schema={"type": "object"})
    )
    reg.remove_domain_type("test", "Remove")
    with pytest.raises(KeyError):
        reg.get_domain_type("test", "Remove")


def test_registry_get_missing_domain_type():
    """Récupérer un type de domaine inexistant lève une KeyError."""
    reg = NodeTypeRegistry(storage_path=None)
    with pytest.raises(KeyError, match="Domain type 'test.missing' non trouvé"):
        reg.get_domain_type("test", "missing")


def test_registry_is_builtin_domain_type():
    """Vérifier si un type de domaine est builtin."""
    reg = NodeTypeRegistry(storage_path=None)
    reg.register_domain_type(
        DomainType(domain="core", name="Builtin", schema={"type": "object"}),
        builtin=True,
    )
    reg.register_domain_type(
        DomainType(domain="core", name="Dynamic", schema={"type": "object"})
    )
    assert reg.is_builtin_domain_type("core", "Builtin") is True
    assert reg.is_builtin_domain_type("core", "Dynamic") is False


def test_registry_contains():
    """Vérifier la présence d'un type dans le registre."""
    reg = NodeTypeRegistry(storage_path=None)
    reg.register_node(NodeType(id="test.node", category="Test"))
    reg.register_domain_type(
        DomainType(domain="cad", name="MeshData", schema={"type": "object"})
    )
    assert "test.node" in reg
    assert "cad.MeshData" in reg
    assert "missing" not in reg


def test_registry_len():
    """Compter le nombre total de types."""
    reg = NodeTypeRegistry(storage_path=None)
    reg.register_node(NodeType(id="test.a", category="Test"))
    reg.register_node(NodeType(id="test.b", category="Test"))
    reg.register_domain_type(
        DomainType(domain="cad", name="MeshData", schema={"type": "object"})
    )
    assert len(reg) == 3


def test_registry_save_and_load(tmp_path):
    """Les types dynamiques sont persistés et rechargés."""
    storage = tmp_path / "node_types.json"

    reg = NodeTypeRegistry(storage_path=storage)
    reg.register_node(NodeType(id="builtin", category="Test"), builtin=True)
    reg.register_node(NodeType(id="dynamic", category="Test"))
    reg.register_domain_type(
        DomainType(domain="core", name="Builtin", schema={"type": "object"}),
        builtin=True,
    )
    reg.register_domain_type(
        DomainType(domain="core", name="Dynamic", schema={"type": "object"})
    )
    reg.save()

    reg2 = NodeTypeRegistry(storage_path=storage)
    reg2.load()
    assert "dynamic" in reg2
    assert "builtin" not in reg2
    assert "core.Dynamic" in reg2
    assert "core.Builtin" not in reg2


def test_registry_save_noop_when_disabled():
    """Pas d'erreur si storage_path=None."""
    reg = NodeTypeRegistry(storage_path=None)
    reg.register_node(NodeType(id="test", category="Test"))
    reg.save()


def test_registry_load_noop_when_no_file(tmp_path):
    """Pas d'erreur si le fichier n'existe pas."""
    storage = tmp_path / "nonexistent.json"
    reg = NodeTypeRegistry(storage_path=storage)
    reg.load()
    assert len(reg) == 0


def test_registry_save_preserves_node_structure(tmp_path):
    """La sauvegarde préserve la structure complète des nœuds."""
    storage = tmp_path / "node_types.json"

    reg = NodeTypeRegistry(storage_path=storage)
    node = NodeType(
        id="test.complex",
        category="Test",
        inputs=[
            PortType(name="a", type="number", required=True),
            PortType(name="b", type="string", required=False),
        ],
        outputs=[PortType(name="result", type="json")],
    )
    reg.register_node(node)
    reg.save()

    reg2 = NodeTypeRegistry(storage_path=storage)
    reg2.load()
    loaded = reg2.get_node("test.complex")
    assert loaded.id == "test.complex"
    assert loaded.category == "Test"
    assert len(loaded.inputs) == 2
    assert loaded.inputs[0].name == "a"
    assert loaded.inputs[0].required is True
    assert loaded.inputs[1].required is False
    assert len(loaded.outputs) == 1


def test_registry_save_preserves_domain_schema(tmp_path):
    """La sauvegarde préserve le schéma des types de domaine."""
    storage = tmp_path / "node_types.json"

    reg = NodeTypeRegistry(storage_path=storage)
    domain_type = DomainType(
        domain="cad",
        name="MeshData",
        schema={
            "type": "object",
            "properties": {
                "vertices": {"type": "array"},
                "faces": {"type": "array"},
            },
            "required": ["vertices", "faces"],
        },
    )
    reg.register_domain_type(domain_type)
    reg.save()

    reg2 = NodeTypeRegistry(storage_path=storage)
    reg2.load()
    loaded = reg2.get_domain_type("cad", "MeshData")
    assert loaded.domain == "cad"
    assert loaded.name == "MeshData"
    assert loaded.schema["type"] == "object"
    assert "vertices" in loaded.schema["properties"]
    assert loaded.schema["required"] == ["vertices", "faces"]
