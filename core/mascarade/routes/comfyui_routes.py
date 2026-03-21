"""ComfyUI image generation routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from mascarade.auth import require_auth
from mascarade.integrations.comfyui import ComfyUIClient

logger = logging.getLogger("mascarade.routes.comfyui")

router = APIRouter(prefix="/comfyui", dependencies=[Depends(require_auth)])


# --- Models ---


class ComfyUIGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    negative_prompt: str = Field(default="", max_length=10_000)
    checkpoint: str | None = Field(default=None, max_length=200)
    width: int = Field(default=512, ge=64, le=2048)
    height: int = Field(default=512, ge=64, le=2048)
    steps: int = Field(default=20, ge=1, le=150)
    cfg: float = Field(default=7.0, ge=1.0, le=30.0)
    seed: int = -1


class ComfyUIWorkflowRequest(BaseModel):
    workflow: dict


# --- Helpers ---


def _require_comfyui(request: Request) -> ComfyUIClient:
    if request.app.state.comfyui is None:
        raise HTTPException(
            status_code=503, detail="ComfyUI non configure (COMFYUI_URL manquant)"
        )
    return request.app.state.comfyui


# --- Routes ---


@router.get("/status")
async def comfyui_status(request: Request):
    client = _require_comfyui(request)
    return await client.get_system_stats()


@router.get("/queue")
async def comfyui_queue(request: Request):
    client = _require_comfyui(request)
    return await client.get_queue_status()


@router.get("/models/{model_type}")
async def comfyui_models(request: Request, model_type: str = "checkpoints"):
    client = _require_comfyui(request)
    models = await client.list_models(model_type)
    return {"models": models, "type": model_type}


@router.post("/generate")
async def comfyui_generate(request: Request, req: ComfyUIGenerateRequest):
    client = _require_comfyui(request)
    result = await client.generate_image(
        req.prompt,
        req.negative_prompt,
        checkpoint=req.checkpoint,
        width=req.width,
        height=req.height,
        steps=req.steps,
        cfg=req.cfg,
        seed=req.seed,
    )
    return result


@router.post("/workflow")
async def comfyui_workflow(request: Request, req: ComfyUIWorkflowRequest):
    if not req.workflow or not isinstance(req.workflow, dict):
        raise HTTPException(status_code=400, detail="Workflow must be a non-empty object")
    if len(str(req.workflow)) > 500_000:
        raise HTTPException(status_code=400, detail="Workflow payload too large")
    client = _require_comfyui(request)
    prompt_id = await client.queue_prompt(req.workflow)
    return {"prompt_id": prompt_id}


@router.get("/history/{prompt_id}")
async def comfyui_history(request: Request, prompt_id: str):
    client = _require_comfyui(request)
    return await client.get_history(prompt_id)


@router.get("/image")
async def comfyui_image(
    request: Request, filename: str, subfolder: str = "", type: str = "output"
):
    client = _require_comfyui(request)
    try:
        image_data = await client.get_image(filename, subfolder, type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid image path parameters") from None
    return Response(content=image_data, media_type="image/png")


@router.post("/interrupt")
async def comfyui_interrupt(request: Request):
    client = _require_comfyui(request)
    await client.interrupt()
    return {"status": "ok"}
