"""SPICE simulation nodes for electronics domain."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
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


@dataclass
class SimulateConfig(NodeConfig):
    """Configuration for SPICE simulation node."""

    ngspice_path: str = "ngspice"
    timeout_seconds: int = 300
    batch_mode: bool = True
    capture_raw_output: bool = False


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


class SimulateNode(BaseNode):
    """Executes SPICE simulation using ngspice in batch mode.

    Mirrors the SpiceAgent simulation capabilities, running ngspice on a provided
    netlist and capturing results.

    Input Ports:
        netlist (electronics.Netlist): SPICE netlist to simulate
        netlist_content (optional<string>): Raw netlist content (alternative to netlist object)
        extra_directives (optional<string>): Additional SPICE directives to append

    Output Ports:
        results (electronics.SimulationResults): Parsed simulation results
        stdout (string): Standard output from ngspice
        stderr (string): Standard error from ngspice
        success (boolean): Whether simulation completed successfully
        exit_code (integer): ngspice exit code

    Configuration:
        ngspice_path (string): Path to ngspice executable (default: "ngspice")
        timeout_seconds (integer): Maximum simulation time in seconds (default: 300)
        batch_mode (boolean): Run in batch mode (default: true)
        capture_raw_output (boolean): Capture raw binary output (default: false)
    """

    node_type = "electronics.spice.simulate"
    description = "Executes SPICE simulation using ngspice in batch mode"

    def _default_config(self) -> SimulateConfig:
        """Return default configuration for simulator."""
        return SimulateConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for simulator."""
        return [
            PortType(
                name="netlist",
                direction=PortDirection.INPUT,
                port_type="electronics.Netlist",
                description="SPICE netlist to simulate",
                optional=True,
                default_value=None,
            ),
            PortType(
                name="netlist_content",
                direction=PortDirection.INPUT,
                port_type="string",
                description="Raw netlist content (alternative to netlist object)",
                optional=True,
                default_value=None,
            ),
            PortType(
                name="extra_directives",
                direction=PortDirection.INPUT,
                port_type="string",
                description="Additional SPICE directives to append",
                optional=True,
                default_value=None,
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for simulator."""
        return [
            PortType(
                name="results",
                direction=PortDirection.OUTPUT,
                port_type="electronics.SimulationResults",
                description="Parsed simulation results",
            ),
            PortType(
                name="stdout",
                direction=PortDirection.OUTPUT,
                port_type="string",
                description="Standard output from ngspice",
            ),
            PortType(
                name="stderr",
                direction=PortDirection.OUTPUT,
                port_type="string",
                description="Standard error from ngspice",
            ),
            PortType(
                name="success",
                direction=PortDirection.OUTPUT,
                port_type="boolean",
                description="Whether simulation completed successfully",
            ),
            PortType(
                name="exit_code",
                direction=PortDirection.OUTPUT,
                port_type="integer",
                description="ngspice exit code",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute SPICE simulation.

        Args:
            inputs: Dictionary with netlist or netlist_content (required),
                   extra_directives (optional)

        Returns:
            Dictionary with results, stdout, stderr, success, exit_code

        Raises:
            ValueError: If neither netlist nor netlist_content is provided
        """
        # Extract netlist content from input
        netlist_obj = inputs.get("netlist")
        netlist_content = inputs.get("netlist_content")
        extra_directives = inputs.get("extra_directives")

        # Determine netlist content
        if netlist_obj and isinstance(netlist_obj, dict):
            netlist_text = netlist_obj.get("content", "")
        elif netlist_content:
            netlist_text = netlist_content
        else:
            raise ValueError(
                "Either 'netlist' object or 'netlist_content' string must be provided"
            )

        if not netlist_text.strip():
            raise ValueError("Netlist content cannot be empty")

        # Append extra directives if provided
        if extra_directives:
            # Insert before .end if present, otherwise append
            if ".end" in netlist_text.lower():
                lines = netlist_text.split("\n")
                end_index = next(
                    (i for i, line in enumerate(lines) if line.strip().lower() == ".end"),
                    len(lines),
                )
                lines.insert(end_index, extra_directives)
                netlist_text = "\n".join(lines)
            else:
                netlist_text += f"\n{extra_directives}\n"

        # Get configuration
        config = self.config
        if not isinstance(config, SimulateConfig):
            config = SimulateConfig()

        logger.info(
            f"Starting ngspice simulation (timeout={config.timeout_seconds}s, "
            f"batch_mode={config.batch_mode})"
        )

        # Create temporary file for netlist
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".cir", delete=False, encoding="utf-8"
        ) as tmp_file:
            tmp_file.write(netlist_text)
            tmp_path = Path(tmp_file.name)

        try:
            # Build ngspice command
            cmd = [config.ngspice_path]
            if config.batch_mode:
                cmd.append("-b")  # Batch mode
            cmd.append(str(tmp_path))  # Netlist file

            logger.debug(f"Running command: {' '.join(cmd)}")

            # Execute ngspice
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=config.timeout_seconds
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise TimeoutError(
                    f"Simulation exceeded timeout of {config.timeout_seconds} seconds"
                )

            # Decode output
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0

            # Determine success
            success = exit_code == 0 and "error" not in stderr.lower()

            logger.info(
                f"Simulation completed: exit_code={exit_code}, success={success}"
            )

            # Parse results (simplified - in production, parse actual output)
            results = {
                "format": "ngspice",
                "raw_output": stdout if config.capture_raw_output else "",
                "measurements": self._extract_measurements(stdout),
                "convergence_info": self._extract_convergence_info(stdout, stderr),
            }

            return {
                "results": results,
                "stdout": stdout,
                "stderr": stderr,
                "success": success,
                "exit_code": exit_code,
            }

        finally:
            # Clean up temporary file
            try:
                tmp_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temporary netlist file: {e}")

    def _extract_measurements(self, stdout: str) -> dict[str, Any]:
        """Extract measurement values from ngspice output.

        Args:
            stdout: ngspice standard output

        Returns:
            Dictionary of measurement name to value
        """
        measurements = {}

        # Simple parser for ngspice output format
        # Example: "v(out) = 5.0000e+00"
        for line in stdout.split("\n"):
            line = line.strip()
            if "=" in line and not line.startswith("*"):
                try:
                    name, value = line.split("=", 1)
                    name = name.strip()
                    value = value.strip()
                    # Try to convert to float
                    try:
                        measurements[name] = float(value)
                    except ValueError:
                        measurements[name] = value
                except ValueError:
                    continue

        return measurements

    def _extract_convergence_info(self, stdout: str, stderr: str) -> dict[str, Any]:
        """Extract convergence information from simulation output.

        Args:
            stdout: ngspice standard output
            stderr: ngspice standard error

        Returns:
            Dictionary with convergence status and issues
        """
        combined = stdout + "\n" + stderr
        combined_lower = combined.lower()

        convergence_info = {
            "converged": True,
            "warnings": [],
            "errors": [],
        }

        # Check for convergence failures
        if "convergence" in combined_lower and "failed" in combined_lower:
            convergence_info["converged"] = False

        # Extract warnings
        for line in combined.split("\n"):
            line_lower = line.lower()
            if "warning" in line_lower:
                convergence_info["warnings"].append(line.strip())
            if "error" in line_lower and not line.startswith("*"):
                convergence_info["errors"].append(line.strip())

        return convergence_info


__all__ = [
    "NetlistGeneratorNode",
    "SimulateNode",
    "BaseNode",
    "NodeConfig",
    "NetlistGeneratorConfig",
    "SimulateConfig",
]
