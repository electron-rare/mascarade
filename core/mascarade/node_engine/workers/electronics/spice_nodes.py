"""SPICE simulation nodes for electronics domain."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from mascarade.node_engine.types import PortDirection, PortType

logger = logging.getLogger("mascarade.node_engine.workers.electronics.spice_nodes")


@dataclass
class NodeConfig:
    """Base configuration for node execution parameters."""

    pass


@dataclass
class NetlistGeneratorConfig(NodeConfig):
    """Configuration for netlist generator node."""

    include_control_section: bool = True
    default_analyses: list[str] = field(default_factory=lambda: ["op"])


class BaseNode:
    """Base class for all executable nodes.

    Nodes are the fundamental execution units in the Universal Node Engine.
    Each node has input/output ports and an execute method.
    """

    node_type: str = ""
    description: str = ""

    def __init__(self, config: NodeConfig | None = None) -> None:
        """Initialize the node with optional configuration.

        Args:
            config: Node-specific configuration parameters
        """
        self.config = config or self._default_config()
        self._input_ports: list[PortType] = self._define_input_ports()
        self._output_ports: list[PortType] = self._define_output_ports()

    def _default_config(self) -> NodeConfig:
        """Return default configuration for this node type.

        Should be overridden by subclasses.
        """
        return NodeConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for this node.

        Should be overridden by subclasses.
        """
        return []

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for this node.

        Should be overridden by subclasses.
        """
        return []

    @property
    def input_ports(self) -> list[PortType]:
        """Get list of input ports."""
        return self._input_ports

    @property
    def output_ports(self) -> list[PortType]:
        """Get list of output ports."""
        return self._output_ports

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute the node with given inputs.

        Args:
            inputs: Dictionary mapping input port names to values

        Returns:
            Dictionary mapping output port names to values

        Raises:
            ValueError: If required inputs are missing or invalid
        """
        raise NotImplementedError("Subclasses must implement execute()")


class NetlistGeneratorNode(BaseNode):
    """Generates a SPICE netlist from a high-level circuit description.

    Mirrors the SpiceAgent.generate_netlist() method, using LLM-assisted
    generation with validation.

    Input Ports:
        circuit_description (string): Natural language or structured circuit description
        device_models (optional<string>): Custom .model / .subckt definitions to include
        target_simulator (optional<string>): Simulator target: "ngspice" (default), "ltspice"

    Output Ports:
        netlist (electronics.Netlist): Generated SPICE netlist

    Configuration:
        include_control_section (boolean): Whether to include .control / .endc block (default: true)
        default_analyses (array<string>): Default analysis types if none specified (default: ["op"])
    """

    node_type = "electronics.spice.netlist_generator"
    description = "Generates a SPICE netlist from a high-level circuit description"

    def _default_config(self) -> NetlistGeneratorConfig:
        """Return default configuration for netlist generator."""
        return NetlistGeneratorConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for netlist generator."""
        return [
            PortType(
                name="circuit_description",
                direction=PortDirection.INPUT,
                port_type="string",
                description="Natural language or structured circuit description",
                optional=False,
            ),
            PortType(
                name="device_models",
                direction=PortDirection.INPUT,
                port_type="string",
                description="Custom .model / .subckt definitions to include",
                optional=True,
                default_value=None,
            ),
            PortType(
                name="target_simulator",
                direction=PortDirection.INPUT,
                port_type="string",
                description='Simulator target: "ngspice" (default), "ltspice"',
                optional=True,
                default_value="ngspice",
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for netlist generator."""
        return [
            PortType(
                name="netlist",
                direction=PortDirection.OUTPUT,
                port_type="electronics.Netlist",
                description="Generated SPICE netlist",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute netlist generation.

        Args:
            inputs: Dictionary with circuit_description (required), device_models (optional),
                   target_simulator (optional)

        Returns:
            Dictionary with netlist (electronics.Netlist)

        Raises:
            ValueError: If circuit_description is missing or empty
        """
        # Validate required inputs
        circuit_description = inputs.get("circuit_description")
        if not circuit_description:
            raise ValueError("circuit_description is required and cannot be empty")

        # Get optional inputs
        device_models = inputs.get("device_models")
        target_simulator = inputs.get("target_simulator", "ngspice")

        # Get configuration
        config = self.config
        if not isinstance(config, NetlistGeneratorConfig):
            config = NetlistGeneratorConfig()

        logger.info(
            f"Generating netlist for target_simulator={target_simulator}, "
            f"include_control_section={config.include_control_section}"
        )

        # Build netlist content
        # This is a simplified implementation - in production, this would
        # integrate with SpiceAgent or an LLM for intelligent netlist generation
        netlist_lines = [
            "* SPICE Netlist - Generated by Universal Node Engine",
            f"* Target simulator: {target_simulator}",
            f"* Circuit description: {circuit_description[:80]}...",
            "",
        ]

        # Add custom device models if provided
        if device_models:
            netlist_lines.append("* Custom device models")
            netlist_lines.append(device_models)
            netlist_lines.append("")

        # Add placeholder circuit (in production, this would be LLM-generated)
        netlist_lines.extend([
            "* Circuit netlist",
            "* TODO: Integrate with SpiceAgent for intelligent generation",
            "",
        ])

        # Add analysis directives
        if config.include_control_section:
            netlist_lines.append(".control")
            for analysis in config.default_analyses:
                netlist_lines.append(f"  {analysis}")
            netlist_lines.append(".endc")
            netlist_lines.append("")

        # End netlist
        netlist_lines.append(".end")

        netlist_content = "\n".join(netlist_lines)

        # Extract components and analyses for metadata
        components = []  # Would be extracted from generated netlist
        analyses = config.default_analyses

        # Return netlist in electronics.Netlist format
        netlist = {
            "format": "spice",
            "content": netlist_content,
            "components": components,
            "analyses": analyses,
        }

        return {"netlist": netlist}


__all__ = ["NetlistGeneratorNode", "BaseNode", "NodeConfig", "NetlistGeneratorConfig"]
