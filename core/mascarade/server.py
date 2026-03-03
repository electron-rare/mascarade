"""Serveur FastAPI — point d'entrée HTTP du core Python."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from mascarade.auth import require_auth

from mascarade.config import settings
from mascarade.integrations.notion import NotionClient
from mascarade.router import Router
from mascarade.agents import Agent, AgentRegistry
from mascarade.agents.skills import register_default_skills
from mascarade.orchestrator import Orchestrator
from mascarade.orchestrator.engine import ExecutionMode
from mascarade.router.router import Strategy


router = Router()
registry = AgentRegistry()
register_default_skills(registry)
orchestrator = Orchestrator(router=router, registry=registry)
notion: NotionClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global notion
    if settings.notion_api_key:
        notion = NotionClient()
    registry.load()
    app.state.router = router
    app.state.registry = registry
    app.state.orchestrator = orchestrator
    app.state.notion = notion
    yield


app = FastAPI(title="Mascarade Core", version="0.1.0", lifespan=lifespan)


# --- Models ---

class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1)


class SendRequest(BaseModel):
    messages: list[Message]
    strategy: Strategy = Strategy.BEST
    provider: str | None = None
    model: str | None = None
    system: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)


class AgentCreate(BaseModel):
    name: str
    description: str
    system_prompt: str
    preferred_provider: str | None = None
    preferred_model: str | None = None
    strategy: Strategy = Strategy.BEST
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)


class TaskRequest(BaseModel):
    agent_names: list[str]
    prompt: str
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL


class NotionAppendRequest(BaseModel):
    content: str = Field(min_length=1)


class NotionCreateRequest(BaseModel):
    parent_id: str
    title: str
    content: str = ""


class NotionScribeRequest(BaseModel):
    messages: list[Message]
    push_to: str | None = None


# --- Routes publiques ---

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "providers": router.available_providers,
        "agents": len(registry),
    }


@app.get("/metrics")
async def get_metrics():
    """Obtenir les métriques complètes du système."""
    return router.metrics_summary()


@app.get("/metrics/providers/{provider_name}")
async def get_provider_metrics(provider_name: str):
    """Obtenir les métriques pour un provider spécifique."""
    return router.provider_metrics(provider_name)


@app.post("/metrics/reset")
async def reset_metrics():
    """Réinitialiser toutes les métriques."""
    router.reset_metrics()
    return {"status": "ok", "message": "Metrics reset successfully"}


@app.get("/cache/stats")
async def get_cache_stats():
    """Obtenir les statistiques du cache."""
    return router.cache.get_stats()


@app.post("/cache/clear")
async def clear_cache():
    """Effacer le cache."""
    router.cache.clear()
    return {"status": "ok", "message": "Cache cleared successfully"}


@app.get("/load-balancer/stats")
async def get_load_balancer_stats():
    """Obtenir les statistiques du load balancer."""
    return router.load_balancer.get_load_stats()


@app.post("/load-balancer/reset")
async def reset_load_balancer():
    """Réinitialiser les statistiques du load balancer."""
    router.load_balancer.reset_stats()
    return {"status": "ok", "message": "Load balancer stats reset successfully"}


@app.get("/fallback/stats")
async def get_fallback_stats():
    """Obtenir les statistiques du mécanisme de fallback."""
    return router.fallback.get_failure_stats()


@app.post("/fallback/reset")
async def reset_fallback():
    """Réinitialiser les statistiques du fallback."""
    router.fallback.reset()
    return {"status": "ok", "message": "Fallback stats reset successfully"}


# --- Routes protégées ---

protected = APIRouter(dependencies=[Depends(require_auth)])


@protected.post("/send")
async def send(req: SendRequest):
    messages = [m.model_dump() for m in req.messages]
    try:
        response = await router.send(
            messages,
            strategy=req.strategy,
            provider=req.provider,
            model=req.model,
            system=req.system,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


@protected.get("/providers")
async def list_providers():
    return {"providers": router.available_providers}


@protected.get("/metrics")
async def metrics_summary():
    return router.metrics_summary()


@protected.get("/metrics/{provider}")
async def metrics_provider(provider: str):
    stats = router.provider_metrics(provider)
    if not stats:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' has no metrics yet")
    return stats


@protected.post("/metrics/reset")
async def metrics_reset():
    router.reset_metrics()
    return {"status": "ok"}


@protected.get("/cache/stats")
async def cache_stats():
    return router.cache.stats()


@protected.post("/cache/reset")
async def cache_reset():
    router.cache.clear()
    return {"status": "ok"}


@protected.get("/load-balancer/stats")
async def lb_stats():
    return router.load_balancer.stats()


@protected.post("/load-balancer/reset")
async def lb_reset():
    router.load_balancer.reset()
    return {"status": "ok"}


@protected.get("/fallback/stats")
async def fallback_stats():
    return router.fallback.stats()


@protected.post("/fallback/reset")
async def fallback_reset():
    router.fallback.reset()
    return {"status": "ok"}


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
    registry.register(agent)
    registry.save()
    return {"name": agent.name, "description": agent.description}


@protected.get("/agents")
async def list_agents():
    return {
        "agents": [
            {"name": a.name, "description": a.description}
            for a in registry.list()
        ]
    }


@protected.post("/agents/{name}/run")
async def run_agent(name: str, req: SendRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    try:
        agent = registry.get(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    messages = [m.model_dump() for m in req.messages]
    prompt = messages[-1]["content"]
    context = messages[:-1] if len(messages) > 1 else None
    response = await agent.run(prompt, router=router, context=context)
    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


@protected.post("/orchestrate")
async def orchestrate(req: TaskRequest):
    try:
        results = await orchestrator.run(
            req.agent_names,
            req.prompt,
            mode=req.mode,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "results": [
            {
                "agent": r.agent_name,
                "step": r.step,
                "content": r.response.content,
                "model": r.response.model,
                "provider": r.response.provider,
            }
            for r in results
        ]
    }


# --- Routes Notion (protégées) ---


def _require_notion() -> NotionClient:
    if notion is None:
        raise HTTPException(
            status_code=503, detail="Notion non configuré (NOTION_API_KEY manquant)"
        )
    return notion


@protected.get("/notion/search")
async def notion_search(q: str):
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
    """Exécuter notion-scribe puis pousser le résultat dans Notion."""
    try:
        agent = registry.get("notion-scribe")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    messages = [m.model_dump() for m in req.messages]
    prompt = messages[-1]["content"]
    context = messages[:-1] if len(messages) > 1 else None
    response = await agent.run(prompt, router=router, context=context)

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


app.include_router(protected)


def start():
    import uvicorn
    uvicorn.run(app, host=settings.core_host, port=settings.core_port)


if __name__ == "__main__":
    start()
