"""Toolpath node worker — registers toolpath generation nodes with the Node Engine."""

from __future__ import annotations

from typing import Any

from mascarade.mcp import McpRuntimeClient
from mascarade.node_engine.worker import NodeWorker, WorkerCapabilities
from mascarade.observability import new_run_id


class ToolpathWorker(NodeWorker):
    """Worker for toolpath generation and CNC operations.

    Provides graph-composable nodes for G-code generation from mesh geometry
    and toolpath optimization for reduced machining time or improved surface finish.
    Integrates with CNC machining workflows.
    """

    domain = "cad"
    name = "toolpath"
    version = "1.0.0"

    capabilities = WorkerCapabilities(
        max_concurrent=4,  # Toolpath operations are CPU-intensive but parallelizable
        timeout_default_s=180,
        requires_runtime=False,  # Toolpath generation can run in core Python
    )

    node_types = [
        "cad.toolpath.generate_gcode",
        "cad.toolpath.optimize",
    ]

    async def execute_node(
        self,
        node_type: str,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute a toolpath node.

        Args:
            node_type: The node type ID (e.g., "cad.toolpath.generate_gcode")
            inputs: Input values for the node
            mcp_client: MCP runtime client for calling toolpath endpoints

        Returns:
            Dictionary of output values

        Raises:
            ValueError: If node_type is not supported by this worker
        """
        if node_type == "cad.toolpath.generate_gcode":
            return await self._execute_generate_gcode(inputs, mcp_client)
        elif node_type == "cad.toolpath.optimize":
            return await self._execute_optimize(inputs, mcp_client)
        else:
            raise ValueError(f"Unsupported node type: {node_type}")

    async def _execute_generate_gcode(
        self,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute cad.toolpath.generate_gcode node.

        Inputs:
            - mesh: MeshData (3D geometry to machine)
            - tool: json (tool geometry: diameter, flute_count, material)
            - strategy: string (machining strategy: "adaptive", "contour", "pocket", "drill", "facing")
            - stock: optional json (raw material dimensions)

        Outputs:
            - gcode: GCode (generated G-code program)
            - toolpath: Toolpath (structured toolpath for visualization)

        Args:
            inputs: Node inputs
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'gcode' and 'toolpath' keys
        """
        mesh = inputs.get("mesh", {})
        tool = inputs.get("tool", {})
        strategy = inputs.get("strategy", "adaptive")
        stock = inputs.get("stock", {})

        if not mesh:
            raise ValueError("mesh is required for generate_gcode node")

        if not tool:
            raise ValueError("tool is required for generate_gcode node")

        # Validate strategy
        valid_strategies = ["adaptive", "contour", "pocket", "drill", "facing"]
        if strategy not in valid_strategies:
            raise ValueError(
                f"Invalid strategy '{strategy}'. Must be one of: {', '.join(valid_strategies)}"
            )

        # Generate G-code from mesh using toolpath generation service
        # For now, this is a placeholder that would integrate with a real CAM library
        # (e.g., OpenCAMLib, PyCAM, or a custom toolpath generator)
        result = await self._generate_toolpath(
            mesh=mesh,
            tool=tool,
            strategy=strategy,
            stock=stock,
            mcp_client=mcp_client,
        )

        gcode = {
            "program": result.get("program", ""),
            "estimated_time_s": result.get("estimated_time_s", 0),
            "bounds": result.get("bounds", {"x": 0, "y": 0, "z": 0}),
            "tool_changes": result.get("tool_changes", 1),
        }

        toolpath = {
            "moves": result.get("moves", []),
            "unit": result.get("unit", "mm"),
            "tool_id": tool.get("id", "tool_0"),
        }

        return {
            "gcode": gcode,
            "toolpath": toolpath,
        }

    async def _execute_optimize(
        self,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute cad.toolpath.optimize node.

        Inputs:
            - toolpath: Toolpath (toolpath to optimize)
            - objective: string (optimization objective: "time", "finish", "tool_life")
            - constraints: optional json (optimization constraints)

        Outputs:
            - toolpath: Toolpath (optimized toolpath)
            - gcode: GCode (optimized G-code)
            - improvement_pct: number (percentage improvement over input)

        Args:
            inputs: Node inputs
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'toolpath', 'gcode', and 'improvement_pct' keys
        """
        toolpath = inputs.get("toolpath", {})
        objective = inputs.get("objective", "time")
        constraints = inputs.get("constraints", {})

        if not toolpath:
            raise ValueError("toolpath is required for optimize node")

        # Validate objective
        valid_objectives = ["time", "finish", "tool_life"]
        if objective not in valid_objectives:
            raise ValueError(
                f"Invalid objective '{objective}'. Must be one of: {', '.join(valid_objectives)}"
            )

        # Optimize the toolpath
        # For now, this is a placeholder that would integrate with optimization algorithms
        # (e.g., feed rate optimization, rapid move consolidation, path reordering)
        result = await self._optimize_toolpath(
            toolpath=toolpath,
            objective=objective,
            constraints=constraints,
            mcp_client=mcp_client,
        )

        optimized_toolpath = {
            "moves": result.get("moves", toolpath.get("moves", [])),
            "unit": toolpath.get("unit", "mm"),
            "tool_id": toolpath.get("tool_id", "tool_0"),
        }

        optimized_gcode = {
            "program": result.get("program", ""),
            "estimated_time_s": result.get("estimated_time_s", 0),
            "bounds": result.get("bounds", {"x": 0, "y": 0, "z": 0}),
            "tool_changes": result.get("tool_changes", 1),
        }

        improvement_pct = result.get("improvement_pct", 0.0)

        return {
            "toolpath": optimized_toolpath,
            "gcode": optimized_gcode,
            "improvement_pct": improvement_pct,
        }

    async def _generate_toolpath(
        self,
        mesh: dict[str, Any],
        tool: dict[str, Any],
        strategy: str,
        stock: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Generate toolpath from mesh using specified strategy.

        This is a placeholder for integration with real CAM libraries.
        In production, this would call OpenCAMLib, PyCAM, or similar.

        Args:
            mesh: MeshData dictionary
            tool: Tool specification
            strategy: Machining strategy
            stock: Stock material dimensions
            mcp_client: MCP runtime client

        Returns:
            Dictionary with toolpath generation results
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Parse mesh vertices and faces
        # 2. Apply the selected machining strategy
        # 3. Generate tool movements considering tool geometry
        # 4. Calculate feed rates and spindle speeds
        # 5. Generate G-code program

        # For now, return a minimal valid structure
        return {
            "program": f"; Generated with strategy: {strategy}\nG21 ; metric\nM2 ; end program",
            "estimated_time_s": 60.0,
            "bounds": {"x": 100.0, "y": 100.0, "z": 50.0},
            "tool_changes": 1,
            "moves": [
                {"x": 0.0, "y": 0.0, "z": 10.0, "feed_rate": 100.0, "type": "rapid"},
                {"x": 50.0, "y": 50.0, "z": 0.0, "feed_rate": 50.0, "type": "linear"},
            ],
            "unit": "mm",
        }

    async def _optimize_toolpath(
        self,
        toolpath: dict[str, Any],
        objective: str,
        constraints: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Optimize toolpath for the given objective.

        This is a placeholder for integration with optimization algorithms.

        Args:
            toolpath: Toolpath dictionary to optimize
            objective: Optimization objective (time/finish/tool_life)
            constraints: Optimization constraints
            mcp_client: MCP runtime client

        Returns:
            Dictionary with optimization results
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Analyze the toolpath moves
        # 2. Apply optimization based on objective:
        #    - time: feed rate optimization, rapid move consolidation
        #    - finish: optimize stepover, adjust feeds for surface quality
        #    - tool_life: balance feeds/speeds for reduced tool wear
        # 3. Reorder moves if beneficial
        # 4. Generate optimized G-code

        moves = toolpath.get("moves", [])
        original_time = len(moves) * 10.0  # Placeholder calculation

        # For now, return a minimal optimization result
        optimized_time = original_time * 0.85  # 15% improvement
        improvement_pct = ((original_time - optimized_time) / original_time) * 100

        return {
            "program": f"; Optimized for {objective}\nG21 ; metric\nM2 ; end program",
            "estimated_time_s": optimized_time,
            "bounds": {"x": 100.0, "y": 100.0, "z": 50.0},
            "tool_changes": 1,
            "moves": moves,
            "improvement_pct": improvement_pct,
        }
