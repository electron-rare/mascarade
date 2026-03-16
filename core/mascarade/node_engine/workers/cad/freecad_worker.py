"""FreeCAD node worker — registers FreeCAD nodes with the Node Engine."""

from __future__ import annotations

from typing import Any

from mascarade.mcp import McpRuntimeClient
from mascarade.node_engine.worker import NodeWorker, WorkerCapabilities
from mascarade.observability import new_run_id


class FreeCADWorker(NodeWorker):
    """Worker for FreeCAD CAD operations.

    Provides graph-composable nodes for FreeCAD document creation, script execution,
    parametric modeling, and export operations. Integrates with the existing FreeCADAgent
    and api/src/routes/cad.ts endpoints.
    """

    domain = "cad"
    name = "freecad"
    version = "1.0.0"

    capabilities = WorkerCapabilities(
        max_concurrent=2,  # FreeCAD runtime is memory-intensive
        timeout_default_s=120,
        requires_runtime=True,
        runtime_check_endpoint="/cad/freecad/runtime",
    )

    node_types = [
        "cad.freecad.create_document",
        "cad.freecad.run_script",
        "cad.freecad.parametric_model",
        "cad.freecad.export",
    ]

    async def execute_node(
        self,
        node_type: str,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute a FreeCAD node by delegating to the MCP client.

        Args:
            node_type: The node type ID (e.g., "cad.freecad.create_document")
            inputs: Input values for the node
            mcp_client: MCP runtime client for calling FreeCAD endpoints

        Returns:
            Dictionary of output values

        Raises:
            ValueError: If node_type is not supported by this worker
        """
        if node_type == "cad.freecad.create_document":
            return await self._execute_create_document(inputs, mcp_client)
        else:
            raise ValueError(f"Unsupported node type: {node_type}")

    async def _execute_create_document(
        self,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute cad.freecad.create_document node.

        Inputs:
            - name: string (document name)
            - parameters: optional map<string, number> (initial parameters)

        Outputs:
            - document: CADDocument

        Args:
            inputs: Node inputs
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'document' key containing CADDocument
        """
        name = inputs.get("name", "McpDocument")
        parameters = inputs.get("parameters", {})

        # Extract parameters with defaults
        # For now, FreeCAD MCP endpoint uses primitive box with length/width/height
        # Future: extend to support arbitrary parameters
        length = parameters.get("length", 10.0)
        width = parameters.get("width", 8.0)
        height = parameters.get("height", 6.0)

        # Generate temporary output path (will be managed by FreeCAD runtime)
        output_path = f"/tmp/freecad_doc_{name}.FCStd"

        # Call MCP client to create document
        result = await mcp_client.freecad_create_document(
            output_path,
            name=name,
            primitive="box",
            length=float(length),
            width=float(width),
            height=float(height),
            run_id=new_run_id(),
            mode="freecad",
            step=0,
            agent_name="freecad",
        )

        # Convert MCP result to CADDocument format
        # The MCP result should contain document info
        cad_document = {
            "document_id": result.get("document_id", output_path),
            "name": name,
            "objects": result.get("objects", []),
            "parameters": {
                "length": length,
                "width": width,
                "height": height,
            },
        }

        return {"document": cad_document}
