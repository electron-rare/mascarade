"""Toolpath node worker — registers toolpath generation nodes with the Node Engine."""

from __future__ import annotations

from typing import Any

from mascarade.mcp import McpRuntimeClient
from mascarade.node_engine.worker import NodeWorker, WorkerCapabilities


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
        # Extract tool parameters
        tool_diameter = tool.get("diameter", 6.0)
        tool.get("flute_count", 2)
        tool_material = tool.get("material", "carbide")

        # Calculate bounds from mesh or stock
        bounds = self._calculate_bounds(mesh, stock)

        # Generate strategy-specific toolpath moves
        moves = self._generate_strategy_moves(strategy, bounds, tool_diameter)

        # Calculate feed rates based on tool and material
        feed_rate = self._calculate_feed_rate(tool_diameter, tool_material, strategy)
        rapid_rate = feed_rate * 3.0  # Rapid moves are typically 3x feed rate
        spindle_speed = self._calculate_spindle_speed(tool_diameter, tool_material)

        # Update moves with calculated feed rates
        for move in moves:
            if move["type"] == "rapid":
                move["feed_rate"] = rapid_rate
            else:
                move["feed_rate"] = feed_rate

        # Calculate estimated machining time
        estimated_time_s = self._calculate_machining_time(moves)

        # Generate G-code program
        gcode_program = self._generate_gcode_program(
            strategy, moves, tool_diameter, spindle_speed, bounds
        )

        return {
            "program": gcode_program,
            "estimated_time_s": estimated_time_s,
            "bounds": bounds,
            "tool_changes": 1,
            "moves": moves,
            "unit": "mm",
        }

    def _calculate_bounds(self, mesh: dict[str, Any], stock: dict[str, Any]) -> dict[str, float]:
        """Calculate bounding box from mesh or stock dimensions."""
        if stock:
            return {
                "x": stock.get("width", 100.0),
                "y": stock.get("depth", 100.0),
                "z": stock.get("height", 50.0),
            }

        # Calculate from mesh vertices if available
        vertices = mesh.get("vertices", [])
        if vertices:
            xs = [v[0] for v in vertices]
            ys = [v[1] for v in vertices]
            zs = [v[2] for v in vertices]
            return {
                "x": max(xs) - min(xs) if xs else 100.0,
                "y": max(ys) - min(ys) if ys else 100.0,
                "z": max(zs) - min(zs) if zs else 50.0,
            }

        # Default bounds
        return {"x": 100.0, "y": 100.0, "z": 50.0}

    def _generate_strategy_moves(
        self, strategy: str, bounds: dict[str, float], tool_diameter: float
    ) -> list[dict[str, Any]]:
        """Generate toolpath moves based on machining strategy."""
        moves = []
        safe_z = 5.0  # Safe Z height above workpiece

        if strategy == "adaptive":
            # Adaptive clearing with spiral pattern
            moves.append({"x": 0.0, "y": 0.0, "z": safe_z, "type": "rapid"})

            stepover = tool_diameter * 0.5  # 50% stepover
            num_passes = int(bounds["x"] / stepover)

            for i in range(num_passes):
                x = i * stepover
                moves.append({"x": x, "y": 0.0, "z": 0.0, "type": "linear"})
                moves.append({"x": x, "y": bounds["y"], "z": 0.0, "type": "linear"})
                moves.append({"x": x, "y": bounds["y"], "z": safe_z, "type": "rapid"})

        elif strategy == "contour":
            # Contour following with offset passes
            moves.append({"x": 0.0, "y": 0.0, "z": safe_z, "type": "rapid"})

            offset = tool_diameter * 0.5
            num_contours = 3

            for i in range(num_contours):
                inset = i * offset
                moves.append({"x": inset, "y": inset, "z": 0.0, "type": "linear"})
                moves.append({"x": bounds["x"] - inset, "y": inset, "z": 0.0, "type": "linear"})
                moves.append(
                    {
                        "x": bounds["x"] - inset,
                        "y": bounds["y"] - inset,
                        "z": 0.0,
                        "type": "linear",
                    }
                )
                moves.append({"x": inset, "y": bounds["y"] - inset, "z": 0.0, "type": "linear"})
                moves.append({"x": inset, "y": inset, "z": 0.0, "type": "linear"})

        elif strategy == "pocket":
            # Pocket clearing with zigzag pattern
            moves.append({"x": 0.0, "y": 0.0, "z": safe_z, "type": "rapid"})

            stepover = tool_diameter * 0.6
            num_passes = int(bounds["y"] / stepover)

            for i in range(num_passes):
                y = i * stepover
                if i % 2 == 0:
                    moves.append({"x": 0.0, "y": y, "z": 0.0, "type": "linear"})
                    moves.append({"x": bounds["x"], "y": y, "z": 0.0, "type": "linear"})
                else:
                    moves.append({"x": bounds["x"], "y": y, "z": 0.0, "type": "linear"})
                    moves.append({"x": 0.0, "y": y, "z": 0.0, "type": "linear"})

        elif strategy == "drill":
            # Drilling pattern at grid points
            grid_spacing = 10.0
            moves.append({"x": 0.0, "y": 0.0, "z": safe_z, "type": "rapid"})

            x_points = int(bounds["x"] / grid_spacing)
            y_points = int(bounds["y"] / grid_spacing)

            for i in range(x_points):
                for j in range(y_points):
                    x = i * grid_spacing
                    y = j * grid_spacing
                    moves.append({"x": x, "y": y, "z": safe_z, "type": "rapid"})
                    moves.append({"x": x, "y": y, "z": -bounds["z"], "type": "linear"})
                    moves.append({"x": x, "y": y, "z": safe_z, "type": "rapid"})

        elif strategy == "facing":
            # Face milling with back-and-forth passes
            moves.append({"x": 0.0, "y": 0.0, "z": safe_z, "type": "rapid"})

            stepover = tool_diameter * 0.75
            num_passes = int(bounds["x"] / stepover)

            for i in range(num_passes):
                x = i * stepover
                if i % 2 == 0:
                    moves.append({"x": x, "y": 0.0, "z": 0.0, "type": "linear"})
                    moves.append({"x": x, "y": bounds["y"], "z": 0.0, "type": "linear"})
                else:
                    moves.append({"x": x, "y": bounds["y"], "z": 0.0, "type": "linear"})
                    moves.append({"x": x, "y": 0.0, "z": 0.0, "type": "linear"})

        # Return to safe position
        moves.append({"x": 0.0, "y": 0.0, "z": safe_z, "type": "rapid"})

        return moves

    def _calculate_feed_rate(
        self, tool_diameter: float, tool_material: str, strategy: str
    ) -> float:
        """Calculate appropriate feed rate based on tool and strategy."""
        # Base feed rate (mm/min) for different materials
        base_rates = {
            "carbide": 1000.0,
            "hss": 500.0,
            "diamond": 1500.0,
        }

        base_rate = base_rates.get(tool_material, 800.0)

        # Strategy modifiers
        strategy_factors = {
            "adaptive": 1.0,
            "contour": 0.8,
            "pocket": 0.9,
            "drill": 0.5,
            "facing": 1.2,
        }

        factor = strategy_factors.get(strategy, 1.0)

        # Tool diameter factor (larger tools can feed faster)
        diameter_factor = (tool_diameter / 6.0) ** 0.5

        return base_rate * factor * diameter_factor

    def _calculate_spindle_speed(self, tool_diameter: float, tool_material: str) -> int:
        """Calculate appropriate spindle speed (RPM) based on tool."""
        # Cutting speed in m/min
        cutting_speeds = {
            "carbide": 200.0,
            "hss": 100.0,
            "diamond": 300.0,
        }

        cutting_speed = cutting_speeds.get(tool_material, 150.0)

        # Calculate RPM: (cutting_speed * 1000) / (pi * diameter)
        import math

        rpm = (cutting_speed * 1000.0) / (math.pi * tool_diameter)

        # Clamp to reasonable range
        return int(max(1000, min(24000, rpm)))

    def _calculate_machining_time(self, moves: list[dict[str, Any]]) -> float:
        """Calculate estimated machining time from moves."""
        total_time = 0.0

        for i, move in enumerate(moves):
            if i == 0:
                continue

            prev = moves[i - 1]

            # Calculate distance
            dx = move["x"] - prev["x"]
            dy = move["y"] - prev["y"]
            dz = move.get("z", 0.0) - prev.get("z", 0.0)

            import math

            distance = math.sqrt(dx**2 + dy**2 + dz**2)

            # Calculate time (distance / feed_rate, convert mm/min to mm/s)
            feed_rate = move.get("feed_rate", 100.0)
            if feed_rate > 0:
                total_time += (distance / feed_rate) * 60.0

        # Add tool change time and setup overhead
        total_time += 30.0  # 30 seconds overhead

        return total_time

    def _generate_gcode_program(
        self,
        strategy: str,
        moves: list[dict[str, Any]],
        tool_diameter: float,
        spindle_speed: int,
        bounds: dict[str, float],
    ) -> str:
        """Generate G-code program from toolpath moves."""
        lines = [
            f"; G-code generated with {strategy} strategy",
            f"; Tool diameter: {tool_diameter}mm",
            f"; Bounding box: X{bounds['x']:.1f} Y{bounds['y']:.1f} Z{bounds['z']:.1f}",
            "",
            "G21 ; Set units to millimeters",
            "G90 ; Absolute positioning",
            "G17 ; XY plane selection",
            "",
            f"M3 S{spindle_speed} ; Start spindle at {spindle_speed} RPM",
            "G4 P2 ; Dwell 2 seconds for spindle ramp-up",
            "",
        ]

        # Generate move commands
        for move in moves:
            x = move["x"]
            y = move["y"]
            z = move.get("z", 0.0)
            feed_rate = move.get("feed_rate", 100.0)
            move_type = move["type"]

            if move_type == "rapid":
                lines.append(f"G0 X{x:.3f} Y{y:.3f} Z{z:.3f}")
            elif move_type == "linear":
                lines.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feed_rate:.0f}")
            elif move_type == "arc_cw":
                # Placeholder for arc moves
                lines.append(f"G2 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feed_rate:.0f}")
            elif move_type == "arc_ccw":
                lines.append(f"G3 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feed_rate:.0f}")

        # Program end
        lines.extend(
            [
                "",
                "M5 ; Stop spindle",
                "G0 Z50 ; Retract to safe height",
                "M30 ; End program and reset",
            ]
        )

        return "\n".join(lines)

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
        moves = toolpath.get("moves", [])
        tool_id = toolpath.get("tool_id", "tool_0")
        toolpath.get("unit", "mm")

        if not moves:
            raise ValueError("Toolpath has no moves to optimize")

        # Calculate original metrics
        original_time = self._calculate_machining_time(moves)
        sum(1 for m in moves if m.get("type") == "rapid")

        # Apply objective-specific optimization
        if objective == "time":
            optimized_moves = self._optimize_for_time(moves, constraints)
        elif objective == "finish":
            optimized_moves = self._optimize_for_finish(moves, constraints)
        elif objective == "tool_life":
            optimized_moves = self._optimize_for_tool_life(moves, constraints)
        else:
            optimized_moves = moves

        # Calculate optimized metrics
        optimized_time = self._calculate_machining_time(optimized_moves)
        sum(1 for m in optimized_moves if m.get("type") == "rapid")

        # Calculate improvement percentage based on objective
        if objective == "time":
            improvement_pct = ((original_time - optimized_time) / original_time) * 100
        elif objective == "finish":
            # For finish, improvement is based on feed rate reduction and move smoothness
            avg_original_feed = sum(
                m.get("feed_rate", 0) for m in moves if m.get("type") != "rapid"
            ) / max(1, len([m for m in moves if m.get("type") != "rapid"]))
            avg_optimized_feed = sum(
                m.get("feed_rate", 0) for m in optimized_moves if m.get("type") != "rapid"
            ) / max(1, len([m for m in optimized_moves if m.get("type") != "rapid"]))
            improvement_pct = ((avg_original_feed - avg_optimized_feed) / avg_original_feed) * 100
        elif objective == "tool_life":
            # For tool life, improvement is based on reduced peak loads
            max_original_feed = max(
                (m.get("feed_rate", 0) for m in moves if m.get("type") != "rapid"),
                default=0,
            )
            max_optimized_feed = max(
                (m.get("feed_rate", 0) for m in optimized_moves if m.get("type") != "rapid"),
                default=0,
            )
            improvement_pct = (
                ((max_original_feed - max_optimized_feed) / max_original_feed) * 100
                if max_original_feed > 0
                else 0
            )
        else:
            improvement_pct = 0.0

        # Calculate bounds from moves
        bounds = self._calculate_bounds_from_moves(optimized_moves)

        # Generate optimized G-code
        gcode_program = self._generate_optimized_gcode(objective, optimized_moves, tool_id, bounds)

        return {
            "program": gcode_program,
            "estimated_time_s": optimized_time,
            "bounds": bounds,
            "tool_changes": 1,
            "moves": optimized_moves,
            "improvement_pct": improvement_pct,
        }

    def _optimize_for_time(
        self, moves: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Optimize toolpath for minimum machining time."""
        optimized = []
        max_feed_rate = constraints.get("max_feed_rate", 2000.0)

        for i, move in enumerate(moves):
            optimized_move = move.copy()

            # Increase feed rates for non-rapid moves (within constraints)
            if move.get("type") != "rapid":
                current_feed = move.get("feed_rate", 100.0)
                optimized_move["feed_rate"] = min(current_feed * 1.25, max_feed_rate)

            # Consolidate consecutive rapid moves
            if (
                i > 0
                and move.get("type") == "rapid"
                and optimized
                and optimized[-1].get("type") == "rapid"
            ):
                # Skip intermediate rapid moves
                optimized[-1] = optimized_move
                continue

            optimized.append(optimized_move)

        return optimized

    def _optimize_for_finish(
        self, moves: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Optimize toolpath for best surface finish."""
        optimized = []
        target_feed_rate = constraints.get("finish_feed_rate", 300.0)

        for move in moves:
            optimized_move = move.copy()

            # Reduce feed rates for cutting moves to improve finish
            if move.get("type") != "rapid":
                optimized_move["feed_rate"] = min(
                    move.get("feed_rate", 500.0) * 0.7, target_feed_rate
                )

            optimized.append(optimized_move)

        # Add interpolation points for smoother paths
        smoothed = []
        for i, move in enumerate(optimized):
            smoothed.append(move)

            # Add intermediate points between cutting moves
            if i < len(optimized) - 1 and move.get("type") != "rapid":
                next_move = optimized[i + 1]
                if next_move.get("type") != "rapid":
                    # Add midpoint for smoother transition
                    midpoint = {
                        "x": (move["x"] + next_move["x"]) / 2,
                        "y": (move["y"] + next_move["y"]) / 2,
                        "z": (move.get("z", 0) + next_move.get("z", 0)) / 2,
                        "feed_rate": move["feed_rate"],
                        "type": "linear",
                    }
                    smoothed.append(midpoint)

        return smoothed

    def _optimize_for_tool_life(
        self, moves: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Optimize toolpath to extend tool life."""
        optimized = []
        conservative_feed_rate = constraints.get("conservative_feed_rate", 400.0)

        for move in moves:
            optimized_move = move.copy()

            # Reduce feed rates to decrease tool wear
            if move.get("type") != "rapid":
                optimized_move["feed_rate"] = min(
                    move.get("feed_rate", 800.0) * 0.75, conservative_feed_rate
                )

            # Add climb milling preference (reverse direction for some passes)
            # This is a simplified representation
            if move.get("type") == "linear":
                optimized_move["climb_milling"] = True

            optimized.append(optimized_move)

        return optimized

    def _calculate_bounds_from_moves(self, moves: list[dict[str, Any]]) -> dict[str, float]:
        """Calculate bounding box from toolpath moves."""
        if not moves:
            return {"x": 0.0, "y": 0.0, "z": 0.0}

        xs = [m["x"] for m in moves]
        ys = [m["y"] for m in moves]
        zs = [m.get("z", 0.0) for m in moves]

        return {
            "x": max(xs) - min(xs) if xs else 0.0,
            "y": max(ys) - min(ys) if ys else 0.0,
            "z": max(zs) - min(zs) if zs else 0.0,
        }

    def _generate_optimized_gcode(
        self,
        objective: str,
        moves: list[dict[str, Any]],
        tool_id: str,
        bounds: dict[str, float],
    ) -> str:
        """Generate G-code program for optimized toolpath."""
        lines = [
            f"; G-code optimized for {objective}",
            f"; Tool ID: {tool_id}",
            f"; Bounding box: X{bounds['x']:.1f} Y{bounds['y']:.1f} Z{bounds['z']:.1f}",
            f"; Total moves: {len(moves)}",
            "",
            "G21 ; Set units to millimeters",
            "G90 ; Absolute positioning",
            "G17 ; XY plane selection",
            "",
        ]

        # Add objective-specific G-code settings
        if objective == "time":
            lines.append("; Optimized for minimum cycle time")
            lines.append("G64 P0.05 ; Continuous path mode with 0.05mm tolerance")
        elif objective == "finish":
            lines.append("; Optimized for surface finish")
            lines.append("G61 ; Exact path mode for best finish")
        elif objective == "tool_life":
            lines.append("; Optimized for tool longevity")
            lines.append("G64 P0.1 ; Balanced path mode")

        lines.extend(
            [
                "M3 S12000 ; Start spindle",
                "G4 P2 ; Dwell 2 seconds",
                "",
            ]
        )

        # Generate move commands
        for move in moves:
            x = move["x"]
            y = move["y"]
            z = move.get("z", 0.0)
            feed_rate = move.get("feed_rate", 100.0)
            move_type = move["type"]

            if move_type == "rapid":
                lines.append(f"G0 X{x:.3f} Y{y:.3f} Z{z:.3f}")
            elif move_type == "linear":
                lines.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feed_rate:.0f}")

        # Program end
        lines.extend(
            [
                "",
                "M5 ; Stop spindle",
                "G0 Z50 ; Retract",
                "M30 ; End program",
            ]
        )

        return "\n".join(lines)
