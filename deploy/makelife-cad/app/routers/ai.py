from fastapi import APIRouter, Depends, UploadFile
from app.middleware.auth import get_current_user
from app.services.datasheet_ingest import datasheet_ingestor
from app.services.ai_assistant import ai_assistant
from app.services.component_search import component_search

router = APIRouter()


@router.post("/datasheets/ingest")
async def ingest_datasheet(
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
):
    content = await file.read()
    result = await datasheet_ingestor.ingest(file.filename or "doc.pdf", content)
    return {"status": "ingested", "filename": file.filename, "result": result}


@router.post("/ai/chat")
async def ai_chat(
    request: dict,
    current_user: dict = Depends(get_current_user),
):
    message = request.get("message", "")
    project_context = request.get("project_context", "")
    result = await ai_assistant.chat(message, project_context)
    return result


@router.post("/components/search")
async def search_components(
    request: dict,
    current_user: dict = Depends(get_current_user),
):
    query = request.get("query", "")
    limit = request.get("limit", 10)
    result = await component_search.search(query, limit)
    return result
