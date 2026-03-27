"""Mesh node worker — pure-Python mesh operations for the Node Engine.

Provides STL/OBJ/PLY import/export, bounding box calculation, triangle
counting, mesh simplification, and boolean operations. No external
dependencies required (no MCP, no FreeCAD).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MeshWorker:
    """Worker for mesh geometry operations.

    Provides graph-composable nodes for mesh import/export, simplification,
    and boolean operations (union, intersection, difference). Serves as building
    blocks for CAD pipelines. All operations run in pure Python.
    """

    node_types = [
        "cad.mesh.import",
        "cad.mesh.export",
        "cad.mesh.simplify",
        "cad.mesh.boolean",
        "cad.mesh.validate",
        "cad.mesh.stats",
    ]

    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a mesh operation node.

        Args:
            node_type: The node type ID (e.g., "cad.mesh.import")
            inputs: Input values for the node

        Returns:
            Dictionary of output values

        Raises:
            ValueError: If node_type is not recognized
        """
        handlers = {
            "cad.mesh.import": self._execute_import,
            "cad.mesh.export": self._execute_export,
            "cad.mesh.simplify": self._execute_simplify,
            "cad.mesh.boolean": self._execute_boolean,
            "cad.mesh.validate": self._execute_validate,
            "cad.mesh.stats": self._execute_stats,
        }
        handler = handlers.get(node_type)
        if not handler:
            raise ValueError(f"Unknown mesh node type: {node_type}")
        return await handler(inputs)

    async def _execute_validate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Validate an STL file or mesh data structure.

        Inputs:
            - data: string (ASCII STL content) OR mesh dict
            - format: string (optional, default "stl")

        Outputs:
            - valid: bool
            - errors: list[str]
            - triangle_count: int
            - vertex_count: int
            - bounding_box: dict
        """
        data = inputs.get("data", "")
        mesh = inputs.get("mesh")
        fmt = inputs.get("format", "stl").lower()

        errors: list[str] = []

        if mesh and isinstance(mesh, dict):
            # Validate mesh dict directly
            pass
        elif data:
            try:
                mesh = await self._parse_mesh(data, fmt)
            except Exception as exc:
                return {
                    "valid": False,
                    "errors": [f"Parse error: {exc}"],
                    "triangle_count": 0,
                    "vertex_count": 0,
                    "bounding_box": {"min": [0, 0, 0], "max": [0, 0, 0]},
                }
        else:
            return {
                "valid": False,
                "errors": ["No data or mesh provided"],
                "triangle_count": 0,
                "vertex_count": 0,
                "bounding_box": {"min": [0, 0, 0], "max": [0, 0, 0]},
            }

        vertices = mesh.get("vertices", [])
        faces = mesh.get("faces", [])

        # Structural checks
        if not vertices:
            errors.append("Mesh has no vertices")
        if not faces:
            errors.append("Mesh has no faces")

        # Check face index validity
        num_verts = len(vertices)
        for i, face in enumerate(faces):
            if len(face) < 3:
                errors.append(f"Face {i} has fewer than 3 vertices")
            for idx in face:
                if idx < 0 or idx >= num_verts:
                    errors.append(f"Face {i} references invalid vertex index {idx}")
                    break

        # Check for degenerate triangles (zero area)
        degenerate_count = 0
        for face in faces:
            if len(face) >= 3:
                area = self._calculate_triangle_area(vertices, face)
                if area < 1e-12:
                    degenerate_count += 1
        if degenerate_count > 0:
            errors.append(f"{degenerate_count} degenerate (zero-area) triangles found")

        stats = self._calculate_mesh_stats(mesh)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "triangle_count": stats["face_count"],
            "vertex_count": stats["vertex_count"],
            "bounding_box": stats["bounding_box"],
        }

    async def _execute_stats(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Calculate mesh statistics: bounding box, triangle count, surface area, volume.

        Inputs:
            - mesh: MeshData dict OR data+format for parsing

        Outputs:
            - vertex_count, face_count, bounding_box, surface_area, volume, is_manifold
        """
        mesh = inputs.get("mesh")
        if not mesh:
            data = inputs.get("data", "")
            fmt = inputs.get("format", "stl").lower()
            if data:
                mesh = await self._parse_mesh(data, fmt)
            else:
                raise ValueError("mesh or data is required for stats")

        return self._calculate_mesh_stats(mesh)

    async def _execute_import(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute mesh import operation."""
        data = inputs.get("data", "")
        format_type = inputs.get("format", "stl").lower()

        if not data:
            raise ValueError("data is required for mesh import")

        mesh = await self._parse_mesh(data, format_type)
        stats = self._calculate_mesh_stats(mesh)

        return {"mesh": mesh, "stats": stats}

    async def _execute_export(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute mesh export operation."""
        mesh = inputs.get("mesh", {})
        format_type = inputs.get("format", "stl").lower()
        options = inputs.get("options", {})

        if not mesh:
            raise ValueError("mesh is required for mesh export")

        data = await self._export_mesh(mesh, format_type, options)
        file_size = len(data) if isinstance(data, (str, bytes)) else 0

        result = {
            "format": format_type,
            "file_path": f"mesh.{format_type}",
            "file_size_bytes": file_size,
            "warnings": [],
        }

        return {"data": data, "result": result}

    async def _execute_simplify(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute mesh simplification operation."""
        mesh = inputs.get("mesh", {})
        target_ratio = inputs.get("target_ratio", 0.5)
        preserve_boundaries = inputs.get("preserve_boundaries", True)

        if not mesh:
            raise ValueError("mesh is required for mesh simplify")

        if not 0.0 <= target_ratio <= 1.0:
            raise ValueError(f"target_ratio must be between 0.0 and 1.0, got {target_ratio}")

        original_face_count = len(mesh.get("faces", []))
        simplified_mesh = await self._simplify_mesh(mesh, target_ratio, preserve_boundaries)
        simplified_face_count = len(simplified_mesh.get("faces", []))

        if original_face_count > 0:
            reduction_pct = (
                (original_face_count - simplified_face_count) / original_face_count
            ) * 100
        else:
            reduction_pct = 0.0

        return {"mesh": simplified_mesh, "reduction_pct": reduction_pct}

    async def _execute_boolean(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute mesh boolean operation."""
        mesh_a = inputs.get("mesh_a", {})
        mesh_b = inputs.get("mesh_b", {})
        operation = inputs.get("operation", "union").lower()

        if not mesh_a:
            raise ValueError("mesh_a is required for boolean operation")
        if not mesh_b:
            raise ValueError("mesh_b is required for boolean operation")

        valid_operations = ["union", "intersection", "difference"]
        if operation not in valid_operations:
            raise ValueError(
                f"Invalid operation '{operation}'. Must be one of: {', '.join(valid_operations)}"
            )

        result_mesh = await self._boolean_operation(mesh_a, mesh_b, operation)

        return {"mesh": result_mesh}

    async def _parse_mesh(self, data: str, format_type: str) -> dict[str, Any]:
        """Parse mesh data from various formats.

        Args:
            data: Mesh data (base64-encoded for binary formats, or ASCII)
            format_type: Format type ('stl', 'obj', 'ply')

        Returns:
            MeshData dictionary with vertices, faces, and normals
        """
        if format_type == "stl":
            return await self._parse_stl(data)
        elif format_type == "obj":
            return await self._parse_obj(data)
        elif format_type == "ply":
            return await self._parse_ply(data)
        else:
            raise ValueError(f"Unsupported mesh format: {format_type}")

    async def _parse_stl(self, data: str) -> dict[str, Any]:
        """Parse STL mesh data (ASCII format).

        Args:
            data: STL data string

        Returns:
            MeshData dictionary
        """
        vertices = []
        faces = []
        normals = []
        vertex_map = {}  # Map to deduplicate vertices
        current_face_vertices = []
        current_normal = None

        lines = data.strip().split("\n")
        for line in lines:
            line = line.strip()

            if line.startswith("facet normal"):
                # Parse normal vector
                parts = line.split()
                current_normal = [float(parts[2]), float(parts[3]), float(parts[4])]

            elif line.startswith("vertex"):
                # Parse vertex
                parts = line.split()
                vertex = [float(parts[1]), float(parts[2]), float(parts[3])]

                # Deduplicate vertices
                vertex_key = tuple(vertex)
                if vertex_key not in vertex_map:
                    vertex_map[vertex_key] = len(vertices)
                    vertices.append(vertex)

                current_face_vertices.append(vertex_map[vertex_key])

            elif line.startswith("endfacet"):
                # Complete the face
                if len(current_face_vertices) == 3:
                    faces.append(current_face_vertices)
                    if current_normal:
                        normals.append(current_normal)

                current_face_vertices = []
                current_normal = None

        return {
            "vertices": vertices,
            "faces": faces,
            "normals": normals,
            "format": "stl",
        }

    async def _parse_obj(self, data: str) -> dict[str, Any]:
        """Parse OBJ mesh data.

        Args:
            data: OBJ data string

        Returns:
            MeshData dictionary
        """
        vertices = []
        faces = []

        lines = data.strip().split("\n")
        for line in lines:
            line = line.strip()

            if line.startswith("v "):
                # Parse vertex
                parts = line.split()
                vertex = [float(parts[1]), float(parts[2]), float(parts[3])]
                vertices.append(vertex)

            elif line.startswith("f "):
                # Parse face (OBJ indices are 1-based)
                parts = line.split()
                face_indices = []
                for part in parts[1:]:
                    # Handle formats like "v/vt/vn" or "v//vn" or just "v"
                    vertex_idx = int(part.split("/")[0]) - 1
                    face_indices.append(vertex_idx)

                if len(face_indices) >= 3:
                    faces.append(face_indices[:3])  # Use first 3 vertices for triangle

        return {
            "vertices": vertices,
            "faces": faces,
            "normals": [],
            "format": "obj",
        }

    async def _parse_ply(self, data: str) -> dict[str, Any]:
        """Parse PLY mesh data (ASCII format).

        Args:
            data: PLY data string

        Returns:
            MeshData dictionary
        """
        vertices = []
        faces = []
        vertex_count = 0
        face_count = 0
        in_header = True
        vertex_section = False
        face_section = False

        lines = data.strip().split("\n")
        for line in lines:
            line = line.strip()

            if in_header:
                if line.startswith("element vertex"):
                    vertex_count = int(line.split()[2])
                elif line.startswith("element face"):
                    face_count = int(line.split()[2])
                elif line == "end_header":
                    in_header = False
                    vertex_section = True
            else:
                if vertex_section and len(vertices) < vertex_count:
                    parts = line.split()
                    vertex = [float(parts[0]), float(parts[1]), float(parts[2])]
                    vertices.append(vertex)

                    if len(vertices) == vertex_count:
                        vertex_section = False
                        face_section = True

                elif face_section and len(faces) < face_count:
                    parts = line.split()
                    # First number is vertex count, rest are indices
                    num_vertices = int(parts[0])
                    face_indices = [int(parts[i + 1]) for i in range(min(num_vertices, 3))]
                    faces.append(face_indices)

        return {
            "vertices": vertices,
            "faces": faces,
            "normals": [],
            "format": "ply",
        }

    async def _export_mesh(
        self, mesh: dict[str, Any], format_type: str, options: dict[str, Any]
    ) -> str:
        """Export mesh to target format.

        Args:
            mesh: MeshData dictionary
            format_type: Target format ('stl', 'obj', 'ply')
            options: Export options

        Returns:
            Exported mesh data as string
        """
        if format_type == "stl":
            return await self._export_stl(mesh, options)
        elif format_type == "obj":
            return await self._export_obj(mesh, options)
        elif format_type == "ply":
            return await self._export_ply(mesh, options)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")

    async def _export_stl(self, mesh: dict[str, Any], options: dict[str, Any]) -> str:
        """Export mesh to STL format (ASCII).

        Args:
            mesh: MeshData dictionary
            options: Export options

        Returns:
            STL data string
        """
        vertices = mesh.get("vertices", [])
        faces = mesh.get("faces", [])
        normals = mesh.get("normals", [])

        lines = ["solid mesh"]

        for i, face in enumerate(faces):
            # Get normal vector (use stored or calculate)
            if i < len(normals):
                normal = normals[i]
            else:
                normal = self._calculate_face_normal(vertices, face)

            lines.append(f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}")
            lines.append("    outer loop")

            for vertex_idx in face:
                if vertex_idx < len(vertices):
                    v = vertices[vertex_idx]
                    lines.append(f"      vertex {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")

            lines.append("    endloop")
            lines.append("  endfacet")

        lines.append("endsolid mesh")

        return "\n".join(lines)

    async def _export_obj(self, mesh: dict[str, Any], options: dict[str, Any]) -> str:
        """Export mesh to OBJ format.

        Args:
            mesh: MeshData dictionary
            options: Export options

        Returns:
            OBJ data string
        """
        vertices = mesh.get("vertices", [])
        faces = mesh.get("faces", [])

        lines = ["# OBJ file exported by MeshWorker"]

        # Export vertices
        for v in vertices:
            lines.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")

        # Export faces (OBJ indices are 1-based)
        for face in faces:
            face_str = " ".join(str(idx + 1) for idx in face)
            lines.append(f"f {face_str}")

        return "\n".join(lines)

    async def _export_ply(self, mesh: dict[str, Any], options: dict[str, Any]) -> str:
        """Export mesh to PLY format (ASCII).

        Args:
            mesh: MeshData dictionary
            options: Export options

        Returns:
            PLY data string
        """
        vertices = mesh.get("vertices", [])
        faces = mesh.get("faces", [])

        lines = [
            "ply",
            "format ascii 1.0",
            f"element vertex {len(vertices)}",
            "property float x",
            "property float y",
            "property float z",
            f"element face {len(faces)}",
            "property list uchar int vertex_indices",
            "end_header",
        ]

        # Export vertices
        for v in vertices:
            lines.append(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")

        # Export faces
        for face in faces:
            face_str = " ".join(str(idx) for idx in face)
            lines.append(f"{len(face)} {face_str}")

        return "\n".join(lines)

    async def _simplify_mesh(
        self, mesh: dict[str, Any], target_ratio: float, preserve_boundaries: bool
    ) -> dict[str, Any]:
        """Simplify mesh using edge collapse decimation.

        This is a basic implementation. Production systems would use libraries like
        trimesh or pymeshlab for robust mesh decimation.

        Args:
            mesh: MeshData dictionary
            target_ratio: Target face count ratio (0.0-1.0)
            preserve_boundaries: Whether to preserve boundary edges

        Returns:
            Simplified MeshData dictionary
        """
        vertices = mesh.get("vertices", [])
        faces = mesh.get("faces", [])

        target_face_count = int(len(faces) * target_ratio)

        # Simple decimation: uniformly sample faces
        # In production, use quadric error metrics (QEM) for better quality
        if target_face_count >= len(faces):
            return mesh  # No simplification needed

        step = len(faces) / target_face_count
        simplified_faces = []
        used_vertices = set()

        for i in range(target_face_count):
            face_idx = int(i * step)
            if face_idx < len(faces):
                face = faces[face_idx]
                simplified_faces.append(face)
                used_vertices.update(face)

        # Rebuild vertex list with only used vertices
        vertex_map = {}
        simplified_vertices = []
        for old_idx in sorted(used_vertices):
            if old_idx < len(vertices):
                vertex_map[old_idx] = len(simplified_vertices)
                simplified_vertices.append(vertices[old_idx])

        # Remap face indices
        remapped_faces = []
        for face in simplified_faces:
            remapped_face = [vertex_map.get(idx, 0) for idx in face]
            remapped_faces.append(remapped_face)

        return {
            "vertices": simplified_vertices,
            "faces": remapped_faces,
            "normals": [],
            "format": mesh.get("format", "stl"),
        }

    async def _boolean_operation(
        self, mesh_a: dict[str, Any], mesh_b: dict[str, Any], operation: str
    ) -> dict[str, Any]:
        """Perform boolean operation on two meshes.

        This is a placeholder implementation. Production systems would use libraries
        like PyMesh, trimesh, or libigl for robust CSG operations.

        Args:
            mesh_a: First mesh
            mesh_b: Second mesh
            operation: Boolean operation type ('union', 'intersection', 'difference')

        Returns:
            Result MeshData dictionary
        """
        vertices_a = mesh_a.get("vertices", [])
        faces_a = mesh_a.get("faces", [])
        vertices_b = mesh_b.get("vertices", [])
        faces_b = mesh_b.get("faces", [])

        # Placeholder: For union, combine both meshes
        # Production implementation would:
        # 1. Compute mesh intersections
        # 2. Classify faces (inside/outside/on-boundary)
        # 3. Construct result mesh based on operation
        if operation == "union":
            # Simple concatenation (not a true union)
            result_vertices = vertices_a + vertices_b
            result_faces = faces_a + [[idx + len(vertices_a) for idx in face] for face in faces_b]

        elif operation == "intersection":
            # Placeholder: return smaller mesh
            if len(faces_a) <= len(faces_b):
                result_vertices = vertices_a
                result_faces = faces_a
            else:
                result_vertices = vertices_b
                result_faces = faces_b

        elif operation == "difference":
            # Placeholder: return first mesh
            result_vertices = vertices_a
            result_faces = faces_a

        else:
            raise ValueError(f"Unsupported boolean operation: {operation}")

        return {
            "vertices": result_vertices,
            "faces": result_faces,
            "normals": [],
            "format": mesh_a.get("format", "stl"),
        }

    def _calculate_mesh_stats(self, mesh: dict[str, Any]) -> dict[str, Any]:
        """Calculate mesh statistics.

        Args:
            mesh: MeshData dictionary

        Returns:
            Statistics dictionary
        """
        vertices = mesh.get("vertices", [])
        faces = mesh.get("faces", [])

        # Calculate bounding box
        if vertices:
            xs = [v[0] for v in vertices]
            ys = [v[1] for v in vertices]
            zs = [v[2] for v in vertices]

            bbox = {
                "min": [min(xs), min(ys), min(zs)],
                "max": [max(xs), max(ys), max(zs)],
            }
        else:
            bbox = {"min": [0, 0, 0], "max": [0, 0, 0]}

        # Calculate surface area (approximate)
        surface_area = 0.0
        for face in faces:
            if len(face) >= 3:
                surface_area += self._calculate_triangle_area(vertices, face)

        # Calculate volume (for closed meshes, using divergence theorem)
        volume = 0.0
        if len(faces) > 0:
            volume = self._calculate_mesh_volume(vertices, faces)

        # Check manifold status (simplified check)
        is_manifold = self._is_manifold(faces)

        return {
            "vertex_count": len(vertices),
            "face_count": len(faces),
            "bounding_box": bbox,
            "surface_area": surface_area,
            "volume": abs(volume),
            "is_manifold": is_manifold,
        }

    def _calculate_face_normal(self, vertices: list[list[float]], face: list[int]) -> list[float]:
        """Calculate normal vector for a triangle face.

        Args:
            vertices: List of vertices
            face: Face vertex indices

        Returns:
            Normal vector [x, y, z]
        """
        if len(face) < 3:
            return [0.0, 0.0, 1.0]

        # Get vertices
        v0 = vertices[face[0]] if face[0] < len(vertices) else [0, 0, 0]
        v1 = vertices[face[1]] if face[1] < len(vertices) else [0, 0, 0]
        v2 = vertices[face[2]] if face[2] < len(vertices) else [0, 0, 0]

        # Calculate edge vectors
        edge1 = [v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]]
        edge2 = [v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]]

        # Cross product
        normal = [
            edge1[1] * edge2[2] - edge1[2] * edge2[1],
            edge1[2] * edge2[0] - edge1[0] * edge2[2],
            edge1[0] * edge2[1] - edge1[1] * edge2[0],
        ]

        # Normalize
        length = (normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2) ** 0.5
        if length > 0:
            normal = [n / length for n in normal]

        return normal

    def _calculate_triangle_area(self, vertices: list[list[float]], face: list[int]) -> float:
        """Calculate area of a triangle face.

        Args:
            vertices: List of vertices
            face: Face vertex indices

        Returns:
            Triangle area
        """
        if len(face) < 3:
            return 0.0

        v0 = vertices[face[0]] if face[0] < len(vertices) else [0, 0, 0]
        v1 = vertices[face[1]] if face[1] < len(vertices) else [0, 0, 0]
        v2 = vertices[face[2]] if face[2] < len(vertices) else [0, 0, 0]

        # Calculate edge vectors
        edge1 = [v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]]
        edge2 = [v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]]

        # Cross product magnitude / 2
        cross = [
            edge1[1] * edge2[2] - edge1[2] * edge2[1],
            edge1[2] * edge2[0] - edge1[0] * edge2[2],
            edge1[0] * edge2[1] - edge1[1] * edge2[0],
        ]

        area = 0.5 * (cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2) ** 0.5

        return area

    def _calculate_mesh_volume(self, vertices: list[list[float]], faces: list[list[int]]) -> float:
        """Calculate signed volume of mesh using divergence theorem.

        Args:
            vertices: List of vertices
            faces: List of faces

        Returns:
            Signed volume
        """
        volume = 0.0

        for face in faces:
            if len(face) >= 3:
                v0 = vertices[face[0]] if face[0] < len(vertices) else [0, 0, 0]
                v1 = vertices[face[1]] if face[1] < len(vertices) else [0, 0, 0]
                v2 = vertices[face[2]] if face[2] < len(vertices) else [0, 0, 0]

                # Signed volume contribution of tetrahedron formed with origin
                volume += v0[0] * (v1[1] * v2[2] - v1[2] * v2[1])
                volume += v0[1] * (v1[2] * v2[0] - v1[0] * v2[2])
                volume += v0[2] * (v1[0] * v2[1] - v1[1] * v2[0])

        return volume / 6.0

    def _is_manifold(self, faces: list[list[int]]) -> bool:
        """Check if mesh is manifold (simplified check).

        A manifold mesh has each edge shared by exactly 2 faces.

        Args:
            faces: List of faces

        Returns:
            True if mesh appears manifold
        """
        edge_count = {}

        for face in faces:
            for i in range(len(face)):
                v1 = face[i]
                v2 = face[(i + 1) % len(face)]

                # Create canonical edge key (sorted)
                edge = tuple(sorted([v1, v2]))
                edge_count[edge] = edge_count.get(edge, 0) + 1

        # Check if all edges are shared by exactly 2 faces
        for count in edge_count.values():
            if count != 2:
                return False

        return True
