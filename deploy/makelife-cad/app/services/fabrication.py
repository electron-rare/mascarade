import io
import zipfile
from app.services.mcp_client import mcp_client


class FabricationExporter:
    async def export(
        self, project_path: str, fmt: str = "jlcpcb"
    ) -> bytes:
        gerber = await mcp_client.call_tool(
            "export_gerber", {"project_path": project_path}
        )
        bom = await mcp_client.call_tool(
            "export_bom",
            {"project_path": project_path, "format": "csv"},
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in gerber.get("result", {}).get("files", []):
                zf.writestr(f["name"], f.get("content", ""))
            bom_csv = bom.get("result", {}).get("content", "")
            if bom_csv:
                zf.writestr("BOM.csv", bom_csv)
        buf.seek(0)
        return buf.read()


fabrication_exporter = FabricationExporter()
