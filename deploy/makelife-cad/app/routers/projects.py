from fastapi import APIRouter, Depends, HTTPException
from app.services.project_manager import project_manager
from app.middleware.auth import get_current_user

router = APIRouter()


@router.get("/projects")
async def list_projects(current_user: dict = Depends(get_current_user)):
    projects = project_manager.list_projects()
    return {"projects": projects}


@router.post("/projects")
async def create_project(request: dict, current_user: dict = Depends(get_current_user)):
    name = request.get("name")
    if not name:
        raise HTTPException(400, "Project name required")
    project = project_manager.create_project(name)
    return project


@router.get("/projects/{project_id}")
async def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, current_user: dict = Depends(get_current_user)):
    if not project_manager.delete_project(project_id):
        raise HTTPException(404, "Project not found")
    return {"deleted": project_id}
