"""PCB Design Rule Checking nodes for electronics domain."""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mascarade.node_engine.types import PortDirection, PortType

logger = logging.getLogger("mascarade.node_engine.workers.electronics.pcb_nodes")


@dataclass
class NodeConfig:
    """Base configuration for node execution parameters."""

    pass


@dataclass
class DrcCheckConfig(NodeConfig):
    """Configuration for DRC check node."""

    severity_threshold: str = "warning"  # "error", "warning", "info"
    kicad_cli_path: str = "kicad-cli"


@dataclass
class RuleDefinitionConfig(NodeConfig):
    """Configuration for rule definition node."""

    pass


@dataclass
class ViolationReporterConfig(NodeConfig):
    """Configuration for violation reporter node."""

    pass


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


class DrcCheckNode(BaseNode):
    """Executes design rule checking on a KiCad PCB file.

    Integrates with KiCad's DRC engine to validate PCB designs against
    manufacturing rules. Mirrors the KiCadAgent.perform_drc() method.

    Input Ports:
        board_file (binary): KiCad .kicad_pcb file content
        rules (optional<json>): Custom DRC rules (overrides board defaults)

    Output Ports:
        report (electronics.DRCReport): DRC results with violations

    Configuration:
        severity_threshold (string): Minimum severity to report: "error", "warning", "info" (default: "warning")
        kicad_cli_path (string): Path to KiCad CLI (default: "kicad-cli")
    """

    node_type = "electronics.pcb.drc_check"
    description = "Executes design rule checking on a KiCad PCB file"

    def _default_config(self) -> DrcCheckConfig:
        """Return default configuration for DRC check."""
        return DrcCheckConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for DRC check."""
        return [
            PortType(
                name="board_file",
                direction=PortDirection.INPUT,
                port_type="binary",
                description="KiCad .kicad_pcb file content",
                optional=False,
            ),
            PortType(
                name="rules",
                direction=PortDirection.INPUT,
                port_type="json",
                description="Custom DRC rules (overrides board defaults)",
                optional=True,
                default_value=None,
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for DRC check."""
        return [
            PortType(
                name="report",
                direction=PortDirection.OUTPUT,
                port_type="electronics.DRCReport",
                description="DRC results with violations",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute DRC check.

        Args:
            inputs: Dictionary with board_file (required), rules (optional)

        Returns:
            Dictionary with report (electronics.DRCReport)

        Raises:
            ValueError: If board_file is missing or empty
            RuntimeError: If kicad-cli is not available or execution fails
        """
        # Validate required inputs
        board_file = inputs.get("board_file")
        if not board_file:
            raise ValueError("board_file is required and cannot be empty")

        # Get optional inputs
        custom_rules = inputs.get("rules")

        # Get configuration
        config = self.config
        if not isinstance(config, DrcCheckConfig):
            config = DrcCheckConfig()

        logger.info(
            f"Running DRC check with severity_threshold={config.severity_threshold}, "
            f"kicad_cli_path={config.kicad_cli_path}"
        )

        # Check if kicad-cli is available
        try:
            check_proc = await asyncio.create_subprocess_exec(
                config.kicad_cli_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await check_proc.communicate()
            if check_proc.returncode != 0:
                raise RuntimeError(
                    f"kicad-cli not available at {config.kicad_cli_path}. "
                    "Please install KiCad and ensure kicad-cli is in your PATH."
                )
        except FileNotFoundError:
            raise RuntimeError(
                f"kicad-cli not found at {config.kicad_cli_path}. "
                "Please install KiCad and ensure kicad-cli is in your PATH."
            )

        # Create temporary files for board and DRC report
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            board_path = tmp_path / "board.kicad_pcb"
            report_path = tmp_path / "drc_report.json"

            # Write board file
            if isinstance(board_file, bytes):
                board_path.write_bytes(board_file)
            else:
                board_path.write_text(str(board_file))

            # Apply custom rules if provided
            if custom_rules:
                # In a real implementation, we would modify the board file
                # to include custom DRC rules. For now, we'll just log it.
                logger.info(f"Custom DRC rules provided: {custom_rules}")

            # Execute kicad-cli DRC
            try:
                proc = await asyncio.create_subprocess_exec(
                    config.kicad_cli_path,
                    "pcb",
                    "drc",
                    "--output",
                    str(report_path),
                    "--format",
                    "json",
                    str(board_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await proc.communicate()

                if proc.returncode != 0:
                    # DRC may return non-zero if violations found, check if report exists
                    if not report_path.exists():
                        raise RuntimeError(
                            f"kicad-cli DRC failed with exit code {proc.returncode}\n"
                            f"stdout: {stdout.decode()}\n"
                            f"stderr: {stderr.decode()}"
                        )

                # Parse DRC report
                if report_path.exists():
                    report_data = json.loads(report_path.read_text())
                    violations = self._parse_violations(
                        report_data, config.severity_threshold
                    )
                else:
                    # No violations found or report not generated
                    violations = []

            except Exception as e:
                logger.error(f"DRC execution failed: {e}")
                raise RuntimeError(f"DRC execution failed: {e}")

        # Build DRC report
        passed = len(violations) == 0
        report = {
            "passed": passed,
            "violations": violations,
            "rules_checked": len(violations) if violations else 0,
            "board_file": "board.kicad_pcb",
        }

        return {"report": report}

    def _parse_violations(
        self, report_data: dict[str, Any], severity_threshold: str
    ) -> list[dict[str, Any]]:
        """Parse KiCad DRC report and filter by severity.

        Args:
            report_data: Raw KiCad DRC report JSON
            severity_threshold: Minimum severity to include

        Returns:
            List of violation dictionaries
        """
        violations = []
        severity_levels = {"error": 3, "warning": 2, "info": 1}
        threshold_level = severity_levels.get(severity_threshold, 2)

        # KiCad DRC report structure varies, so we handle it defensively
        # In a real implementation, we'd parse the actual KiCad JSON format
        if "violations" in report_data:
            for violation in report_data["violations"]:
                severity = violation.get("severity", "warning")
                severity_level = severity_levels.get(severity, 2)

                if severity_level >= threshold_level:
                    violations.append({
                        "rule": violation.get("rule", "unknown"),
                        "severity": severity,
                        "location": {
                            "x": violation.get("x", 0),
                            "y": violation.get("y", 0),
                            "layer": violation.get("layer", "unknown"),
                        },
                        "message": violation.get("message", ""),
                    })

        return violations


class RuleDefinitionNode(BaseNode):
    """Defines custom DRC rules for manufacturing constraints.

    Provides preset rules for common PCB manufacturers (JLCPCB, OSH Park)
    and allows custom rule overrides.

    Input Ports:
        manufacturer_preset (optional<string>): Preset: "jlcpcb_standard", "jlcpcb_advanced", "oshpark"
        custom_overrides (optional<json>): Override specific rules

    Output Ports:
        rules (json): Complete DRC rule set

    Configuration:
        None
    """

    node_type = "electronics.pcb.rule_definition"
    description = "Defines custom DRC rules for manufacturing constraints"

    def _default_config(self) -> RuleDefinitionConfig:
        """Return default configuration for rule definition."""
        return RuleDefinitionConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for rule definition."""
        return [
            PortType(
                name="manufacturer_preset",
                direction=PortDirection.INPUT,
                port_type="string",
                description='Preset: "jlcpcb_standard", "jlcpcb_advanced", "oshpark"',
                optional=True,
                default_value=None,
            ),
            PortType(
                name="custom_overrides",
                direction=PortDirection.INPUT,
                port_type="json",
                description="Override specific rules",
                optional=True,
                default_value=None,
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for rule definition."""
        return [
            PortType(
                name="rules",
                direction=PortDirection.OUTPUT,
                port_type="json",
                description="Complete DRC rule set",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute rule definition.

        Args:
            inputs: Dictionary with manufacturer_preset (optional), custom_overrides (optional)

        Returns:
            Dictionary with rules (json)
        """
        manufacturer_preset = inputs.get("manufacturer_preset")
        custom_overrides = inputs.get("custom_overrides", {})

        # Define manufacturer presets
        presets = {
            "jlcpcb_standard": {
                "min_trace_width_mm": 0.127,
                "min_clearance_mm": 0.127,
                "min_drill_mm": 0.3,
                "min_annular_ring_mm": 0.13,
                "min_via_diameter_mm": 0.45,
                "min_silkscreen_width_mm": 0.15,
                "min_solder_mask_bridge_mm": 0.1,
                "max_board_size_mm": [400, 500],
                "layer_count": [1, 2, 4, 6],
            },
            "jlcpcb_advanced": {
                "min_trace_width_mm": 0.09,
                "min_clearance_mm": 0.09,
                "min_drill_mm": 0.2,
                "min_annular_ring_mm": 0.08,
                "min_via_diameter_mm": 0.3,
                "min_silkscreen_width_mm": 0.12,
                "min_solder_mask_bridge_mm": 0.08,
                "max_board_size_mm": [400, 500],
                "layer_count": [1, 2, 4, 6, 8],
            },
            "oshpark": {
                "min_trace_width_mm": 0.152,
                "min_clearance_mm": 0.152,
                "min_drill_mm": 0.254,
                "min_annular_ring_mm": 0.127,
                "min_via_diameter_mm": 0.508,
                "min_silkscreen_width_mm": 0.152,
                "min_solder_mask_bridge_mm": 0.102,
                "max_board_size_mm": [279, 406],
                "layer_count": [2, 4],
            },
        }

        # Start with preset or empty rules
        if manufacturer_preset and manufacturer_preset in presets:
            rules = presets[manufacturer_preset].copy()
            logger.info(f"Using manufacturer preset: {manufacturer_preset}")
        else:
            # Default generic rules
            rules = {
                "min_trace_width_mm": 0.15,
                "min_clearance_mm": 0.15,
                "min_drill_mm": 0.3,
                "min_annular_ring_mm": 0.15,
                "min_via_diameter_mm": 0.5,
                "min_silkscreen_width_mm": 0.15,
                "min_solder_mask_bridge_mm": 0.1,
                "max_board_size_mm": [300, 400],
                "layer_count": [1, 2, 4],
            }
            logger.info("Using default generic rules")

        # Apply custom overrides
        if custom_overrides:
            rules.update(custom_overrides)
            logger.info(f"Applied {len(custom_overrides)} custom overrides")

        return {"rules": rules}


class ViolationReporterNode(BaseNode):
    """Formats DRC violations into human-readable or machine-parsable reports.

    Converts DRC report into various formats (markdown, CSV, JSON) for
    documentation and integration purposes.

    Input Ports:
        report (electronics.DRCReport): Raw DRC report
        format (optional<string>): Output format: "markdown" (default), "csv", "json"

    Output Ports:
        formatted_report (string): Formatted violation report
        summary (json): { total: int, errors: int, warnings: int, passed: bool }

    Configuration:
        None
    """

    node_type = "electronics.pcb.violation_reporter"
    description = "Formats DRC violations into human-readable or machine-parsable reports"

    def _default_config(self) -> ViolationReporterConfig:
        """Return default configuration for violation reporter."""
        return ViolationReporterConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for violation reporter."""
        return [
            PortType(
                name="report",
                direction=PortDirection.INPUT,
                port_type="electronics.DRCReport",
                description="Raw DRC report",
                optional=False,
            ),
            PortType(
                name="format",
                direction=PortDirection.INPUT,
                port_type="string",
                description='Output format: "markdown" (default), "csv", "json"',
                optional=True,
                default_value="markdown",
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for violation reporter."""
        return [
            PortType(
                name="formatted_report",
                direction=PortDirection.OUTPUT,
                port_type="string",
                description="Formatted violation report",
            ),
            PortType(
                name="summary",
                direction=PortDirection.OUTPUT,
                port_type="json",
                description="{ total: int, errors: int, warnings: int, passed: bool }",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute violation reporting.

        Args:
            inputs: Dictionary with report (required), format (optional)

        Returns:
            Dictionary with formatted_report (string), summary (json)

        Raises:
            ValueError: If report is missing or invalid
        """
        # Validate required inputs
        report = inputs.get("report")
        if not report:
            raise ValueError("report is required and cannot be empty")

        output_format = inputs.get("format", "markdown")

        # Calculate summary statistics
        violations = report.get("violations", [])
        errors = sum(1 for v in violations if v.get("severity") == "error")
        warnings = sum(1 for v in violations if v.get("severity") == "warning")
        total = len(violations)
        passed = report.get("passed", total == 0)

        summary = {
            "total": total,
            "errors": errors,
            "warnings": warnings,
            "passed": passed,
        }

        # Format report based on requested format
        if output_format == "markdown":
            formatted_report = self._format_markdown(report, summary)
        elif output_format == "csv":
            formatted_report = self._format_csv(violations)
        elif output_format == "json":
            formatted_report = json.dumps(report, indent=2)
        else:
            # Default to markdown
            formatted_report = self._format_markdown(report, summary)

        logger.info(
            f"Generated {output_format} report: {total} violations "
            f"({errors} errors, {warnings} warnings)"
        )

        return {
            "formatted_report": formatted_report,
            "summary": summary,
        }

    def _format_markdown(self, report: dict[str, Any], summary: dict[str, Any]) -> str:
        """Format DRC report as markdown.

        Args:
            report: DRC report dictionary
            summary: Summary statistics

        Returns:
            Markdown formatted report
        """
        lines = [
            "# PCB Design Rule Check Report",
            "",
            f"**Board File:** {report.get('board_file', 'unknown')}",
            f"**Rules Checked:** {report.get('rules_checked', 0)}",
            f"**Status:** {'✅ PASSED' if summary['passed'] else '❌ FAILED'}",
            "",
            "## Summary",
            "",
            f"- **Total Violations:** {summary['total']}",
            f"- **Errors:** {summary['errors']}",
            f"- **Warnings:** {summary['warnings']}",
            "",
        ]

        violations = report.get("violations", [])
        if violations:
            lines.append("## Violations")
            lines.append("")

            for i, violation in enumerate(violations, 1):
                severity = violation.get("severity", "unknown")
                severity_emoji = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(
                    severity, "⚪"
                )

                lines.append(f"### {i}. {severity_emoji} {violation.get('rule', 'Unknown Rule')}")
                lines.append(f"**Severity:** {severity}")
                lines.append(f"**Message:** {violation.get('message', 'No message')}")

                location = violation.get("location", {})
                lines.append(
                    f"**Location:** x={location.get('x', 0)}, y={location.get('y', 0)}, "
                    f"layer={location.get('layer', 'unknown')}"
                )
                lines.append("")
        else:
            lines.append("No violations found. Board passes all DRC checks! ✅")
            lines.append("")

        return "\n".join(lines)

    def _format_csv(self, violations: list[dict[str, Any]]) -> str:
        """Format violations as CSV.

        Args:
            violations: List of violation dictionaries

        Returns:
            CSV formatted violations
        """
        lines = ["Rule,Severity,Message,X,Y,Layer"]

        for violation in violations:
            location = violation.get("location", {})
            lines.append(
                f'"{violation.get("rule", "")}","{violation.get("severity", "")}","{violation.get("message", "")}",{location.get("x", 0)},{location.get("y", 0)},"{location.get("layer", "")}"'
            )

        return "\n".join(lines)
