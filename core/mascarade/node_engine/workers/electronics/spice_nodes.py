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


@dataclass
class AnalyzeConfig(NodeConfig):
    """Configuration for circuit analysis node."""

    include_measurements: bool = True
    suggest_improvements: bool = True


@dataclass
class DebugConvergenceConfig(NodeConfig):
    """Configuration for convergence debugging node."""

    include_fixes: bool = True
    include_prevention_tips: bool = True


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


class AnalyzeNode(BaseNode):
    """Analyzes a SPICE circuit and provides insights.

    Mirrors the SpiceAgent.analyze_circuit() method, providing detailed analysis
    of circuit characteristics, behavior, and performance.

    Input Ports:
        netlist (electronics.Netlist): SPICE netlist to analyze
        netlist_content (optional<string>): Raw netlist content (alternative to netlist object)
        analysis_type (optional<string>): Type of analysis to perform (default: "general")

    Output Ports:
        analysis_report (string): Detailed analysis report
        characteristics (object): Key circuit characteristics
        recommendations (array<string>): Suggested measurements and improvements

    Configuration:
        include_measurements (boolean): Include suggested measurements (default: true)
        suggest_improvements (boolean): Suggest circuit improvements (default: true)
    """

    node_type = "electronics.spice.analyze"
    description = "Analyzes a SPICE circuit and provides insights"

    def _default_config(self) -> AnalyzeConfig:
        """Return default configuration for analyzer."""
        return AnalyzeConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for analyzer."""
        return [
            PortType(
                name="netlist",
                direction=PortDirection.INPUT,
                port_type="electronics.Netlist",
                description="SPICE netlist to analyze",
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
                name="analysis_type",
                direction=PortDirection.INPUT,
                port_type="string",
                description="Type of analysis to perform (default: general)",
                optional=True,
                default_value="general",
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for analyzer."""
        return [
            PortType(
                name="analysis_report",
                direction=PortDirection.OUTPUT,
                port_type="string",
                description="Detailed analysis report",
            ),
            PortType(
                name="characteristics",
                direction=PortDirection.OUTPUT,
                port_type="object",
                description="Key circuit characteristics",
            ),
            PortType(
                name="recommendations",
                direction=PortDirection.OUTPUT,
                port_type="array",
                description="Suggested measurements and improvements",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute circuit analysis.

        Args:
            inputs: Dictionary with netlist or netlist_content (required),
                   analysis_type (optional)

        Returns:
            Dictionary with analysis_report, characteristics, recommendations

        Raises:
            ValueError: If neither netlist nor netlist_content is provided
        """
        # Extract netlist content from input
        netlist_obj = inputs.get("netlist")
        netlist_content = inputs.get("netlist_content")
        analysis_type = inputs.get("analysis_type", "general")

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

        # Get configuration
        config = self.config
        if not isinstance(config, AnalyzeConfig):
            config = AnalyzeConfig()

        logger.info(
            f"Analyzing circuit (type={analysis_type}, "
            f"include_measurements={config.include_measurements})"
        )

        # Parse netlist for basic analysis
        characteristics = self._extract_characteristics(netlist_text)

        # Generate analysis report
        report_lines = [
            f"SPICE Circuit Analysis Report ({analysis_type})",
            "=" * 60,
            "",
            "1. Key Circuit Characteristics:",
        ]

        for key, value in characteristics.items():
            report_lines.append(f"   - {key}: {value}")

        report_lines.extend([
            "",
            "2. Expected Behavior:",
            "   - Circuit topology analyzed",
            "   - Component values extracted",
            "   - Analysis directives identified",
            "",
            "3. Critical Parameters:",
            "   - See characteristics section above",
        ])

        # Add recommendations
        recommendations = []

        if config.include_measurements:
            report_lines.extend([
                "",
                "4. Suggested Measurements:",
            ])
            measurements = self._suggest_measurements(netlist_text, characteristics)
            for measurement in measurements:
                report_lines.append(f"   - {measurement}")
                recommendations.append(measurement)

        if config.suggest_improvements:
            report_lines.extend([
                "",
                "5. Potential Improvements:",
            ])
            improvements = self._suggest_improvements(netlist_text, characteristics)
            for improvement in improvements:
                report_lines.append(f"   - {improvement}")
                recommendations.append(improvement)

        analysis_report = "\n".join(report_lines)

        logger.info("Circuit analysis completed successfully")

        return {
            "analysis_report": analysis_report,
            "characteristics": characteristics,
            "recommendations": recommendations,
        }

    def _extract_characteristics(self, netlist: str) -> dict[str, Any]:
        """Extract key characteristics from netlist.

        Args:
            netlist: SPICE netlist content

        Returns:
            Dictionary of circuit characteristics
        """
        characteristics = {
            "total_lines": len(netlist.split("\n")),
            "components": [],
            "analysis_types": [],
            "has_control_section": False,
        }

        # Parse netlist lines
        for line in netlist.split("\n"):
            line = line.strip()
            line_lower = line.lower()

            # Skip comments and empty lines
            if not line or line.startswith("*"):
                continue

            # Detect components (first character indicates type)
            if line and line[0].upper() in "RCLDQMVIJKX":
                component_type = {
                    "R": "resistor",
                    "C": "capacitor",
                    "L": "inductor",
                    "D": "diode",
                    "Q": "transistor",
                    "M": "mosfet",
                    "V": "voltage_source",
                    "I": "current_source",
                    "J": "jfet",
                    "K": "coupled_inductor",
                    "X": "subcircuit",
                }.get(line[0].upper(), "unknown")
                characteristics["components"].append(component_type)

            # Detect analysis types
            if line_lower.startswith(".ac"):
                characteristics["analysis_types"].append("AC")
            elif line_lower.startswith(".dc"):
                characteristics["analysis_types"].append("DC")
            elif line_lower.startswith(".tran"):
                characteristics["analysis_types"].append("transient")
            elif line_lower.startswith(".op"):
                characteristics["analysis_types"].append("operating_point")

            # Detect control section
            if line_lower.startswith(".control"):
                characteristics["has_control_section"] = True

        # Count component types
        characteristics["component_count"] = len(characteristics["components"])
        characteristics["unique_component_types"] = len(
            set(characteristics["components"])
        )

        return characteristics

    def _suggest_measurements(
        self, netlist: str, characteristics: dict[str, Any]
    ) -> list[str]:
        """Suggest useful measurements based on circuit.

        Args:
            netlist: SPICE netlist content
            characteristics: Extracted circuit characteristics

        Returns:
            List of suggested measurements
        """
        suggestions = []

        # Suggest based on analysis types
        if "AC" in characteristics.get("analysis_types", []):
            suggestions.append("Measure frequency response (magnitude and phase)")
            suggestions.append("Identify pole and zero frequencies")

        if "transient" in characteristics.get("analysis_types", []):
            suggestions.append("Measure rise/fall times")
            suggestions.append("Check for oscillations or ringing")

        if "operating_point" in characteristics.get("analysis_types", []):
            suggestions.append("Verify DC bias points")
            suggestions.append("Check quiescent currents")

        # Default suggestions
        if not suggestions:
            suggestions.append("Add appropriate analysis directives (.ac, .dc, .tran)")
            suggestions.append("Measure critical node voltages")
            suggestions.append("Verify component power dissipation")

        return suggestions

    def _suggest_improvements(
        self, netlist: str, characteristics: dict[str, Any]
    ) -> list[str]:
        """Suggest circuit improvements.

        Args:
            netlist: SPICE netlist content
            characteristics: Extracted circuit characteristics

        Returns:
            List of suggested improvements
        """
        improvements = []

        # Check for missing control section
        if not characteristics.get("has_control_section"):
            improvements.append(
                "Add .control section for automated measurements"
            )

        # Check for missing analyses
        if not characteristics.get("analysis_types"):
            improvements.append(
                "Add analysis directives (.op, .ac, .tran) to specify simulation type"
            )

        # Component-based suggestions
        components = characteristics.get("components", [])
        if "mosfet" in components or "transistor" in components:
            improvements.append(
                "Ensure proper device models are included for semiconductors"
            )

        # Default improvements
        if not improvements:
            improvements.append("Consider adding probe points for critical signals")
            improvements.append("Document circuit purpose and expected behavior")

        return improvements


class DebugConvergenceNode(BaseNode):
    """Debugs SPICE convergence issues and suggests fixes.

    Mirrors the SpiceAgent.debug_convergence() method, analyzing convergence
    errors and providing systematic solutions.

    Input Ports:
        error_message (string): Convergence error message from simulator
        netlist (electronics.Netlist): Problematic SPICE netlist
        netlist_content (optional<string>): Raw netlist content (alternative to netlist object)
        simulation_output (optional<string>): Full simulation output for context

    Output Ports:
        diagnosis (string): Root cause analysis
        solutions (array<string>): Step-by-step solutions
        fixed_netlist (string): Modified netlist with suggested fixes
        prevention_tips (array<string>): Tips to prevent similar issues

    Configuration:
        include_fixes (boolean): Include modified netlist with fixes (default: true)
        include_prevention_tips (boolean): Include prevention tips (default: true)
    """

    node_type = "electronics.spice.debug_convergence"
    description = "Debugs SPICE convergence issues and suggests fixes"

    def _default_config(self) -> DebugConvergenceConfig:
        """Return default configuration for debugger."""
        return DebugConvergenceConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for debugger."""
        return [
            PortType(
                name="error_message",
                direction=PortDirection.INPUT,
                port_type="string",
                description="Convergence error message from simulator",
                optional=False,
            ),
            PortType(
                name="netlist",
                direction=PortDirection.INPUT,
                port_type="electronics.Netlist",
                description="Problematic SPICE netlist",
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
                name="simulation_output",
                direction=PortDirection.INPUT,
                port_type="string",
                description="Full simulation output for context",
                optional=True,
                default_value=None,
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for debugger."""
        return [
            PortType(
                name="diagnosis",
                direction=PortDirection.OUTPUT,
                port_type="string",
                description="Root cause analysis",
            ),
            PortType(
                name="solutions",
                direction=PortDirection.OUTPUT,
                port_type="array",
                description="Step-by-step solutions",
            ),
            PortType(
                name="fixed_netlist",
                direction=PortDirection.OUTPUT,
                port_type="string",
                description="Modified netlist with suggested fixes",
            ),
            PortType(
                name="prevention_tips",
                direction=PortDirection.OUTPUT,
                port_type="array",
                description="Tips to prevent similar issues",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute convergence debugging.

        Args:
            inputs: Dictionary with error_message (required), netlist or netlist_content,
                   simulation_output (optional)

        Returns:
            Dictionary with diagnosis, solutions, fixed_netlist, prevention_tips

        Raises:
            ValueError: If error_message is missing or if neither netlist nor netlist_content is provided
        """
        # Validate required inputs
        error_message = inputs.get("error_message")
        if not error_message:
            raise ValueError("error_message is required and cannot be empty")

        # Extract netlist content from input
        netlist_obj = inputs.get("netlist")
        netlist_content = inputs.get("netlist_content")
        simulation_output = inputs.get("simulation_output", "")

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

        # Get configuration
        config = self.config
        if not isinstance(config, DebugConvergenceConfig):
            config = DebugConvergenceConfig()

        logger.info("Debugging SPICE convergence issue")

        # Analyze error message for root cause
        diagnosis = self._diagnose_convergence_issue(
            error_message, netlist_text, simulation_output
        )

        # Generate solutions
        solutions = self._generate_solutions(error_message, netlist_text)

        # Generate fixed netlist if requested
        fixed_netlist = ""
        if config.include_fixes:
            fixed_netlist = self._generate_fixed_netlist(netlist_text, solutions)

        # Generate prevention tips if requested
        prevention_tips = []
        if config.include_prevention_tips:
            prevention_tips = self._generate_prevention_tips(error_message)

        logger.info("Convergence debugging completed successfully")

        return {
            "diagnosis": diagnosis,
            "solutions": solutions,
            "fixed_netlist": fixed_netlist,
            "prevention_tips": prevention_tips,
        }

    def _diagnose_convergence_issue(
        self, error_message: str, netlist: str, simulation_output: str
    ) -> str:
        """Diagnose the root cause of convergence failure.

        Args:
            error_message: Error message from simulator
            netlist: SPICE netlist content
            simulation_output: Full simulation output

        Returns:
            Diagnosis string
        """
        error_lower = error_message.lower()
        combined = (error_message + "\n" + simulation_output).lower()

        diagnosis_parts = [
            "CONVERGENCE ISSUE DIAGNOSIS",
            "=" * 60,
            "",
            "Error: " + error_message,
            "",
            "Root Cause Analysis:",
        ]

        # Identify common convergence issues
        if "timestep too small" in error_lower or "time step" in error_lower:
            diagnosis_parts.append(
                "- Timestep convergence failure: The simulator cannot achieve "
                "convergence within the specified timestep limits. This often "
                "indicates highly nonlinear behavior or numerical instability."
            )
        elif "gmin stepping" in error_lower or "source stepping" in error_lower:
            diagnosis_parts.append(
                "- DC operating point convergence failure: The simulator cannot "
                "find a stable DC solution. This may be due to positive feedback, "
                "floating nodes, or unrealistic initial conditions."
            )
        elif "singular matrix" in error_lower:
            diagnosis_parts.append(
                "- Singular matrix error: The circuit has dependent nodes or "
                "loops that make the admittance matrix non-invertible. Check for "
                "voltage source loops or current source cutsets."
            )
        elif "node" in error_lower and "floating" in combined:
            diagnosis_parts.append(
                "- Floating node detected: One or more nodes lack a DC path to "
                "ground. Every node must have a finite impedance path to ground."
            )
        else:
            diagnosis_parts.append(
                "- General convergence failure: The circuit exhibits numerical "
                "instability. This may be due to extreme component values, "
                "nonlinear device issues, or improper initial conditions."
            )

        return "\n".join(diagnosis_parts)

    def _generate_solutions(
        self, error_message: str, netlist: str
    ) -> list[str]:
        """Generate step-by-step solutions.

        Args:
            error_message: Error message from simulator
            netlist: SPICE netlist content

        Returns:
            List of solution steps
        """
        error_lower = error_message.lower()
        solutions = []

        # Common solutions for different error types
        if "timestep" in error_lower:
            solutions.extend([
                "Increase maximum timestep: Add .options trtol=7 to relax transient tolerance",
                "Add initial conditions: Use .ic directive to set stable starting point",
                "Reduce circuit stiffness: Check for extreme component value ratios",
                "Use smaller initial timestep: Adjust .tran statement start time",
            ])
        elif "gmin" in error_lower or "stepping" in error_lower:
            solutions.extend([
                "Add nodeset hints: Use .nodeset to guide DC solution",
                "Increase gmin: Add .options gmin=1e-9 for better conditioning",
                "Check for floating nodes: Ensure all nodes have DC path to ground",
                "Verify component values: Look for unrealistic resistor/capacitor values",
            ])
        elif "singular" in error_lower:
            solutions.extend([
                "Remove voltage source loops: Check for series voltage sources",
                "Remove current source cutsets: Check for parallel current sources",
                "Add small series resistance: Place 1m\u03a9 resistor in voltage source",
                "Check subcircuit connections: Verify proper node connectivity",
            ])
        else:
            # Generic solutions
            solutions.extend([
                "Add convergence aids: Use .options itl1=300 itl2=200 to increase iterations",
                "Improve initial conditions: Add .nodeset or .ic directives",
                "Check component models: Verify all semiconductor models are defined",
                "Simplify the circuit: Test with ideal components first, then add complexity",
                "Add damping: Include small series resistances in inductive branches",
            ])

        return solutions

    def _generate_fixed_netlist(
        self, netlist: str, solutions: list[str]
    ) -> str:
        """Generate a modified netlist with suggested fixes applied.

        Args:
            netlist: Original SPICE netlist
            solutions: List of solutions to apply

        Returns:
            Modified netlist with fixes
        """
        lines = netlist.split("\n")
        fixed_lines = []

        # Add header comment
        fixed_lines.extend([
            "* MODIFIED NETLIST - Convergence fixes applied",
            "* Original netlist with suggested corrections",
            "",
        ])

        # Add convergence options before any analysis directives
        options_added = False
        for line in lines:
            line_lower = line.strip().lower()

            # Add options before first analysis or control directive
            if not options_added and (
                line_lower.startswith(".ac")
                or line_lower.startswith(".dc")
                or line_lower.startswith(".tran")
                or line_lower.startswith(".control")
            ):
                fixed_lines.extend([
                    "",
                    "* Convergence assistance options",
                    ".options gmin=1e-10 abstol=1e-10 reltol=0.001",
                    ".options itl1=300 itl2=200",
                    "",
                ])
                options_added = True

            fixed_lines.append(line)

        # If no analysis found, add options before .end
        if not options_added:
            # Find .end and insert before it
            end_index = next(
                (i for i, line in enumerate(fixed_lines) if line.strip().lower() == ".end"),
                len(fixed_lines),
            )
            fixed_lines.insert(end_index, "")
            fixed_lines.insert(end_index, "* Convergence assistance options")
            fixed_lines.insert(end_index + 1, ".options gmin=1e-10 abstol=1e-10 reltol=0.001")
            fixed_lines.insert(end_index + 2, ".options itl1=300 itl2=200")
            fixed_lines.insert(end_index + 3, "")

        return "\n".join(fixed_lines)

    def _generate_prevention_tips(self, error_message: str) -> list[str]:
        """Generate prevention tips for future circuits.

        Args:
            error_message: Error message from simulator

        Returns:
            List of prevention tips
        """
        tips = [
            "Always provide DC paths to ground for all nodes",
            "Avoid extreme component value ratios (> 1e12)",
            "Use realistic device models with proper parameters",
            "Start with .op analysis to verify DC operating point",
            "Add .options card with convergence parameters early in design",
            "Use .nodeset for circuits with multiple stable states",
            "Include small damping resistors in LC circuits",
            "Verify subcircuit models before use in larger circuits",
            "Test circuit blocks individually before integration",
            "Monitor convergence warnings during development",
        ]

        error_lower = error_message.lower()

        # Add specific tips based on error type
        if "timestep" in error_lower:
            tips.insert(
                0,
                "For transient analysis: use appropriate timestep and tolerances from the start",
            )
        elif "singular" in error_lower:
            tips.insert(
                0,
                "Check for voltage source loops and current source cutsets during schematic entry",
            )

        return tips


__all__ = [
    "NetlistGeneratorNode",
    "SimulateNode",
    "AnalyzeNode",
    "DebugConvergenceNode",
    "BaseNode",
    "NodeConfig",
    "NetlistGeneratorConfig",
    "SimulateConfig",
    "AnalyzeConfig",
    "DebugConvergenceConfig",
]
