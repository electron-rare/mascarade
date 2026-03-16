"""Types de base pour le Node Engine — DomainType, PortType, NodeType."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DomainType:
    """Type de domaine pour validation des données entre nœuds."""

    domain: str
    name: str
    schema: dict[str, Any]

    def __post_init__(self) -> None:
        """Valider les champs requis."""
        if not self.domain:
            raise ValueError("domain cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if not self.schema:
            raise ValueError("schema cannot be empty")
        if not isinstance(self.schema, dict):
            raise ValueError("schema must be a dict")


@dataclass
class PortType:
    """Définition d'un port d'entrée ou de sortie pour un nœud."""

    name: str
    type: str
    required: bool = True

    def __post_init__(self) -> None:
        """Valider les champs requis."""
        if not self.name:
            raise ValueError("name cannot be empty")
        if not self.type:
            raise ValueError("type cannot be empty")


@dataclass
class NodeType:
    """Définition d'un type de nœud avec ses entrées et sorties."""

    id: str
    category: str
    inputs: list[PortType] = field(default_factory=list)
    outputs: list[PortType] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Valider les champs requis."""
        if not self.id:
            raise ValueError("id cannot be empty")
        if not self.category:
            raise ValueError("category cannot be empty")
        if not isinstance(self.inputs, list):
            raise ValueError("inputs must be a list")
        if not isinstance(self.outputs, list):
            raise ValueError("outputs must be a list")
