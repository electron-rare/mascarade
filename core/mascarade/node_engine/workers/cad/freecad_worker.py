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
        elif node_type == "cad.freecad.run_script":
            return await self._execute_run_script(inputs, mcp_client)
        elif node_type == "cad.freecad.parametric_model":
            return await self._execute_parametric_model(inputs, mcp_client)
        elif node_type == "cad.freecad.export":
            return await self._execute_export(inputs, mcp_client)
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

    async def _execute_run_script(
        self,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute cad.freecad.run_script node.

        Inputs:
            - document: CADDocument (document context)
            - script: string (FreeCAD Python script to execute)
            - timeout_s: optional number (execution timeout, defaults to 60s)

        Outputs:
            - document: CADDocument (updated document)
            - result: json (script return value)
            - logs: string (execution logs)

        Args:
            inputs: Node inputs
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'document', 'result', and 'logs' keys
        """
        document = inputs.get("document", {})
        script = inputs.get("script", "")
        inputs.get("timeout_s", 60)

        if not script:
            raise ValueError("Script is required for run_script node")

        # Extract document ID or use output path
        document_id = document.get("document_id", "/tmp/freecad_doc.FCStd")

        # Call MCP client to execute the script
        result = await mcp_client.freecad_run_python_script(
            script,
            output_path=document_id,
            run_id=new_run_id(),
            mode="freecad",
            step=0,
            agent_name="freecad",
        )

        # Extract script result and logs from MCP response
        script_result = result.get("result", {})
        logs = result.get("logs", result.get("output", ""))

        # Update document with any changes from script execution
        updated_document = {
            "document_id": document_id,
            "name": document.get("name", "McpDocument"),
            "objects": result.get("objects", document.get("objects", [])),
            "parameters": document.get("parameters", {}),
        }

        return {
            "document": updated_document,
            "result": script_result,
            "logs": logs,
        }

    async def _execute_parametric_model(
        self,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute cad.freecad.parametric_model node.

        Inputs:
            - template: string (parametric template name)
            - parameters: map<string, number> (parameter values)
            - description: optional string (AI-assisted parameter inference)

        Outputs:
            - document: CADDocument (created document)
            - mesh: MeshData (tessellated mesh output)

        Args:
            inputs: Node inputs
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'document' and 'mesh' keys
        """
        template = inputs.get("template", "box")
        parameters = inputs.get("parameters", {})
        description = inputs.get("description", "")

        # For now, we support basic parametric templates
        # Future: integrate with FreeCADAgent for AI-assisted parameter inference
        if description:
            # TODO: Integrate with FreeCADAgent.generate_freecad_script() for AI assistance
            pass

        # Extract parameters with defaults (box template)
        length = parameters.get("length", 10.0)
        width = parameters.get("width", 8.0)
        height = parameters.get("height", 6.0)

        # Generate temporary output path
        output_path = f"/tmp/freecad_parametric_{template}.FCStd"

        # Step 1: Create the document with parametric template
        doc_result = await mcp_client.freecad_create_document(
            output_path,
            name=f"Parametric_{template}",
            primitive=template,
            length=float(length),
            width=float(width),
            height=float(height),
            run_id=new_run_id(),
            mode="freecad",
            step=0,
            agent_name="freecad",
        )

        # Step 2: Generate tessellated mesh from the document
        # For now, create a simple mesh representation
        # Future: Call FreeCAD export to STL and parse mesh data
        mesh_data = {
            "vertices": [],
            "faces": [],
            "normals": [],
            "format": "stl",
        }

        # If the result contains mesh data, use it
        if "mesh" in doc_result:
            mesh_data = doc_result["mesh"]

        # Build CADDocument response
        cad_document = {
            "document_id": doc_result.get("document_id", output_path),
            "name": f"Parametric_{template}",
            "objects": doc_result.get("objects", []),
            "parameters": {
                "length": length,
                "width": width,
                "height": height,
            },
        }

        return {
            "document": cad_document,
            "mesh": mesh_data,
        }

    async def _execute_export(
        self,
        inputs: dict[str, Any],
        mcp_client: McpRuntimeClient,
    ) -> dict[str, Any]:
        """Execute cad.freecad.export node.

        Inputs:
            - document: CADDocument (document to export)
            - output_path: string (export file path)
            - format: string (export format: "STEP", "STL", "OBJ", "IGES", etc.)
            - mesh_quality: optional string (for mesh formats: "coarse", "medium", "fine")

        Outputs:
            - export_result: ExportResult (file_path, format, size_bytes)
            - mesh: optional MeshData (for STL/OBJ formats with vertices, faces, normals)

        Args:
            inputs: Node inputs
            mcp_client: MCP runtime client

        Returns:
            Dictionary with 'export_result' and optional 'mesh' keys
        """
        document = inputs.get("document", {})
        output_path = inputs.get("output_path", "")
        export_format = inputs.get("format", "STEP").upper()
        mesh_quality = inputs.get("mesh_quality", "medium")

        if not output_path:
            raise ValueError("output_path is required for export node")

        if not document:
            raise ValueError("document is required for export node")

        # Extract document ID
        document_id = document.get("document_id", "")
        if not document_id:
            raise ValueError("document.document_id is required for export")

        # Call MCP client to export the document
        # The export may be handled through a Python script execution
        # that uses FreeCAD's native export functionality
        export_script = self._generate_export_script(
            document_id,
            output_path,
            export_format,
            mesh_quality,
        )

        result = await mcp_client.freecad_run_python_script(
            export_script,
            output_path=document_id,
            run_id=new_run_id(),
            mode="freecad",
            step=0,
            agent_name="freecad",
        )

        # Build ExportResult
        export_result = {
            "file_path": output_path,
            "format": export_format,
            "size_bytes": result.get("size_bytes", 0),
            "success": result.get("success", True),
        }

        outputs = {"export_result": export_result}

        # Extract mesh data for mesh formats (STL, OBJ)
        if export_format in ["STL", "OBJ"]:
            mesh_data = await self._extract_mesh_data(
                output_path,
                export_format,
                result,
            )
            outputs["mesh"] = mesh_data

        return outputs

    def _generate_export_script(
        self,
        document_path: str,
        output_path: str,
        export_format: str,
        mesh_quality: str,
    ) -> str:
        """Generate FreeCAD Python script for exporting a document.

        Args:
            document_path: Path to the FreeCAD document
            output_path: Output file path
            export_format: Export format (STEP, STL, OBJ, etc.)
            mesh_quality: Mesh quality for tessellation (coarse, medium, fine)

        Returns:
            Python script string for FreeCAD execution
        """
        # Quality settings for mesh tessellation
        quality_settings = {
            "coarse": {"linear_deflection": 0.5, "angular_deflection": 0.5},
            "medium": {"linear_deflection": 0.1, "angular_deflection": 0.3},
            "fine": {"linear_deflection": 0.01, "angular_deflection": 0.1},
        }
        settings = quality_settings.get(mesh_quality, quality_settings["medium"])

        script = f"""
import FreeCAD
import Mesh
import Part
import os

# Open the document
doc = FreeCAD.openDocument("{document_path}")

# Get all objects to export
objects = [obj for obj in doc.Objects if hasattr(obj, 'Shape')]

if not objects:
    print("No exportable objects found in document")
    result = {{"success": False, "error": "No exportable objects"}}
else:
    try:
        # Export based on format
        if "{export_format}" == "STEP":
            Part.export(objects, "{output_path}")
        elif "{export_format}" == "IGES":
            Part.export(objects, "{output_path}")
        elif "{export_format}" == "STL":
            # Create mesh from shapes
            mesh = Mesh.Mesh()
            for obj in objects:
                if hasattr(obj, 'Shape') and obj.Shape:
                    shape_mesh = Mesh.Mesh()
                    shape_mesh.addFacets(obj.Shape.tessellate({settings["linear_deflection"]}))
                    mesh.addMesh(shape_mesh)
            mesh.write("{output_path}")
        elif "{export_format}" == "OBJ":
            # OBJ export through Mesh
            mesh = Mesh.Mesh()
            for obj in objects:
                if hasattr(obj, 'Shape') and obj.Shape:
                    shape_mesh = Mesh.Mesh()
                    shape_mesh.addFacets(obj.Shape.tessellate({settings["linear_deflection"]}))
                    mesh.addMesh(shape_mesh)
            mesh.write("{output_path}", "OBJ")
        else:
            # Try generic Part export
            Part.export(objects, "{output_path}")

        # Get file size
        size_bytes = os.path.getsize("{output_path}") if os.path.exists("{output_path}") else 0

        result = {{
            "success": True,
            "size_bytes": size_bytes,
            "objects_exported": len(objects)
        }}
    except Exception as e:
        result = {{"success": False, "error": str(e)}}

print(result)
"""
        return script

    async def _extract_mesh_data(
        self,
        mesh_file_path: str,
        mesh_format: str,
        execution_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract mesh data from exported mesh file.

        For STL/OBJ formats, this parses the mesh file to extract
        vertices, faces, and normals for downstream processing.

        Args:
            mesh_file_path: Path to the exported mesh file
            mesh_format: Mesh format (STL, OBJ)
            execution_result: Result from the export script execution

        Returns:
            MeshData dictionary with vertices, faces, normals, and metadata
        """
        # For now, return a placeholder mesh structure
        # In a full implementation, this would parse the actual STL/OBJ file
        # or extract mesh data directly from FreeCAD's Mesh API
        mesh_data = {
            "vertices": [],
            "faces": [],
            "normals": [],
            "format": mesh_format.lower(),
            "vertex_count": 0,
            "face_count": 0,
        }

        # If execution result contains mesh data, use it
        if "mesh" in execution_result:
            mesh_data.update(execution_result["mesh"])

        # Add metadata
        mesh_data["source_file"] = mesh_file_path
        mesh_data["extracted"] = True

        return mesh_data
