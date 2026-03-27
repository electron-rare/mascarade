#!/usr/bin/env python3
"""Federated Execution Plan Example.

Demonstrates the FederatedExecutor planner that assigns graph nodes to
machines based on domain capabilities. No actual distributed execution
happens -- the output is a plan describing which node runs where.

This is a Phase 5 MVP template for federation planning.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from mascarade.node_engine.cross_domain.federation import (
    ExecutionPlan,
    FederatedExecutor,
    MachineProfile,
)
from mascarade.node_engine.graph import Edge, Graph, Node


def build_multi_domain_graph() -> Graph:
    """Build a sample graph spanning AI, CAD, Electronics, and Hardware domains."""
    nodes = [
        Node(id="llm-design", type="ai.llm-inference"),
        Node(id="classify-intent", type="ai.classify"),
        Node(id="summarize-spec", type="ai.summarize"),
        Node(id="trace-calc", type="cad.trace-width"),
        Node(id="bom-gen", type="cad.bom-generate"),
        Node(id="mesh-import", type="cad.mesh.import"),
        Node(id="spice-sim", type="electronics.spice.analyze"),
        Node(id="drc-check", type="electronics.pcb.drc"),
        Node(id="fw-compile", type="electronics.firmware.compile"),
        Node(id="deploy-ota", type="hardware.esp32.ota"),
        Node(id="midi-seq", type="hardware.midi.note-sequence"),
    ]
    edges = [
        Edge(from_node="llm-design", from_port="response", to_node="classify-intent", to_port="text"),
        Edge(from_node="classify-intent", from_port="category", to_node="trace-calc", to_port="spec"),
        Edge(from_node="llm-design", from_port="response", to_node="summarize-spec", to_port="text"),
        Edge(from_node="trace-calc", from_port="width", to_node="bom-gen", to_port="trace_data"),
        Edge(from_node="bom-gen", from_port="bom", to_node="spice-sim", to_port="netlist"),
        Edge(from_node="spice-sim", from_port="result", to_node="drc-check", to_port="analysis"),
        Edge(from_node="drc-check", from_port="passed", to_node="fw-compile", to_port="trigger"),
        Edge(from_node="fw-compile", from_port="binary", to_node="deploy-ota", to_port="firmware"),
    ]
    return Graph(id="federated-demo", nodes=nodes, edges=edges)


def build_machine_profiles() -> list[MachineProfile]:
    """Build sample machine profiles matching Mascarade infrastructure."""
    return [
        MachineProfile(
            id="tower",
            name="Tower",
            capabilities=["gpu-inference", "docker-runtime", "cpu-compute", "llm-api"],
            gpu_vram_gb=5.0,
            ram_gb=32.0,
            max_concurrent=12,
            priority=10,
        ),
        MachineProfile(
            id="kxkm-ai",
            name="KXKM-AI",
            capabilities=["gpu-inference", "cpu-compute", "cpu-inference"],
            gpu_vram_gb=24.0,
            ram_gb=64.0,
            max_concurrent=8,
            priority=5,
        ),
        MachineProfile(
            id="mac",
            name="Mac Dev",
            capabilities=[
                "kicad-host",
                "spice-runtime",
                "cpu-compute",
                "hardware-connected",
                "midi-interface",
                "serial-access",
            ],
            gpu_vram_gb=0.0,
            ram_gb=16.0,
            max_concurrent=8,
            priority=3,
        ),
        MachineProfile(
            id="photon",
            name="Photon VM",
            capabilities=["cpu-compute", "llm-api", "docker-runtime"],
            gpu_vram_gb=0.0,
            ram_gb=6.8,
            max_concurrent=4,
            priority=1,
        ),
    ]


def main():
    print("=" * 70)
    print("Federated Execution Plan — Phase 5 MVP")
    print("=" * 70)

    graph = build_multi_domain_graph()
    profiles = build_machine_profiles()
    executor = FederatedExecutor()

    print(f"\nGraph: {graph.id} ({graph.node_count} nodes, {graph.edge_count} edges)")
    print(f"Machines: {', '.join(p.name for p in profiles)}")

    # Generate the plan
    plan = executor.plan(graph, profiles)

    # Display assignments
    print(f"\n--- Node Assignments ---")
    for a in plan.assignments:
        network_tag = " [NETWORK]" if a.requires_network else ""
        print(f"  {a.node_id:25s} -> {a.machine_name:12s} ({a.node_type}){network_tag}")

    # Display machine summary
    print(f"\n--- Machine Summary ---")
    for machine_id, node_ids in plan.machine_summary.items():
        profile = next(p for p in profiles if p.id == machine_id)
        print(f"  {profile.name}: {len(node_ids)} nodes — {', '.join(node_ids)}")

    # Display resource estimate
    print(f"\n--- Resource Estimate ---")
    re = plan.resource_estimate
    print(f"  Total nodes: {re.total_nodes}")
    print(f"  Machines used: {re.machines_used}")
    print(f"  Estimated memory: {re.estimated_memory_mb} MB")
    print(f"  Cross-machine edges: {re.cross_machine_edges}")
    print(f"  Network transfers needed: {re.estimated_network_transfers}")

    # Warnings
    if plan.warnings:
        print(f"\n--- Warnings ---")
        for w in plan.warnings:
            print(f"  ! {w}")

    if plan.unassigned_nodes:
        print(f"\n--- Unassigned Nodes ---")
        for n in plan.unassigned_nodes:
            print(f"  ? {n}")

    # Full plan as JSON
    print(f"\n--- Full Plan (JSON) ---")
    print(json.dumps(plan.to_dict(), indent=2))

    print(f"\nPlan complete: {'READY' if plan.is_complete else 'INCOMPLETE'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
