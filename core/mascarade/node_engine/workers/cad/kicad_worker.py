"""KiCad node worker — registers KiCad nodes with the Node Engine."""

from __future__ import annotations

from typing import Any

from mascarade.mcp import McpRuntimeClient
from mascarade.node_engine.worker import NodeWorker, WorkerCapabilities
from mascarade.observability import new_run_id


class KiCadWorker(NodeWorker):
    """Worker for KiCad PCB design operations.

    Provides graph-composable nodes for KiCad schematic creation, PCB layout optimization,
    footprint generation, DRC checks, and manufacturing file generation. Integrates with
    the existing KiCadAgent and api/src/routes/cad.ts endpoints.
    """

    domain = "cad"
    name = "kicad"
    version = "1.0.0"

    capabilities = WorkerCapabilities(
        max_concurrent=3,  # KiCad operations are typically lighter than 3D CAD
        timeout_default_s=180,  # Longer timeout for complex PCB operations
        requires_runtime=True,
        runtime_check_endpoint="/cad/kicad/runtime",
    )

    node_types = [
        "cad.kicad.generate_schematic",
        "cad.kicad.optimize_layout",
        "cad.kicad.generate_footprint",
        "cad.kicad.perform_drc",
        "cad.kicad.generate_manufacturing_files",
    ]

    async def execute_node(
        self,
        node_type: str,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute a KiCad node by delegating to the MCP client.

        Args:
            node_type: The node type ID (e.g., "cad.kicad.generate_schematic")
            inputs: Input values for the node
            mcp_client: MCP runtime client for calling KiCad endpoints

        Returns:
            Dictionary of output values

        Raises:
            ValueError: If node_type is not supported by this worker
        """
        if node_type == "cad.kicad.generate_schematic":
            return await self._execute_generate_schematic(inputs, mcp_client)
        elif node_type == "cad.kicad.optimize_layout":
            return await self._execute_optimize_layout(inputs, mcp_client)
        elif node_type == "cad.kicad.generate_footprint":
            return await self._execute_generate_footprint(inputs, mcp_client)
        elif node_type == "cad.kicad.perform_drc":
            return await self._execute_perform_drc(inputs, mcp_client)
        elif node_type == "cad.kicad.generate_manufacturing_files":
            return await self._execute_generate_manufacturing_files(inputs, mcp_client)
        else:
            raise ValueError(f"Unsupported node type: {node_type}")

    async def _execute_generate_schematic(
        self,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute cad.kicad.generate_schematic node.

        Inputs:
            - requirements: string (schematic requirements and specifications)
            - project_name: optional string (project name, defaults to "KiCadProject")
            - include_power: optional boolean (include power flags and symbols, defaults to True)

        Outputs:
            - schematic: PCBSchematic (generated schematic with components and nets)
            - design_notes: string (explanation of design choices)

        Args:
            inputs: Node inputs
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'schematic' and 'design_notes' keys
        """
        requirements = inputs.get("requirements", "")
        project_name = inputs.get("project_name", "KiCadProject")
        include_power = inputs.get("include_power", True)

        if not requirements:
            raise ValueError("requirements is required for generate_schematic node")

        # Generate schematic using KiCad agent via MCP
        result = await mcp_client.kicad_generate_schematic(
            requirements=requirements,
            project_name=project_name,
            include_power=include_power,
            run_id=new_run_id(),
            mode="kicad",
            step=0,
            agent_name="kicad",
        )

        schematic = {
            "project_id": result.get("project_id", project_name),
            "components": result.get("components", []),
            "nets": result.get("nets", []),
            "power_symbols": result.get("power_symbols", []) if include_power else [],
            "schematic_path": result.get("schematic_path", ""),
        }

        design_notes = result.get("design_notes", result.get("explanation", ""))

        return {
            "schematic": schematic,
            "design_notes": design_notes,
        }

    async def _execute_optimize_layout(
        self,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute cad.kicad.optimize_layout node.

        Inputs:
            - schematic: PCBSchematic (input schematic)
            - constraints: string (layout constraints and requirements)
            - board_size: optional map<string, number> (width, height in mm)
            - layer_count: optional number (number of PCB layers, defaults to 2)

        Outputs:
            - layout: PCBLayout (optimized PCB layout)
            - optimization_report: string (detailed optimization recommendations)

        Args:
            inputs: Node inputs
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'layout' and 'optimization_report' keys
        """
        schematic = inputs.get("schematic", {})
        constraints = inputs.get("constraints", "")
        board_size = inputs.get("board_size", {"width": 100.0, "height": 80.0})
        layer_count = inputs.get("layer_count", 2)

        if not schematic:
            raise ValueError("schematic is required for optimize_layout node")

        if not constraints:
            raise ValueError("constraints is required for optimize_layout node")

        # Optimize layout using KiCad agent via MCP
        result = await mcp_client.kicad_optimize_layout(
            schematic=schematic,
            constraints=constraints,
            board_width=board_size.get("width", 100.0),
            board_height=board_size.get("height", 80.0),
            layer_count=layer_count,
            run_id=new_run_id(),
            mode="kicad",
            step=0,
            agent_name="kicad",
        )

        layout = {
            "board_id": result.get("board_id", schematic.get("project_id", "")),
            "components": result.get("components", []),
            "traces": result.get("traces", []),
            "vias": result.get("vias", []),
            "board_outline": result.get("board_outline", board_size),
            "layer_count": layer_count,
            "layout_path": result.get("layout_path", ""),
        }

        optimization_report = result.get(
            "optimization_report",
            result.get("recommendations", ""),
        )

        return {
            "layout": layout,
            "optimization_report": optimization_report,
        }

    async def _execute_generate_footprint(
        self,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute cad.kicad.generate_footprint node.

        Inputs:
            - component_description: string (component specifications and requirements)
            - package_type: string (package type: "DIP", "SMD", "QFP", "BGA", etc.)
            - pin_count: number (number of pins/pads)
            - pitch: optional number (pin pitch in mm)

        Outputs:
            - footprint: ComponentFootprint (generated footprint)
            - footprint_library: string (footprint library path)

        Args:
            inputs: Node inputs
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'footprint' and 'footprint_library' keys
        """
        component_description = inputs.get("component_description", "")
        package_type = inputs.get("package_type", "SMD")
        pin_count = inputs.get("pin_count", 0)
        pitch = inputs.get("pitch", 2.54)

        if not component_description:
            raise ValueError(
                "component_description is required for generate_footprint node"
            )

        if pin_count <= 0:
            raise ValueError("pin_count must be greater than 0")

        # Generate footprint using KiCad agent via MCP
        result = await mcp_client.kicad_generate_footprint(
            description=component_description,
            package_type=package_type,
            pin_count=pin_count,
            pitch=pitch,
            run_id=new_run_id(),
            mode="kicad",
            step=0,
            agent_name="kicad",
        )

        footprint = {
            "footprint_id": result.get("footprint_id", ""),
            "package_type": package_type,
            "pads": result.get("pads", []),
            "silkscreen": result.get("silkscreen", {}),
            "courtyard": result.get("courtyard", {}),
            "model_3d": result.get("model_3d", ""),
            "pin_count": pin_count,
            "pitch": pitch,
        }

        footprint_library = result.get("library_path", "")

        return {
            "footprint": footprint,
            "footprint_library": footprint_library,
        }

    async def _execute_perform_drc(
        self,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute cad.kicad.perform_drc node.

        Inputs:
            - layout: PCBLayout (PCB layout to check)
            - design_rules: string (design rules and constraints)
            - check_clearance: optional boolean (check clearance violations, defaults to True)
            - check_tracks: optional boolean (check track width compliance, defaults to True)

        Outputs:
            - drc_report: DRCReport (design rule check results)
            - violations: list<DRCViolation> (list of violations found)
            - passed: boolean (whether the design passed DRC)

        Args:
            inputs: Node inputs
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'drc_report', 'violations', and 'passed' keys
        """
        layout = inputs.get("layout", {})
        design_rules = inputs.get("design_rules", "")
        check_clearance = inputs.get("check_clearance", True)
        check_tracks = inputs.get("check_tracks", True)

        if not layout:
            raise ValueError("layout is required for perform_drc node")

        if not design_rules:
            raise ValueError("design_rules is required for perform_drc node")

        # Perform DRC using KiCad agent via MCP
        result = await mcp_client.kicad_perform_drc(
            layout=layout,
            design_rules=design_rules,
            check_clearance=check_clearance,
            check_tracks=check_tracks,
            run_id=new_run_id(),
            mode="kicad",
            step=0,
            agent_name="kicad",
        )

        violations = result.get("violations", [])
        passed = len(violations) == 0 or result.get("passed", False)

        drc_report = {
            "board_id": layout.get("board_id", ""),
            "timestamp": result.get("timestamp", ""),
            "rules_checked": result.get("rules_checked", []),
            "violation_count": len(violations),
            "warning_count": result.get("warning_count", 0),
            "passed": passed,
        }

        return {
            "drc_report": drc_report,
            "violations": violations,
            "passed": passed,
        }

    async def _execute_generate_manufacturing_files(
        self,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute cad.kicad.generate_manufacturing_files node.

        Inputs:
            - layout: PCBLayout (finalized PCB layout)
            - output_directory: string (output directory for manufacturing files)
            - include_gerbers: optional boolean (generate Gerber files, defaults to True)
            - include_drill: optional boolean (generate drill files, defaults to True)
            - include_bom: optional boolean (generate BOM, defaults to True)
            - include_pick_place: optional boolean (generate pick-and-place, defaults to True)

        Outputs:
            - manufacturing_files: ManufacturingFiles (generated files)
            - file_list: list<string> (list of generated file paths)

        Args:
            inputs: Node inputs
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'manufacturing_files' and 'file_list' keys
        """
        layout = inputs.get("layout", {})
        output_directory = inputs.get("output_directory", "/tmp/kicad_manufacturing")
        include_gerbers = inputs.get("include_gerbers", True)
        include_drill = inputs.get("include_drill", True)
        include_bom = inputs.get("include_bom", True)
        include_pick_place = inputs.get("include_pick_place", True)

        if not layout:
            raise ValueError("layout is required for generate_manufacturing_files node")

        if not output_directory:
            raise ValueError(
                "output_directory is required for generate_manufacturing_files node"
            )

        # Generate manufacturing files using KiCad agent via MCP
        result = await mcp_client.kicad_generate_manufacturing_files(
            layout=layout,
            output_directory=output_directory,
            include_gerbers=include_gerbers,
            include_drill=include_drill,
            include_bom=include_bom,
            include_pick_place=include_pick_place,
            run_id=new_run_id(),
            mode="kicad",
            step=0,
            agent_name="kicad",
        )

        manufacturing_files = {
            "board_id": layout.get("board_id", ""),
            "output_directory": output_directory,
            "gerber_files": result.get("gerber_files", []) if include_gerbers else [],
            "drill_files": result.get("drill_files", []) if include_drill else [],
            "bom_file": result.get("bom_file", "") if include_bom else "",
            "pick_place_file": (
                result.get("pick_place_file", "") if include_pick_place else ""
            ),
            "assembly_drawings": result.get("assembly_drawings", []),
        }

        file_list = result.get("file_list", [])

        return {
            "manufacturing_files": manufacturing_files,
            "file_list": file_list,
        }
