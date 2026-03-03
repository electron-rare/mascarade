"""Serveur FastAPI — point d'entrée HTTP du core Python."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from mascarade.config import settings
from mascarade.router import Router
from mascarade.agents import Agent, AgentRegistry
from mascarade.orchestrator import Orchestrator
from mascarade.orchestrator.engine import ExecutionMode


router = Router()
registry = AgentRegistry()
orchestrator = Orchestrator(router=router, registry=registry)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.router = router
    app.state.registry = registry
    app.state.orchestrator = orchestrator
    yield


app = FastAPI(title="Mascarade Core", version="0.1.0", lifespan=lifespan)


# --- Models ---

class SendRequest(BaseModel):
    messages: list[dict]
    strategy: str = "best"
    provider: str | None = None
    model: str | None = None
    system: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096


class AgentCreate(BaseModel):
    name: str
    description: str
    system_prompt: str
    preferred_provider: str | None = None
    preferred_model: str | None = None
    strategy: str = "best"
    temperature: float = 0.7
    max_tokens: int = 4096


class TaskRequest(BaseModel):
    agent_names: list[str]
    prompt: str
    mode: str = "sequential"


# --- Routes ---

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "providers": router.available_providers,
        "agents": len(registry),
    }


@app.post("/send")
async def send(req: SendRequest):
    response = await router.send(
        req.messages,
        strategy=req.strategy,
        provider=req.provider,
        model=req.model,
        system=req.system,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


@app.get("/providers")
async def list_providers():
    return {"providers": router.available_providers}


@app.post("/agents")
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
    return {"name": agent.name, "description": agent.description}


@app.get("/agents")
async def list_agents():
    return {
        "agents": [
            {"name": a.name, "description": a.description}
            for a in registry.list()
        ]
    }


@app.post("/agents/{name}/run")
async def run_agent(name: str, req: SendRequest):
    agent = registry.get(name)
    prompt = req.messages[-1]["content"] if req.messages else ""
    context = req.messages[:-1] if len(req.messages) > 1 else None
    response = await agent.run(prompt, router=router, context=context)
    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


@app.post("/orchestrate")
async def orchestrate(req: TaskRequest):
    results = await orchestrator.run(
        req.agent_names,
        req.prompt,
        mode=req.mode,
    )
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


def start():
    import uvicorn
    uvicorn.run(app, host=settings.core_host, port=settings.core_port)


if __name__ == "__main__":
    start()
