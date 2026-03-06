"""Serveur FastAPI — point d'entree HTTP du core Python."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Literal

import logging

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("mascarade.server")

from mascarade.agents import Agent, AgentRegistry
from mascarade.agents.skills import register_default_skills
from mascarade.auth import add_api_key, get_active_api_keys, remove_api_key, require_auth
from mascarade.config import settings
from mascarade.integrations.comfyui import ComfyUIClient
from mascarade.integrations.notion import NotionClient
from mascarade.orchestrator import Orchestrator
from mascarade.orchestrator.engine import ExecutionMode
from mascarade.router import Router
from mascarade.router.router import Strategy


@asynccontextmanager
async def lifespan(app: FastAPI):
    router = Router()
    registry = AgentRegistry()
    register_default_skills(registry)
    orchestrator = Orchestrator(router=router, registry=registry)

    app.state.router = router
    app.state.registry = registry
    app.state.orchestrator = orchestrator
    app.state.notion = NotionClient() if settings.notion_api_key else None
    app.state.comfyui = ComfyUIClient() if settings.comfyui_url else None

    registry.load()
    yield

    if app.state.notion is not None:
        await app.state.notion.close()
    if app.state.comfyui is not None:
        await app.state.comfyui.close()


app = FastAPI(title="Mascarade Core", version="0.1.0", lifespan=lifespan)


# --- Models ---

class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=100_000)


class SendRequest(BaseModel):
    messages: list[Message] = Field(max_length=200)
    strategy: Strategy = Strategy.BEST
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=100)
    system: str | None = Field(default=None, max_length=10_000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=1000)
    system_prompt: str = Field(max_length=50_000)
    preferred_provider: str | None = Field(default=None, max_length=50)
    preferred_model: str | None = Field(default=None, max_length=100)
    strategy: Strategy = Strategy.BEST
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)


class TaskRequest(BaseModel):
    agent_names: list[str] = Field(max_length=20)
    prompt: str = Field(min_length=1, max_length=100_000)
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL


class NotionAppendRequest(BaseModel):
    content: str = Field(min_length=1, max_length=50_000)


class NotionCreateRequest(BaseModel):
    parent_id: str = Field(max_length=200)
    title: str = Field(max_length=500)
    content: str = Field(default="", max_length=50_000)


class NotionScribeRequest(BaseModel):
    messages: list[Message] = Field(max_length=200)
    push_to: str | None = Field(default=None, max_length=200)


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


# --- Route publique ---

@app.get("/health")
async def health():
    """Health check endpoint - returns basic system status."""
    health_data = {"status": "ok"}

    # Add optional metrics if state is initialized
    if hasattr(app.state, 'router'):
        health_data["providers"] = app.state.router.available_providers
    if hasattr(app.state, 'registry'):
        health_data["agents"] = len(app.state.registry)

    return health_data


# --- Routes protegees ---

protected = APIRouter(dependencies=[Depends(require_auth)])


# --- Gestion des cles API ---

class APIKeyCreate(BaseModel):
    key: str = Field(min_length=8, max_length=256, description="Nouvelle cle API")


class APIKeyRemove(BaseModel):
    key: str = Field(min_length=1, max_length=256, description="Cle API a retirer")


@protected.post("/api-keys")
async def create_api_key(req: APIKeyCreate):
    add_api_key(req.key)
    return {"status": "ok", "message": "API key added successfully"}


@protected.post("/api-keys/remove")
async def delete_api_key(req: APIKeyRemove):
    remove_api_key(req.key)
    return {"status": "ok", "message": "API key removed successfully"}


@protected.get("/api-keys")
async def list_api_keys():
    keys = get_active_api_keys()
    return {"api_keys": [{"key": k[:4] + "***" + k[-4:], "active": True} for k in keys]}


# --- LLM ---

@protected.post("/send")
async def send(req: SendRequest):
    messages = [m.model_dump() for m in req.messages]
    try:
        response = await app.state.router.send(
            messages,
            strategy=req.strategy,
            provider=req.provider,
            model=req.model,
            system=req.system,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except ValueError as exc:
        logger.warning("Send request rejected: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid request parameters") from exc
    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


@protected.get("/providers")
async def list_providers():
    return {"providers": app.state.router.available_providers}


@protected.get("/providers/bedrock/models")
async def bedrock_models():
    """List Bedrock models including fine-tuned custom models."""
    provider = app.state.router._providers.get("bedrock")
    if not provider:
        raise HTTPException(status_code=503, detail="Bedrock provider not configured")
    return {
        "default": provider.default_model,
        "available": provider.available_models(),
        "custom": provider.custom_models(),
    }


@protected.get("/providers/bedrock/finetune-jobs")
async def bedrock_finetune_jobs():
    """Check status of Bedrock fine-tuning jobs."""
    provider = app.state.router._providers.get("bedrock")
    if not provider:
        raise HTTPException(status_code=503, detail="Bedrock provider not configured")
    jobs = await provider.finetune_jobs()
    return {"jobs": jobs}


# --- Metrics ---

@protected.get("/metrics")
async def metrics_summary():
    return app.state.router.metrics_summary()


@protected.get("/metrics/{provider}")
async def metrics_provider(provider: str):
    stats = app.state.router.provider_metrics(provider)
    if not stats:
        raise HTTPException(status_code=404, detail="Provider has no metrics yet")
    return stats


@protected.post("/metrics/reset")
async def metrics_reset():
    app.state.router.reset_metrics()
    return {"status": "ok"}


# --- Cache ---

@protected.get("/cache/stats")
async def cache_stats():
    return app.state.router.cache.get_stats()


@protected.post("/cache/reset")
async def cache_reset():
    app.state.router.cache.clear()
    return {"status": "ok"}


# --- Load Balancer ---

@protected.get("/load-balancer/stats")
async def lb_stats():
    return app.state.router.load_balancer.get_load_stats()


@protected.post("/load-balancer/reset")
async def lb_reset():
    app.state.router.load_balancer.reset_stats()
    return {"status": "ok"}


# --- Fallback ---

@protected.get("/fallback/stats")
async def fallback_stats():
    return app.state.router.fallback.get_failure_stats()


@protected.post("/fallback/reset")
async def fallback_reset():
    app.state.router.fallback.reset()
    return {"status": "ok"}


# --- Agents ---

@protected.post("/agents")
async def create_agent(req: AgentCreate):
    agent = Agent(
        name=req.name,
        description=req.description,
        system_prompt=req.system_prompt,
        preferred_provider=req.preferred_provider,
        preferred_model=req.preferred_model,
        strategy=req.strategy,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    app.state.registry.register(agent)
    app.state.registry.save()
    return {"name": agent.name, "description": agent.description}


@protected.get("/agents")
async def list_agents():
    return {
        "agents": [
            {"name": a.name, "description": a.description}
            for a in app.state.registry.list()
        ]
    }


@protected.post("/agents/{name}/run")
async def run_agent(name: str, req: SendRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    try:
        agent = app.state.registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    messages = [m.model_dump() for m in req.messages]
    prompt = messages[-1]["content"]
    context = messages[:-1] if len(messages) > 1 else None
    response = await agent.run(prompt, router=app.state.router, context=context)
    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


# --- Orchestration ---

@protected.post("/orchestrate")
async def orchestrate(req: TaskRequest):
    try:
        results = await app.state.orchestrator.run(
            req.agent_names,
            req.prompt,
            mode=req.mode,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent not found: {exc}") from exc
    return {
        "results": [
            {
                "agent": r.agent_name,
                "step": r.step,
                "content": r.response.content,
                "model": r.response.model,
                "provider": r.response.provider,
                **({"error": r.error} if r.error else {}),
            }
            for r in results
        ]
    }


# --- Notion ---

def _require_notion() -> NotionClient:
    if app.state.notion is None:
        raise HTTPException(
            status_code=503, detail="Notion non configure (NOTION_API_KEY manquant)"
        )
    return app.state.notion


@protected.get("/notion/search")
async def notion_search(q: str):
    if len(q) > 1000:
        raise HTTPException(status_code=400, detail="Search query too long (max 1000 chars)")
    client = _require_notion()
    results = await client.search(q)
    return {"results": results}


@protected.get("/notion/pages/{page_id}")
async def notion_read_page(page_id: str):
    client = _require_notion()
    content = await client.read_page(page_id)
    return {"page_id": page_id, "content": content}


@protected.post("/notion/pages/{page_id}/append")
async def notion_append(page_id: str, req: NotionAppendRequest):
    client = _require_notion()
    await client.append_to_page(page_id, req.content)
    return {"status": "ok", "page_id": page_id}


@protected.post("/notion/pages")
async def notion_create_page(req: NotionCreateRequest):
    client = _require_notion()
    page_id = await client.create_page(req.parent_id, req.title, req.content)
    return {"page_id": page_id}


@protected.post("/agents/notion-scribe/run-and-push")
async def run_notion_scribe_and_push(req: NotionScribeRequest):
    try:
        agent = app.state.registry.get("notion-scribe")
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent 'notion-scribe' not found")

    messages = [m.model_dump() for m in req.messages]
    prompt = messages[-1]["content"]
    context = messages[:-1] if len(messages) > 1 else None
    response = await agent.run(prompt, router=app.state.router, context=context)

    result = {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
        "pushed_to_notion": False,
    }

    if req.push_to:
        client = _require_notion()
        await client.append_to_page(req.push_to, response.content)
        result["pushed_to_notion"] = True
        result["notion_page_id"] = req.push_to

    return result


# --- ComfyUI ---

def _require_comfyui() -> ComfyUIClient:
    if app.state.comfyui is None:
        raise HTTPException(
            status_code=503, detail="ComfyUI non configure (COMFYUI_URL manquant)"
        )
    return app.state.comfyui


@protected.get("/comfyui/status")
async def comfyui_status():
    client = _require_comfyui()
    return await client.get_system_stats()


@protected.get("/comfyui/queue")
async def comfyui_queue():
    client = _require_comfyui()
    return await client.get_queue_status()


@protected.get("/comfyui/models/{model_type}")
async def comfyui_models(model_type: str = "checkpoints"):
    client = _require_comfyui()
    models = await client.list_models(model_type)
    return {"models": models, "type": model_type}


@protected.post("/comfyui/generate")
async def comfyui_generate(req: ComfyUIGenerateRequest):
    client = _require_comfyui()
    result = await client.generate_image(
        req.prompt, req.negative_prompt,
        checkpoint=req.checkpoint, width=req.width, height=req.height,
        steps=req.steps, cfg=req.cfg, seed=req.seed,
    )
    return result


@protected.post("/comfyui/workflow")
async def comfyui_workflow(req: ComfyUIWorkflowRequest):
    if not req.workflow or not isinstance(req.workflow, dict):
        raise HTTPException(status_code=400, detail="Workflow must be a non-empty object")
    if len(str(req.workflow)) > 500_000:
        raise HTTPException(status_code=400, detail="Workflow payload too large")
    client = _require_comfyui()
    prompt_id = await client.queue_prompt(req.workflow)
    return {"prompt_id": prompt_id}


@protected.get("/comfyui/history/{prompt_id}")
async def comfyui_history(prompt_id: str):
    client = _require_comfyui()
    return await client.get_history(prompt_id)


@protected.get("/comfyui/image")
async def comfyui_image(filename: str, subfolder: str = "", type: str = "output"):
    from fastapi.responses import Response

    client = _require_comfyui()
    try:
        image_data = await client.get_image(filename, subfolder, type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid image path parameters")
    return Response(content=image_data, media_type="image/png")


@protected.post("/comfyui/interrupt")
async def comfyui_interrupt():
    client = _require_comfyui()
    await client.interrupt()
    return {"status": "ok"}


app.include_router(protected)


def start():
    import uvicorn
    uvicorn.run(app, host=settings.core_host, port=settings.core_port)


if __name__ == "__main__":
    start()
