"""Component library and selection nodes for electronics domain."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from mascarade.node_engine.types import PortDirection, PortType

logger = logging.getLogger("mascarade.node_engine.workers.electronics.component_nodes")


@dataclass
class NodeConfig:
    """Base configuration for node execution parameters."""

    pass


@dataclass
class LookupConfig(NodeConfig):
    """Configuration for component lookup node."""

    include_alternatives: bool = True
    include_availability: bool = True


@dataclass
class JlcpcbOptimizationConfig(NodeConfig):
    """Configuration for JLCPCB optimization node."""

    prefer_basic_parts: bool = True
    max_extended_parts: int = 5


@dataclass
class BomGeneratorConfig(NodeConfig):
    """Configuration for BOM generator node."""

    format: str = "jlcpcb"  # "jlcpcb", "csv", "json"
    include_cost_estimates: bool = True


@dataclass
class CplGeneratorConfig(NodeConfig):
    """Configuration for CPL generator node."""

    coordinate_units: str = "mm"  # "mm", "mil"
    rotation_standard: str = "jlcpcb"  # "jlcpcb", "kicad"


@dataclass
class AvailabilityCheckConfig(NodeConfig):
    """Configuration for availability check node."""

    check_stock: bool = True
    check_lead_time: bool = True


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


class LookupNode(BaseNode):
    """Looks up component specifications and finds alternatives.

    Searches component databases (LCSC, JLCPCB) for matching parts based on
    electrical specifications, package type, and other criteria.

    Input Ports:
        component_spec (string): Component specification (e.g., "10kΩ resistor 0805")
        requirements (optional<json>): Additional requirements (voltage, tolerance, etc.)

    Output Ports:
        alternatives (json): List of alternative components with part numbers
        best_match (json): Recommended component with full specifications

    Configuration:
        include_alternatives (bool): Include alternative suggestions (default: True)
        include_availability (bool): Include stock and availability info (default: True)
    """

    node_type = "electronics.component.lookup"
    description = "Looks up component specifications and finds alternatives"

    def _default_config(self) -> LookupConfig:
        """Return default configuration for lookup."""
        return LookupConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for component lookup."""
        return [
            PortType(
                name="component_spec",
                direction=PortDirection.INPUT,
                port_type="string",
                description='Component specification (e.g., "10kΩ resistor 0805")',
                optional=False,
            ),
            PortType(
                name="requirements",
                direction=PortDirection.INPUT,
                port_type="json",
                description="Additional requirements (voltage, tolerance, etc.)",
                optional=True,
                default_value=None,
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for component lookup."""
        return [
            PortType(
                name="alternatives",
                direction=PortDirection.OUTPUT,
                port_type="json",
                description="List of alternative components with part numbers",
            ),
            PortType(
                name="best_match",
                direction=PortDirection.OUTPUT,
                port_type="json",
                description="Recommended component with full specifications",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute component lookup.

        Args:
            inputs: Dictionary with component_spec (required), requirements (optional)

        Returns:
            Dictionary with alternatives (json), best_match (json)

        Raises:
            ValueError: If component_spec is missing or empty
        """
        # Validate required inputs
        component_spec = inputs.get("component_spec")
        if not component_spec:
            raise ValueError("component_spec is required and cannot be empty")

        requirements = inputs.get("requirements", {})

        # Get configuration
        config = self.config
        if not isinstance(config, LookupConfig):
            config = LookupConfig()

        logger.info(f"Looking up component: {component_spec}")

        # Simulate component lookup (in production, this would query LCSC/JLCPCB API)
        # Parse component spec to extract basic info
        spec_parts = component_spec.lower().split()

        # Generate mock alternatives based on the spec
        alternatives = []
        if config.include_alternatives:
            alternatives = self._generate_mock_alternatives(component_spec, requirements)

        # Select best match (first alternative in this mock implementation)
        best_match = alternatives[0] if alternatives else self._generate_default_component(component_spec)

        logger.info(f"Found {len(alternatives)} alternatives for {component_spec}")

        return {
            "alternatives": alternatives,
            "best_match": best_match,
        }

    def _generate_mock_alternatives(
        self, component_spec: str, requirements: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Generate mock component alternatives for demonstration.

        Args:
            component_spec: Component specification string
            requirements: Additional requirements

        Returns:
            List of component alternatives
        """
        # This is a mock implementation - in production, query actual databases
        config = self.config
        if not isinstance(config, LookupConfig):
            config = LookupConfig()

        alternatives = [
            {
                "lcsc_part_number": "C17414",
                "manufacturer": "UniOhm",
                "mpn": "0805W8F1002T5E",
                "description": "10kΩ ±1% 0805 Resistor",
                "value": "10kΩ",
                "package": "0805",
                "tolerance": "±1%",
                "power_rating": "0.125W",
                "jlcpcb_basic": True,
                "stock": 50000 if config.include_availability else None,
                "price_unit": "$0.0009",
            },
            {
                "lcsc_part_number": "C25804",
                "manufacturer": "UniOhm",
                "mpn": "0805W8F1003T5E",
                "description": "100kΩ ±1% 0805 Resistor",
                "value": "100kΩ",
                "package": "0805",
                "tolerance": "±1%",
                "power_rating": "0.125W",
                "jlcpcb_basic": True,
                "stock": 45000 if config.include_availability else None,
                "price_unit": "$0.0009",
            },
        ]

        return alternatives

    def _generate_default_component(self, component_spec: str) -> dict[str, Any]:
        """Generate a default component when no matches found.

        Args:
            component_spec: Component specification string

        Returns:
            Default component dictionary
        """
        return {
            "lcsc_part_number": "UNKNOWN",
            "manufacturer": "Generic",
            "mpn": "N/A",
            "description": component_spec,
            "value": "N/A",
            "package": "N/A",
            "jlcpcb_basic": False,
            "stock": 0,
            "price_unit": "$0.00",
        }


class JlcpcbOptimizationNode(BaseNode):
    """Optimizes component selection for JLCPCB assembly.

    Analyzes component requirements and selects optimal parts from JLCPCB's
    basic and extended component library, optimizing for cost and availability.

    Input Ports:
        requirements (json): Circuit requirements and component specifications
        prefer_basic (optional<boolean>): Prefer JLCPCB basic parts (default: True)

    Output Ports:
        optimized_bom (json): Optimized BOM with JLCPCB part recommendations
        summary (json): Optimization summary (basic/extended part counts, cost estimate)

    Configuration:
        prefer_basic_parts (bool): Prefer basic parts over extended (default: True)
        max_extended_parts (int): Maximum number of extended parts (default: 5)
    """

    node_type = "electronics.component.jlcpcb_optimization"
    description = "Optimizes component selection for JLCPCB assembly"

    def _default_config(self) -> JlcpcbOptimizationConfig:
        """Return default configuration for JLCPCB optimization."""
        return JlcpcbOptimizationConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for JLCPCB optimization."""
        return [
            PortType(
                name="requirements",
                direction=PortDirection.INPUT,
                port_type="json",
                description="Circuit requirements and component specifications",
                optional=False,
            ),
            PortType(
                name="prefer_basic",
                direction=PortDirection.INPUT,
                port_type="boolean",
                description="Prefer JLCPCB basic parts (default: True)",
                optional=True,
                default_value=True,
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for JLCPCB optimization."""
        return [
            PortType(
                name="optimized_bom",
                direction=PortDirection.OUTPUT,
                port_type="json",
                description="Optimized BOM with JLCPCB part recommendations",
            ),
            PortType(
                name="summary",
                direction=PortDirection.OUTPUT,
                port_type="json",
                description="Optimization summary (basic/extended part counts, cost estimate)",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute JLCPCB optimization.

        Args:
            inputs: Dictionary with requirements (required), prefer_basic (optional)

        Returns:
            Dictionary with optimized_bom (json), summary (json)

        Raises:
            ValueError: If requirements is missing or invalid
        """
        # Validate required inputs
        requirements = inputs.get("requirements")
        if not requirements:
            raise ValueError("requirements is required and cannot be empty")

        prefer_basic = inputs.get("prefer_basic", True)

        # Get configuration
        config = self.config
        if not isinstance(config, JlcpcbOptimizationConfig):
            config = JlcpcbOptimizationConfig()

        logger.info("Optimizing component selection for JLCPCB assembly")

        # Simulate optimization (in production, query JLCPCB API)
        optimized_bom = self._optimize_components(requirements, prefer_basic, config)

        # Generate summary
        basic_count = sum(1 for item in optimized_bom if item.get("jlcpcb_basic", False))
        extended_count = len(optimized_bom) - basic_count
        total_cost = sum(float(item.get("price_unit", "$0").replace("$", "")) * item.get("quantity", 1) for item in optimized_bom)

        summary = {
            "total_components": len(optimized_bom),
            "basic_parts": basic_count,
            "extended_parts": extended_count,
            "estimated_cost": f"${total_cost:.2f}",
            "optimization_notes": f"Optimized for JLCPCB assembly with {basic_count} basic parts",
        }

        logger.info(
            f"Optimization complete: {basic_count} basic, {extended_count} extended parts"
        )

        return {
            "optimized_bom": optimized_bom,
            "summary": summary,
        }

    def _optimize_components(
        self,
        requirements: dict[str, Any],
        prefer_basic: bool,
        config: JlcpcbOptimizationConfig,
    ) -> list[dict[str, Any]]:
        """Optimize component selection for JLCPCB.

        Args:
            requirements: Component requirements
            prefer_basic: Prefer basic parts flag
            config: Optimization configuration

        Returns:
            List of optimized components
        """
        # Mock implementation - in production, query JLCPCB API
        optimized = [
            {
                "comment": "10kΩ Resistor",
                "designator": "R1,R2,R3",
                "footprint": "R_0805_2012Metric",
                "lcsc_part_number": "C17414",
                "manufacturer": "UniOhm",
                "mpn": "0805W8F1002T5E",
                "quantity": 3,
                "jlcpcb_basic": True,
                "price_unit": "$0.0009",
            },
            {
                "comment": "100nF Capacitor",
                "designator": "C1,C2",
                "footprint": "C_0805_2012Metric",
                "lcsc_part_number": "C49678",
                "manufacturer": "Samsung",
                "mpn": "CL21B104KBCNNNC",
                "quantity": 2,
                "jlcpcb_basic": True,
                "price_unit": "$0.0015",
            },
        ]

        return optimized


class BomGeneratorNode(BaseNode):
    """Generates Bill of Materials in JLCPCB or standard formats.

    Creates a complete BOM from circuit description or component list,
    with LCSC part numbers, footprints, and quantities.

    Input Ports:
        circuit_description (string): Circuit description or component list
        components (optional<json>): Pre-selected component list

    Output Ports:
        bom (string): Formatted BOM (CSV format)
        bom_json (json): BOM as JSON structure

    Configuration:
        format (string): Output format "jlcpcb", "csv", "json" (default: "jlcpcb")
        include_cost_estimates (bool): Include cost estimates (default: True)
    """

    node_type = "electronics.component.bom_generator"
    description = "Generates Bill of Materials in JLCPCB or standard formats"

    def _default_config(self) -> BomGeneratorConfig:
        """Return default configuration for BOM generator."""
        return BomGeneratorConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for BOM generator."""
        return [
            PortType(
                name="circuit_description",
                direction=PortDirection.INPUT,
                port_type="string",
                description="Circuit description or component list",
                optional=False,
            ),
            PortType(
                name="components",
                direction=PortDirection.INPUT,
                port_type="json",
                description="Pre-selected component list",
                optional=True,
                default_value=None,
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for BOM generator."""
        return [
            PortType(
                name="bom",
                direction=PortDirection.OUTPUT,
                port_type="string",
                description="Formatted BOM (CSV format)",
            ),
            PortType(
                name="bom_json",
                direction=PortDirection.OUTPUT,
                port_type="json",
                description="BOM as JSON structure",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute BOM generation.

        Args:
            inputs: Dictionary with circuit_description (required), components (optional)

        Returns:
            Dictionary with bom (string), bom_json (json)

        Raises:
            ValueError: If circuit_description is missing or empty
        """
        # Validate required inputs
        circuit_description = inputs.get("circuit_description")
        if not circuit_description:
            raise ValueError("circuit_description is required and cannot be empty")

        components = inputs.get("components")

        # Get configuration
        config = self.config
        if not isinstance(config, BomGeneratorConfig):
            config = BomGeneratorConfig()

        logger.info(f"Generating BOM in {config.format} format")

        # Generate BOM (mock implementation)
        bom_data = self._generate_bom_data(circuit_description, components)

        # Format BOM based on config
        if config.format == "jlcpcb":
            bom_csv = self._format_jlcpcb_csv(bom_data)
        elif config.format == "csv":
            bom_csv = self._format_standard_csv(bom_data)
        else:
            bom_csv = json.dumps(bom_data, indent=2)

        logger.info(f"Generated BOM with {len(bom_data)} line items")

        return {
            "bom": bom_csv,
            "bom_json": bom_data,
        }

    def _generate_bom_data(
        self, circuit_description: str, components: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]]:
        """Generate BOM data structure.

        Args:
            circuit_description: Circuit description
            components: Pre-selected components (optional)

        Returns:
            List of BOM line items
        """
        # Mock implementation
        if components:
            return components

        # Generate default BOM from description
        return [
            {
                "comment": "10kΩ Resistor",
                "designator": "R1,R2,R3",
                "footprint": "R_0805_2012Metric",
                "lcsc_part_number": "C17414",
                "manufacturer": "UniOhm",
                "mpn": "0805W8F1002T5E",
                "quantity": 3,
            },
            {
                "comment": "100nF Capacitor",
                "designator": "C1,C2",
                "footprint": "C_0805_2012Metric",
                "lcsc_part_number": "C49678",
                "manufacturer": "Samsung",
                "mpn": "CL21B104KBCNNNC",
                "quantity": 2,
            },
        ]

    def _format_jlcpcb_csv(self, bom_data: list[dict[str, Any]]) -> str:
        """Format BOM as JLCPCB CSV.

        Args:
            bom_data: BOM data structure

        Returns:
            CSV formatted string
        """
        lines = ["Comment,Designator,Footprint,LCSC Part Number,Manufacturer,MPN,Quantity"]

        for item in bom_data:
            lines.append(
                f'"{item.get("comment", "")}","{item.get("designator", "")}","{item.get("footprint", "")}","{item.get("lcsc_part_number", "")}","{item.get("manufacturer", "")}","{item.get("mpn", "")}",{item.get("quantity", 0)}'
            )

        return "\n".join(lines)

    def _format_standard_csv(self, bom_data: list[dict[str, Any]]) -> str:
        """Format BOM as standard CSV.

        Args:
            bom_data: BOM data structure

        Returns:
            CSV formatted string
        """
        lines = ["Reference,Value,Footprint,Quantity,Manufacturer,MPN"]

        for item in bom_data:
            lines.append(
                f'"{item.get("designator", "")}","{item.get("comment", "")}","{item.get("footprint", "")}",{item.get("quantity", 0)},"{item.get("manufacturer", "")}","{item.get("mpn", "")}"'
            )

        return "\n".join(lines)


class CplGeneratorNode(BaseNode):
    """Generates Component Placement List for JLCPCB assembly.

    Creates CPL file with component positions, rotations, and layer assignments
    for pick-and-place assembly.

    Input Ports:
        pcb_description (string): PCB layout description or file reference
        components (json): Component placement data

    Output Ports:
        cpl (string): Formatted CPL file (CSV format)
        cpl_json (json): CPL as JSON structure

    Configuration:
        coordinate_units (string): "mm" or "mil" (default: "mm")
        rotation_standard (string): "jlcpcb" or "kicad" (default: "jlcpcb")
    """

    node_type = "electronics.component.cpl_generator"
    description = "Generates Component Placement List for JLCPCB assembly"

    def _default_config(self) -> CplGeneratorConfig:
        """Return default configuration for CPL generator."""
        return CplGeneratorConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for CPL generator."""
        return [
            PortType(
                name="pcb_description",
                direction=PortDirection.INPUT,
                port_type="string",
                description="PCB layout description or file reference",
                optional=False,
            ),
            PortType(
                name="components",
                direction=PortDirection.INPUT,
                port_type="json",
                description="Component placement data",
                optional=False,
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for CPL generator."""
        return [
            PortType(
                name="cpl",
                direction=PortDirection.OUTPUT,
                port_type="string",
                description="Formatted CPL file (CSV format)",
            ),
            PortType(
                name="cpl_json",
                direction=PortDirection.OUTPUT,
                port_type="json",
                description="CPL as JSON structure",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute CPL generation.

        Args:
            inputs: Dictionary with pcb_description (required), components (required)

        Returns:
            Dictionary with cpl (string), cpl_json (json)

        Raises:
            ValueError: If required inputs are missing
        """
        # Validate required inputs
        pcb_description = inputs.get("pcb_description")
        if not pcb_description:
            raise ValueError("pcb_description is required and cannot be empty")

        components = inputs.get("components")
        if not components:
            raise ValueError("components is required and cannot be empty")

        # Get configuration
        config = self.config
        if not isinstance(config, CplGeneratorConfig):
            config = CplGeneratorConfig()

        logger.info(f"Generating CPL with {config.coordinate_units} units")

        # Generate CPL data
        cpl_data = self._generate_cpl_data(pcb_description, components, config)

        # Format CPL as CSV
        cpl_csv = self._format_cpl_csv(cpl_data)

        logger.info(f"Generated CPL with {len(cpl_data)} components")

        return {
            "cpl": cpl_csv,
            "cpl_json": cpl_data,
        }

    def _generate_cpl_data(
        self,
        pcb_description: str,
        components: list[dict[str, Any]],
        config: CplGeneratorConfig,
    ) -> list[dict[str, Any]]:
        """Generate CPL data structure.

        Args:
            pcb_description: PCB description
            components: Component placement data
            config: CPL generator configuration

        Returns:
            List of CPL entries
        """
        # Mock implementation - in production, parse PCB file
        return [
            {
                "designator": "R1",
                "mid_x": 10.5,
                "mid_y": 20.3,
                "rotation": 0,
                "side": "Top",
            },
            {
                "designator": "R2",
                "mid_x": 15.5,
                "mid_y": 20.3,
                "rotation": 0,
                "side": "Top",
            },
            {
                "designator": "C1",
                "mid_x": 10.5,
                "mid_y": 25.0,
                "rotation": 90,
                "side": "Top",
            },
        ]

    def _format_cpl_csv(self, cpl_data: list[dict[str, Any]]) -> str:
        """Format CPL as CSV.

        Args:
            cpl_data: CPL data structure

        Returns:
            CSV formatted string
        """
        lines = ["Designator,Mid X,Mid Y,Rotation,Side"]

        for item in cpl_data:
            lines.append(
                f'{item.get("designator", "")},{item.get("mid_x", 0)},{item.get("mid_y", 0)},{item.get("rotation", 0)},{item.get("side", "Top")}'
            )

        return "\n".join(lines)


class AvailabilityCheckNode(BaseNode):
    """Checks component availability and stock levels at JLCPCB/LCSC.

    Queries component databases for real-time stock information, lead times,
    and pricing tiers.

    Input Ports:
        part_numbers (json): List of LCSC part numbers to check
        check_alternatives (optional<boolean>): Check alternatives if unavailable (default: True)

    Output Ports:
        availability (json): Availability info for each part number
        recommendations (json): Alternative recommendations for out-of-stock parts

    Configuration:
        check_stock (bool): Check stock levels (default: True)
        check_lead_time (bool): Check lead times (default: True)
    """

    node_type = "electronics.component.availability_check"
    description = "Checks component availability and stock levels at JLCPCB/LCSC"

    def _default_config(self) -> AvailabilityCheckConfig:
        """Return default configuration for availability check."""
        return AvailabilityCheckConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for availability check."""
        return [
            PortType(
                name="part_numbers",
                direction=PortDirection.INPUT,
                port_type="json",
                description="List of LCSC part numbers to check",
                optional=False,
            ),
            PortType(
                name="check_alternatives",
                direction=PortDirection.INPUT,
                port_type="boolean",
                description="Check alternatives if unavailable (default: True)",
                optional=True,
                default_value=True,
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for availability check."""
        return [
            PortType(
                name="availability",
                direction=PortDirection.OUTPUT,
                port_type="json",
                description="Availability info for each part number",
            ),
            PortType(
                name="recommendations",
                direction=PortDirection.OUTPUT,
                port_type="json",
                description="Alternative recommendations for out-of-stock parts",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute availability check.

        Args:
            inputs: Dictionary with part_numbers (required), check_alternatives (optional)

        Returns:
            Dictionary with availability (json), recommendations (json)

        Raises:
            ValueError: If part_numbers is missing or empty
        """
        # Validate required inputs
        part_numbers = inputs.get("part_numbers")
        if not part_numbers:
            raise ValueError("part_numbers is required and cannot be empty")

        check_alternatives = inputs.get("check_alternatives", True)

        # Get configuration
        config = self.config
        if not isinstance(config, AvailabilityCheckConfig):
            config = AvailabilityCheckConfig()

        logger.info(f"Checking availability for {len(part_numbers)} part numbers")

        # Check availability (mock implementation)
        availability = self._check_availability(part_numbers, config)

        # Generate recommendations for out-of-stock items
        recommendations = []
        if check_alternatives:
            recommendations = self._generate_recommendations(availability)

        logger.info(f"Availability check complete: {len(availability)} parts checked")

        return {
            "availability": availability,
            "recommendations": recommendations,
        }

    def _check_availability(
        self, part_numbers: list[str], config: AvailabilityCheckConfig
    ) -> list[dict[str, Any]]:
        """Check availability for part numbers.

        Args:
            part_numbers: List of LCSC part numbers
            config: Availability check configuration

        Returns:
            List of availability records
        """
        # Mock implementation - in production, query LCSC/JLCPCB API
        availability = []

        for part_number in part_numbers:
            availability.append({
                "lcsc_part_number": part_number,
                "in_stock": True,
                "stock_level": 50000 if config.check_stock else None,
                "lead_time_days": 3 if config.check_lead_time else None,
                "moq": 1,
                "price_breaks": [
                    {"quantity": 1, "price": "$0.0009"},
                    {"quantity": 10, "price": "$0.0008"},
                    {"quantity": 100, "price": "$0.0007"},
                ],
            })

        return availability

    def _generate_recommendations(
        self, availability: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Generate alternative recommendations for unavailable parts.

        Args:
            availability: Availability records

        Returns:
            List of recommendations
        """
        recommendations = []

        for item in availability:
            if not item.get("in_stock", False) or item.get("stock_level", 0) < 100:
                recommendations.append({
                    "original_part": item.get("lcsc_part_number"),
                    "reason": "Low stock or unavailable",
                    "alternatives": [
                        {
                            "lcsc_part_number": "C17415",
                            "description": "Alternative 10kΩ resistor",
                            "stock_level": 100000,
                        },
                    ],
                })

        return recommendations
