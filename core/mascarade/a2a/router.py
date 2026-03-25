"""A2A protocol endpoints for FastAPI."""
from __future__ import annotations
import logging, uuid, time
from typing import Any
from mascarade.a2a.agent_card import AgentCard

logger = logging.getLogger("mascarade.a2a")
_tasks: dict[str, dict] = {}

def mount_a2a(app: Any, card: AgentCard) -> None:
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.get("/.well-known/agent.json")
    async def agent_card_endpoint():
        return card.to_dict()

    @app.post("/a2a/tasks")
    async def create_task(request: Request):
        body = await request.json()
        task_id = str(uuid.uuid4())
        _tasks[task_id] = {
            "id": task_id, "status": "pending",
            "input": body.get("input", ""), "agent": body.get("agent", card.name),
            "created_at": time.time(), "result": None,
        }
        return JSONResponse({"id": task_id, "status": "pending"}, status_code=201)

    @app.get("/a2a/tasks/{task_id}")
    async def get_task(task_id: str):
        task = _tasks.get(task_id)
        if not task:
            return JSONResponse({"error": "not found"}, status_code=404)
        return task

    @app.get("/a2a/tasks")
    async def list_tasks():
        return list(_tasks.values())[-50:]

    logger.info("A2A protocol mounted (/.well-known/agent.json, /a2a/tasks)")
