from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response
from app.middleware.auth import get_current_user
from app.services.fabrication import fabrication_exporter
from app.services.dolibarr_bom import dolibarr_bom
from app.services.drive_storage import drive_storage
from app.services.calendar_milestones import calendar_milestones
from app.services.review_session import review_session

router = APIRouter()


@router.post("/fabrication/export")
async def export_fabrication(
    request: dict,
    current_user: dict = Depends(get_current_user),
):
    project = request.get("project", "")
    fmt = request.get("format", "jlcpcb")
    zip_bytes = await fabrication_exporter.export(project, fmt)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={project}_manufacturing.zip"
        },
    )


@router.post("/bom/sync-dolibarr")
async def sync_bom_dolibarr(
    request: dict,
    current_user: dict = Depends(get_current_user),
):
    components = request.get("components", [])
    results = await dolibarr_bom.check_stock(components)
    return {"components": results}


@router.post("/drive/upload")
async def upload_to_drive(
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
):
    content = await file.read()
    ok = await drive_storage.upload(file.filename or "file", content)
    return {"uploaded": ok, "filename": file.filename}


@router.post("/project/{project_id}/milestones")
async def create_milestone(
    project_id: str,
    request: dict,
    current_user: dict = Depends(get_current_user),
):
    title = request.get("title", "Milestone")
    date = request.get("date", "")
    ok = await calendar_milestones.create_milestone(project_id, title, date)
    return {"created": ok, "project": project_id, "title": title}


@router.post("/review/create")
async def create_review(
    request: dict,
    current_user: dict = Depends(get_current_user),
):
    project_name = request.get("project_name", "")
    result = await review_session.create(project_name)
    return result
