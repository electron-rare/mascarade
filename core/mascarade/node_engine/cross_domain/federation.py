"""Federated execution planner for multi-machine graph execution.

Assigns graph nodes to machines based on domain capabilities, hardware
profiles, and resource constraints. This is the Phase 5 MVP planner --
it produces an ExecutionPlan describing which node runs where, without
performing actual distributed execution (that requires prima.cpp/Ray).

See SPEC-029-P5 for full specification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from mascarade.node_engine.graph import Graph

logger = logging.getLogger("mascarade.node_engine.cross_domain.federation")

# ---------------------------------------------------------------------------
# Domain -> capability requirement mapping
# ---------------------------------------------------------------------------

# Maps domain prefixes to the machine capabilities they require.
# A machine must advertise at least one of the listed capabilities
# to be eligible for executing nodes in that domain.
DOMAIN_CAPABILITY_MAP: dict[str, list[str]] = {
    "ai": ["gpu-inference", "llm-api", "cpu-inference"],
    "electronics": ["kicad-host", "spice-runtime", "cpu-compute"],
    "hardware": ["hardware-connected", "gpio-access", "serial-access"],
    "cad": ["docker-runtime", "freecad-host", "cpu-compute"],
    "midi": ["midi-interface", "hardware-connected"],
    "adapter": ["cpu-compute"],  # Adapters run anywhere
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class NodeAssignment:
    """Assignment of a single node to a machine."""

    node_id: str
    node_type: str
    machine_id: str
    machine_name: str
    reason: str
    estimated_memory_mb: int = 0
    requires_network: bool = False


@dataclass
class ResourceEstimate:
    """Estimated resource usage for executing the plan."""

    total_nodes: int = 0
    machines_used: int = 0
    estimated_memory_mb: int = 0
    estimated_network_transfers: int = 0
    cross_machine_edges: int = 0


@dataclass
class ExecutionPlan:
    """Plan describing which node runs on which machine.

    Produced by FederatedExecutor.plan(). Contains node-to-machine
    assignments and estimated resource usage. Does not execute anything.
    """

    graph_id: str
    assignments: list[NodeAssignment] = field(default_factory=list)
    resource_estimate: ResourceEstimate = field(default_factory=ResourceEstimate)
    unassigned_nodes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """True if every node has been assigned to a machine."""
        return len(self.unassigned_nodes) == 0

    @property
    def machine_summary(self) -> dict[str, list[str]]:
        """Map of machine_id -> list of assigned node_ids."""
        summary: dict[str, list[str]] = {}
        for a in self.assignments:
            summary.setdefault(a.machine_id, []).append(a.node_id)
        return summary

    def to_dict(self) -> dict[str, Any]:
        """Serialize the plan to a dictionary."""
        return {
            "graph_id": self.graph_id,
            "assignments": [
                {
                    "node_id": a.node_id,
                    "node_type": a.node_type,
                    "machine_id": a.machine_id,
                    "machine_name": a.machine_name,
                    "reason": a.reason,
                    "estimated_memory_mb": a.estimated_memory_mb,
                    "requires_network": a.requires_network,
                }
                for a in self.assignments
            ],
            "resource_estimate": {
                "total_nodes": self.resource_estimate.total_nodes,
                "machines_used": self.resource_estimate.machines_used,
                "estimated_memory_mb": self.resource_estimate.estimated_memory_mb,
                "estimated_network_transfers": self.resource_estimate.estimated_network_transfers,
                "cross_machine_edges": self.resource_estimate.cross_machine_edges,
            },
            "unassigned_nodes": self.unassigned_nodes,
            "warnings": self.warnings,
            "is_complete": self.is_complete,
        }


# ---------------------------------------------------------------------------
# MachineProfile helper
# ---------------------------------------------------------------------------


@dataclass
class MachineProfile:
    """Describes a machine's capabilities for federation planning.

    Can be constructed from a MACHINE_PROFILES.json entry or manually.
    """

    id: str
    name: str
    capabilities: list[str] = field(default_factory=list)
    gpu_vram_gb: float = 0.0
    ram_gb: float = 0.0
    max_concurrent: int = 10
    priority: int = 0  # Higher = preferred when multiple machines qualify

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MachineProfile:
        """Create a MachineProfile from a dictionary (e.g. JSON entry)."""
        return cls(
            id=data.get("id", data.get("name", "unknown")),
            name=data.get("name", "unknown"),
            capabilities=data.get("capabilities", []),
            gpu_vram_gb=data.get("gpu_vram_gb", 0.0),
            ram_gb=data.get("ram_gb", 0.0),
            max_concurrent=data.get("max_concurrent", 10),
            priority=data.get("priority", 0),
        )

    def has_capability(self, capability: str) -> bool:
        """Check if this machine has a specific capability."""
        return capability in self.capabilities


# ---------------------------------------------------------------------------
# FederatedExecutor
# ---------------------------------------------------------------------------


class FederatedExecutor:
    """Plans federated execution of graphs across multiple machines.

    Takes a graph and a list of machine profiles, then assigns each node
    to the best-suited machine based on domain capabilities. This is the
    Phase 5 MVP planner -- it returns an ExecutionPlan without performing
    actual distributed execution.

    Example::

        profiles = [
            MachineProfile(id="tower", name="Tower", capabilities=["gpu-inference", "docker-runtime"]),
            MachineProfile(id="photon", name="Photon", capabilities=["cpu-compute", "llm-api"]),
            MachineProfile(id="mac", name="Mac", capabilities=["kicad-host", "hardware-connected"]),
        ]
        executor = FederatedExecutor()
        plan = executor.plan(graph, profiles)
        print(plan.machine_summary)

    Planning rules:
        - AI nodes -> machines with gpu-inference (preferred) or llm-api or cpu-inference
        - Electronics nodes -> machines with kicad-host or spice-runtime or cpu-compute
        - Hardware nodes -> machines with hardware-connected or gpio-access
        - CAD nodes -> machines with docker-runtime or freecad-host or cpu-compute
        - Adapter nodes -> any machine with cpu-compute
        - When multiple machines qualify, prefer higher priority, then more VRAM
        - Unassigned nodes are reported in the plan
    """

    def __init__(
        self,
        domain_capability_map: dict[str, list[str]] | None = None,
    ) -> None:
        """Initialize the federated executor.

        Args:
            domain_capability_map: Optional override for the default
                domain-to-capability mapping. If None, uses DOMAIN_CAPABILITY_MAP.
        """
        self.domain_capability_map = domain_capability_map or DOMAIN_CAPABILITY_MAP

    def plan(
        self,
        graph: Graph,
        machine_profiles: list[MachineProfile | dict[str, Any]],
    ) -> ExecutionPlan:
        """Assign graph nodes to machines based on capabilities.

        Args:
            graph: The graph to plan execution for.
            machine_profiles: List of MachineProfile instances or dicts
                (from MACHINE_PROFILES.json).

        Returns:
            ExecutionPlan with node-to-machine assignments and resource estimates.
        """
        # Normalize profiles
        profiles: list[MachineProfile] = []
        for p in machine_profiles:
            if isinstance(p, dict):
                profiles.append(MachineProfile.from_dict(p))
            else:
                profiles.append(p)

        if not profiles:
            logger.warning("No machine profiles provided -- all nodes will be unassigned")

        assignments: list[NodeAssignment] = []
        unassigned: list[str] = []
        warnings: list[str] = []
        total_memory = 0

        for node in graph.nodes:
            node_id = getattr(node, "id", "")
            node_type = getattr(node, "type", None) or getattr(node, "node_type", "")
            domain = self._extract_domain(node_type)

            # Find required capabilities for this domain
            required_caps = self.domain_capability_map.get(domain, [])

            if not required_caps:
                # Unknown domain -- try to assign to any machine with cpu-compute
                required_caps = ["cpu-compute"]
                warnings.append(
                    f"Node '{node_id}' has unknown domain '{domain}' -- "
                    f"falling back to cpu-compute requirement"
                )

            # Find eligible machines
            eligible = self._find_eligible_machines(profiles, required_caps)

            if not eligible:
                unassigned.append(node_id)
                warnings.append(
                    f"No machine can execute node '{node_id}' "
                    f"(domain={domain}, requires one of: {required_caps})"
                )
                continue

            # Select best machine (highest priority, then most VRAM)
            best = self._select_best_machine(eligible, domain)

            # Estimate memory for this node
            mem_estimate = self._estimate_node_memory(domain)
            total_memory += mem_estimate

            assignments.append(
                NodeAssignment(
                    node_id=node_id,
                    node_type=node_type,
                    machine_id=best.id,
                    machine_name=best.name,
                    reason=f"domain={domain}, matched capability in {best.capabilities}",
                    estimated_memory_mb=mem_estimate,
                    requires_network=False,
                )
            )

        # Count cross-machine edges
        cross_machine_edges = self._count_cross_machine_edges(graph, assignments)

        # Mark assignments that require network transfer
        assignment_map = {a.node_id: a for a in assignments}
        for edge in graph.edges:
            src_id = getattr(edge, "from_node", None) or getattr(edge, "source_node", "")
            tgt_id = getattr(edge, "to_node", None) or getattr(edge, "target_node", "")
            src_assign = assignment_map.get(src_id)
            tgt_assign = assignment_map.get(tgt_id)
            if src_assign and tgt_assign and src_assign.machine_id != tgt_assign.machine_id:
                tgt_assign.requires_network = True

        # Build resource estimate
        machines_used = len({a.machine_id for a in assignments})
        resource_estimate = ResourceEstimate(
            total_nodes=len(graph.nodes),
            machines_used=machines_used,
            estimated_memory_mb=total_memory,
            estimated_network_transfers=cross_machine_edges,
            cross_machine_edges=cross_machine_edges,
        )

        plan = ExecutionPlan(
            graph_id=graph.id,
            assignments=assignments,
            resource_estimate=resource_estimate,
            unassigned_nodes=unassigned,
            warnings=warnings,
        )

        logger.info(
            "Federation plan for graph '%s': %d nodes assigned to %d machine(s), "
            "%d unassigned, %d cross-machine edges",
            graph.id,
            len(assignments),
            machines_used,
            len(unassigned),
            cross_machine_edges,
        )

        return plan

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_domain(node_type: str) -> str:
        """Extract the domain prefix from a node type string."""
        if "." in node_type:
            return node_type.split(".")[0]
        return node_type

    @staticmethod
    def _find_eligible_machines(
        profiles: list[MachineProfile],
        required_caps: list[str],
    ) -> list[MachineProfile]:
        """Find machines that have at least one of the required capabilities."""
        eligible = []
        for p in profiles:
            if any(p.has_capability(cap) for cap in required_caps):
                eligible.append(p)
        return eligible

    @staticmethod
    def _select_best_machine(
        eligible: list[MachineProfile],
        domain: str,
    ) -> MachineProfile:
        """Select the best machine from eligible candidates.

        Prefers higher priority, then more GPU VRAM (for AI domain),
        then more RAM.
        """
        if domain == "ai":
            # For AI nodes, prefer machines with more VRAM
            return max(eligible, key=lambda p: (p.priority, p.gpu_vram_gb, p.ram_gb))
        else:
            # For other domains, prefer higher priority, then more RAM
            return max(eligible, key=lambda p: (p.priority, p.ram_gb))

    @staticmethod
    def _estimate_node_memory(domain: str) -> int:
        """Estimate memory usage in MB for a node in the given domain."""
        estimates = {
            "ai": 512,
            "electronics": 256,
            "cad": 1024,
            "hardware": 64,
            "midi": 32,
            "adapter": 16,
        }
        return estimates.get(domain, 128)

    @staticmethod
    def _count_cross_machine_edges(
        graph: Graph,
        assignments: list[NodeAssignment],
    ) -> int:
        """Count edges where source and target are on different machines."""
        assignment_map = {a.node_id: a.machine_id for a in assignments}
        count = 0
        for edge in graph.edges:
            src_id = getattr(edge, "from_node", None) or getattr(edge, "source_node", "")
            tgt_id = getattr(edge, "to_node", None) or getattr(edge, "target_node", "")
            src_machine = assignment_map.get(src_id)
            tgt_machine = assignment_map.get(tgt_id)
            if src_machine and tgt_machine and src_machine != tgt_machine:
                count += 1
        return count
