"""Unified cross-domain orchestration pipeline.

Automatically detects domain boundaries in a graph, inserts adapter nodes
where needed, executes the augmented graph through the runtime, and returns
results annotated with conversion metadata.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from mascarade.node_engine.cross_domain.register import AdapterRegistry
from mascarade.node_engine.graph import Edge, Graph, Node
from mascarade.node_engine.runtime import (
    ExecutionMode,
    ExecutionStatus,
    GraphExecutionContext,
    GraphRuntime,
)

logger = logging.getLogger("mascarade.node_engine.cross_domain.orchestrator")


@dataclass
class AdapterInsertionRecord:
    """Metadata about a single adapter node that was automatically inserted."""

    adapter_node_id: str
    mapping_id: str
    source_node_id: str
    source_port: str
    target_node_id: str
    target_port: str
    source_domain: str
    target_domain: str
    lossy: bool = False


@dataclass
class OrchestrationResult:
    """Result of a cross-domain orchestration run.

    Wraps the underlying GraphExecutionContext with additional metadata
    about which adapter nodes were inserted and how data was converted.
    """

    execution_context: GraphExecutionContext
    adapter_insertions: list[AdapterInsertionRecord] = field(default_factory=list)
    original_node_count: int = 0
    augmented_node_count: int = 0

    @property
    def status(self) -> ExecutionStatus:
        return self.execution_context.status

    @property
    def node_results(self) -> dict[str, Any]:
        return self.execution_context.node_results

    @property
    def conversion_metadata(self) -> list[dict[str, Any]]:
        """Return conversion metadata for all adapter insertions."""
        meta = []
        for record in self.adapter_insertions:
            entry: dict[str, Any] = {
                "adapter_node_id": record.adapter_node_id,
                "mapping_id": record.mapping_id,
                "source_node": record.source_node_id,
                "target_node": record.target_node_id,
                "source_domain": record.source_domain,
                "target_domain": record.target_domain,
                "lossy": record.lossy,
            }
            # Include execution result if available
            result = self.execution_context.node_results.get(record.adapter_node_id)
            if result is not None:
                entry["execution_status"] = result.status
                entry["execution_time_ms"] = result.execution_time_ms
            meta.append(entry)
        return meta


def _node_domain(node: Any) -> str:
    """Extract the domain from a node, handling both Pydantic and dataclass models."""
    # Pydantic Node has a .domain property
    if hasattr(node, "domain"):
        d = node.domain
        if callable(d):
            return d()
        return d
    # Dataclass GraphNode may have node_type
    node_type = getattr(node, "type", None) or getattr(node, "node_type", "")
    if "." in node_type:
        return node_type.split(".")[0]
    return ""


class CrossDomainOrchestrator:
    """Orchestrates execution of graphs that span multiple domains.

    Analyzes a graph for domain transitions (edges where the source node
    belongs to a different domain than the target node), looks up appropriate
    adapters in the AdapterRegistry, inserts adapter nodes into the graph,
    and executes the augmented graph through the GraphRuntime.

    Example::

        orchestrator = CrossDomainOrchestrator(runtime, adapter_registry)
        result = await orchestrator.execute(graph, inputs={"prompt": "..."})
        print(result.conversion_metadata)
    """

    def __init__(
        self,
        runtime: GraphRuntime,
        adapter_registry: AdapterRegistry,
    ) -> None:
        self.runtime = runtime
        self.adapter_registry = adapter_registry

    def analyze_domain_transitions(self, graph: Graph) -> list[dict[str, Any]]:
        """Find all edges in the graph that cross domain boundaries.

        Args:
            graph: Graph to analyze

        Returns:
            List of dicts, each describing a domain transition with keys:
            - edge: the original edge object
            - source_node: source node object
            - target_node: target node object
            - source_domain: domain of the source node
            - target_domain: domain of the target node
        """
        transitions: list[dict[str, Any]] = []

        for edge in graph.edges:
            # Handle both Edge (Pydantic) and GraphEdge (dataclass)
            src_id = getattr(edge, "from_node", None) or getattr(edge, "source_node", "")
            tgt_id = getattr(edge, "to_node", None) or getattr(edge, "target_node", "")

            src_node = graph.get_node(src_id)
            tgt_node = graph.get_node(tgt_id)

            if src_node is None or tgt_node is None:
                continue

            src_domain = _node_domain(src_node)
            tgt_domain = _node_domain(tgt_node)

            if src_domain and tgt_domain and src_domain != tgt_domain:
                transitions.append(
                    {
                        "edge": edge,
                        "source_node": src_node,
                        "target_node": tgt_node,
                        "source_domain": src_domain,
                        "target_domain": tgt_domain,
                    }
                )

        logger.info(
            "Found %d domain transition(s) in graph with %d nodes",
            len(transitions),
            graph.node_count,
        )
        return transitions

    def _find_adapter_mapping(
        self,
        source_domain: str,
        target_domain: str,
    ) -> str | None:
        """Find a suitable adapter mapping ID for a domain transition.

        Searches the adapter registry for any mapping that converts from
        source_domain to target_domain.

        Args:
            source_domain: Source domain identifier
            target_domain: Target domain identifier

        Returns:
            Mapping ID string if found, None otherwise
        """
        for mapping_id in self.adapter_registry.list_mappings():
            # Mapping IDs have the form "domain.Type->domain.Type"
            if "->" not in mapping_id:
                continue
            src_part, tgt_part = mapping_id.split("->", 1)
            src_dom = src_part.split(".")[0] if "." in src_part else ""
            tgt_dom = tgt_part.split(".")[0] if "." in tgt_part else ""
            if src_dom == source_domain and tgt_dom == target_domain:
                return mapping_id
        return None

    def insert_adapter_nodes(
        self,
        graph: Graph,
        transitions: list[dict[str, Any]],
    ) -> tuple[Graph, list[AdapterInsertionRecord]]:
        """Create a new graph with adapter nodes inserted at domain boundaries.

        For each domain transition, inserts an adapter node between the source
        and target nodes, replacing the original edge with two edges:
        source -> adapter -> target.

        Args:
            graph: Original graph
            transitions: Domain transitions as returned by analyze_domain_transitions()

        Returns:
            Tuple of (augmented_graph, insertion_records)

        Raises:
            KeyError: If no adapter is registered for a required domain transition
        """
        if not transitions:
            return graph, []

        # Collect new nodes and edges, starting from the originals
        new_nodes = list(graph.nodes)
        # Build a set of edges to remove (the cross-domain ones)
        edges_to_remove: set[int] = set()
        new_edges: list[Any] = []
        records: list[AdapterInsertionRecord] = []

        for transition in transitions:
            edge = transition["edge"]
            src_domain = transition["source_domain"]
            tgt_domain = transition["target_domain"]

            # Find adapter mapping
            mapping_id = self._find_adapter_mapping(src_domain, tgt_domain)
            if mapping_id is None:
                raise KeyError(
                    f"No adapter registered for domain transition "
                    f"{src_domain} -> {tgt_domain}. "
                    f"Available mappings: {self.adapter_registry.list_mappings()}"
                )

            adapter, mapping = self.adapter_registry.lookup(mapping_id)

            # Generate unique ID for the adapter node
            adapter_node_id = f"_adapter_{src_domain}_to_{tgt_domain}_{uuid.uuid4().hex[:8]}"

            # Extract port names from the original edge
            src_port = getattr(edge, "from_port", None) or getattr(edge, "source_port", "out")
            tgt_port = getattr(edge, "to_port", None) or getattr(edge, "target_port", "in")
            src_id = getattr(edge, "from_node", None) or getattr(edge, "source_node", "")
            tgt_id = getattr(edge, "to_node", None) or getattr(edge, "target_node", "")

            # Create the adapter node as a Pydantic Node (matching the graph's node type)
            adapter_node = Node(
                id=adapter_node_id,
                type=f"adapter.{src_domain}-to-{tgt_domain}",
                inputs={},
                config={
                    "mapping": mapping_id,
                    "adapter_config": {},
                },
            )
            new_nodes.append(adapter_node)

            # Mark original edge for removal
            for i, e in enumerate(graph.edges):
                if e is edge:
                    edges_to_remove.add(i)
                    break

            # Create two new edges: source -> adapter and adapter -> target
            edge_src_to_adapter = Edge(
                from_node=src_id,
                from_port=src_port,
                to_node=adapter_node_id,
                to_port="source",
            )
            edge_adapter_to_tgt = Edge(
                from_node=adapter_node_id,
                from_port="result",
                to_node=tgt_id,
                to_port=tgt_port,
            )
            new_edges.append(edge_src_to_adapter)
            new_edges.append(edge_adapter_to_tgt)

            records.append(
                AdapterInsertionRecord(
                    adapter_node_id=adapter_node_id,
                    mapping_id=mapping_id,
                    source_node_id=src_id,
                    source_port=src_port,
                    target_node_id=tgt_id,
                    target_port=tgt_port,
                    source_domain=src_domain,
                    target_domain=tgt_domain,
                    lossy=mapping.lossy,
                )
            )

            logger.info(
                "Inserted adapter node '%s' for %s -> %s (mapping: %s, lossy: %s)",
                adapter_node_id,
                src_id,
                tgt_id,
                mapping_id,
                mapping.lossy,
            )

        # Build final edge list: keep non-removed original edges + new edges
        final_edges = [
            e for i, e in enumerate(graph.edges) if i not in edges_to_remove
        ] + new_edges

        # Create the augmented graph
        augmented = Graph(
            id=graph.id,
            name=graph.name,
            version=graph.version,
            status=graph.status,
            nodes=new_nodes,
            edges=final_edges,
            metadata=graph.metadata,
        )

        return augmented, records

    async def execute(
        self,
        graph: Graph,
        inputs: dict[str, Any] | None = None,
        mode: str | ExecutionMode = "eager",
        *,
        metadata: dict[str, Any] | None = None,
        target_nodes: set[str] | None = None,
    ) -> OrchestrationResult:
        """Execute a multi-domain graph with automatic adapter insertion.

        1. Analyzes the graph for domain transitions
        2. Inserts adapter nodes at domain boundaries
        3. Executes the augmented graph via the runtime
        4. Returns results with adapter conversion metadata

        Args:
            graph: Graph with nodes from potentially multiple domains
            inputs: Optional initial inputs for the graph
            mode: Execution mode - "eager", "lazy", or "stepped"
            metadata: Optional metadata for the execution context
            target_nodes: Optional target nodes for lazy execution

        Returns:
            OrchestrationResult with execution context and conversion metadata

        Raises:
            KeyError: If no adapter is found for a required domain transition
            ValueError: If graph validation fails
            RuntimeError: If execution fails
        """
        original_count = graph.node_count

        # Step 1: Analyze for domain transitions
        transitions = self.analyze_domain_transitions(graph)

        # Step 2: Insert adapter nodes if needed
        if transitions:
            augmented_graph, insertion_records = self.insert_adapter_nodes(
                graph, transitions
            )
            logger.info(
                "Augmented graph: %d -> %d nodes (%d adapter(s) inserted)",
                original_count,
                augmented_graph.node_count,
                len(insertion_records),
            )
        else:
            augmented_graph = graph
            insertion_records = []
            logger.info("No domain transitions found — executing graph as-is")

        # Step 3: Resolve execution mode
        if isinstance(mode, str):
            exec_mode = ExecutionMode(mode)
        else:
            exec_mode = mode

        # Step 4: Execute via runtime
        execution_context = await self.runtime.execute(
            augmented_graph,
            initial_inputs=inputs,
            metadata=metadata,
            mode=exec_mode,
            target_nodes=target_nodes,
        )

        # Step 5: Build and return result with conversion metadata
        result = OrchestrationResult(
            execution_context=execution_context,
            adapter_insertions=insertion_records,
            original_node_count=original_count,
            augmented_node_count=augmented_graph.node_count,
        )

        logger.info(
            "Cross-domain orchestration %s: %d adapters, status=%s",
            "completed" if result.status == ExecutionStatus.COMPLETED else "finished",
            len(insertion_records),
            result.status,
        )

        return result
