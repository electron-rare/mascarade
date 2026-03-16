"""Mesh node worker — registers mesh operation nodes with the Node Engine."""

from __future__ import annotations

from typing import Any

from mascarade.mcp import McpRuntimeClient
from mascarade.node_engine.worker import NodeWorker, WorkerCapabilities
from mascarade.observability import new_run_id


class MeshWorker(NodeWorker):
    """Worker for mesh geometry operations.

    Provides graph-composable nodes for mesh import/export, simplification,
    and boolean operations (union, intersection, difference). Serves as building
    blocks for CAD pipelines.
    """

    domain = "cad"
    name = "mesh"
    version = "1.0.0"

    capabilities = WorkerCapabilities(
        max_concurrent=4,  # Mesh operations are CPU-intensive but parallelizable
        timeout_default_s=90,
        requires_runtime=False,  # Mesh operations can run in core Python
    )

    node_types = [
        "cad.mesh.import",
        "cad.mesh.export",
        "cad.mesh.simplify",
        "cad.mesh.boolean",
    ]

    async def execute_node(
        self,
        node_type: str,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute a mesh operation node.

        Args:
            node_type: The node type ID (e.g., "cad.mesh.import")
            inputs: Input values for the node
            mcp_client: MCP runtime client for calling mesh endpoints

        Returns:
            Dictionary of output values

        Raises:
            ValueError: If node_type is not recognized
        """
        if node_type == "cad.mesh.import":
            return await self._execute_import(inputs, mcp_client)
        elif node_type == "cad.mesh.export":
            return await self._execute_export(inputs, mcp_client)
        elif node_type == "cad.mesh.simplify":
            return await self._execute_simplify(inputs, mcp_client)
        elif node_type == "cad.mesh.boolean":
            return await self._execute_boolean(inputs, mcp_client)
        else:
            raise ValueError(f"Unknown mesh node type: {node_type}")

    async def _execute_import(
        self, inputs: dict[str, Any], mcp_client: McpRuntimeClient
    ) -> dict[str, Any]:
        """Execute mesh import operation.

        Imports a mesh from file data (STL, OBJ, PLY).

        Args:
            inputs: Must contain 'data' (binary) and 'format' (string)
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'mesh' (MeshData) and 'stats' (json)
        """
        run_id = new_run_id()
        response = await mcp_client.mesh_import(
            data=inputs["data"], format=inputs["format"], run_id=run_id
        )
        return {"mesh": response["mesh"], "stats": response["stats"]}

    async def _execute_export(
        self, inputs: dict[str, Any], mcp_client: McpRuntimeClient
    ) -> dict[str, Any]:
        """Execute mesh export operation.

        Exports a mesh to a target format.

        Args:
            inputs: Must contain 'mesh' (MeshData) and 'format' (string),
                   optional 'options' (json)
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'data' (binary) and 'result' (ExportResult)
        """
        run_id = new_run_id()
        response = await mcp_client.mesh_export(
            mesh=inputs["mesh"],
            format=inputs["format"],
            options=inputs.get("options"),
            run_id=run_id,
        )
        return {"data": response["data"], "result": response["result"]}

    async def _execute_simplify(
        self, inputs: dict[str, Any], mcp_client: McpRuntimeClient
    ) -> dict[str, Any]:
        """Execute mesh simplification operation.

        Reduces mesh complexity while preserving shape fidelity.

        Args:
            inputs: Must contain 'mesh' (MeshData) and 'target_ratio' (number),
                   optional 'preserve_boundaries' (boolean)
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'mesh' (MeshData) and 'reduction_pct' (number)
        """
        run_id = new_run_id()
        response = await mcp_client.mesh_simplify(
            mesh=inputs["mesh"],
            target_ratio=inputs["target_ratio"],
            preserve_boundaries=inputs.get("preserve_boundaries", True),
            run_id=run_id,
        )
        return {"mesh": response["mesh"], "reduction_pct": response["reduction_pct"]}

    async def _execute_boolean(
        self, inputs: dict[str, Any], mcp_client: McpRuntimeClient
    ) -> dict[str, Any]:
        """Execute mesh boolean operation.

        Performs boolean operations (union, intersection, difference) on two meshes.

        Args:
            inputs: Must contain 'mesh_a' (MeshData), 'mesh_b' (MeshData),
                   and 'operation' (string: 'union', 'intersection', 'difference')
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'mesh' (MeshData)
        """
        run_id = new_run_id()
        response = await mcp_client.mesh_boolean(
            mesh_a=inputs["mesh_a"],
            mesh_b=inputs["mesh_b"],
            operation=inputs["operation"],
            run_id=run_id,
        )
        return {"mesh": response["mesh"]}
