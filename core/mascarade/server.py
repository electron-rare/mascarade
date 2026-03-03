"""Serveur FastAPI — point d'entrée HTTP du core Python."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from mascarade.config import settings
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.router = router
    app.state.registry = registry
    app.state.orchestrator = orchestrator
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


@app.post("/orchestrate")
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


def start():
    import uvicorn
    uvicorn.run(app, host=settings.core_host, port=settings.core_port)


if __name__ == "__main__":
    start()
