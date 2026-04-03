import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", "/workspace"))


class ProjectManager:
    def __init__(self, workspace: Path = WORKSPACE_DIR):
        self._workspace = workspace

    def list_projects(self) -> list[dict]:
        projects = []
        if not self._workspace.exists():
            return projects
        for kicad_pro in self._workspace.rglob("*.kicad_pro"):
            meta = self._read_meta(kicad_pro.parent)
            if meta:
                projects.append(meta)
            else:
                projects.append({
                    "id": kicad_pro.stem,
                    "name": kicad_pro.stem,
                    "path": str(kicad_pro.parent.relative_to(self._workspace)),
                    "created": datetime.fromtimestamp(
                        kicad_pro.stat().st_ctime, tz=timezone.utc
                    ).isoformat(),
                })
        return projects

    def create_project(self, name: str) -> dict:
        project_id = str(uuid.uuid4())[:8]
        project_dir = self._workspace / name
        project_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "id": project_id,
            "name": name,
            "path": name,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self._write_meta(project_dir, meta)
        return meta

    def get_project(self, project_id: str) -> dict | None:
        for kicad_pro in self._workspace.rglob("*.kicad_pro"):
            meta = self._read_meta(kicad_pro.parent)
            if meta and meta.get("id") == project_id:
                return meta
        return None

    def delete_project(self, project_id: str) -> bool:
        project = self.get_project(project_id)
        if not project:
            return False
        project_dir = self._workspace / project["path"]
        if project_dir.exists():
            import shutil
            shutil.rmtree(project_dir)
        return True

    def _meta_path(self, project_dir: Path) -> Path:
        return project_dir / ".makelife.json"

    def _read_meta(self, project_dir: Path) -> dict | None:
        meta_file = self._meta_path(project_dir)
        if meta_file.exists():
            return json.loads(meta_file.read_text())
        return None

    def _write_meta(self, project_dir: Path, meta: dict):
        self._meta_path(project_dir).write_text(
            json.dumps(meta, indent=2)
        )


project_manager = ProjectManager()
