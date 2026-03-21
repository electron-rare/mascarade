"""Memory management endpoints for Mem0 integration."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from mascarade.auth import require_auth

logger = logging.getLogger("mascarade.routers.memory")

router = APIRouter(prefix="/api", tags=["memory"])


# --- Models ---


class Message(BaseModel):
    """A chat message with role and content."""

    role: str = Field(min_length=1, max_length=20)
    content: str = Field(min_length=1, max_length=100_000)


class MemoryAddRequest(BaseModel):
    """Request model for adding memories."""

    messages: list[Message] = Field(min_length=1, max_length=200)
    user_id: str = Field(min_length=1, max_length=100)
    metadata: dict[str, Any] | None = None
    agent_id: str | None = Field(default=None, max_length=100)


class MemorySearchRequest(BaseModel):
    """Request model for searching memories."""

    query: str = Field(min_length=1, max_length=1000)
    user_id: str = Field(min_length=1, max_length=100)
    limit: int = Field(default=10, ge=1, le=100)
    agent_id: str | None = Field(default=None, max_length=100)


class MemoryGetRequest(BaseModel):
    """Request model for retrieving all memories."""

    user_id: str = Field(min_length=1, max_length=100)
    agent_id: str | None = Field(default=None, max_length=100)


class MemoryDeleteRequest(BaseModel):
    """Request model for deleting memories."""

    memory_id: str = Field(min_length=1, max_length=100)
    user_id: str = Field(min_length=1, max_length=100)


# --- Helper functions ---


def _get_mem0_url(request: Request) -> str:
    """
    Get Mem0 service URL from configuration.

    Args:
        request: FastAPI request object

    Returns:
        Mem0 service base URL
    """
    # Default to docker-compose service name
    return "http://mem0:8765"


async def _mem0_request(
    url: str,
    method: str = "GET",
    json_data: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Make HTTP request to Mem0 service.

    Args:
        url: Request URL
        method: HTTP method (GET, POST, DELETE)
        json_data: JSON request body
        timeout: Request timeout in seconds

    Returns:
        Response JSON data

    Raises:
        HTTPException: If Mem0 service is unavailable or returns an error
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "POST":
                response = await client.post(url, json=json_data)
            elif method == "DELETE":
                response = await client.delete(url, json=json_data)
            else:
                response = await client.get(url, params=json_data)

            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException as e:
        logger.error(f"Mem0 service timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory service timeout",
        ) from e
    except httpx.HTTPStatusError as e:
        logger.error(f"Mem0 service error: {e}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Memory service error: {e.response.text}",
        ) from e
    except Exception as e:
        logger.error(f"Mem0 service connection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory service unavailable",
        ) from e


# --- Endpoints ---


@router.get("/memory/status")
async def get_memory_status(request: Request) -> dict[str, Any]:
    """
    Get Mem0 memory service status.

    Returns basic status information about the Mem0 integration.
    This endpoint will be expanded to include actual Mem0 service health checks.

    Returns:
        Status dictionary with service information
    """
    status_data = {
        "status": "ok",
        "service": "mem0",
        "description": "Mem0 memory integration endpoint"
    }

    # Future: Add actual Mem0 service health check
    # if hasattr(request.app.state, "mem0"):
    #     try:
    #         mem0_status = await request.app.state.mem0.health_check()
    #         status_data["mem0"] = mem0_status
    #     except Exception as e:
    #         status_data["status"] = "degraded"
    #         status_data["error"] = str(e)

    return status_data


@router.post("/memory/add", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)])
async def add_memory(req: MemoryAddRequest, request: Request) -> dict[str, Any]:
    """
    Add memories to Mem0 storage with user/agent scoping.

    Stores conversation context for later retrieval. Memories are scoped to
    user_id and optionally agent_id for privacy isolation.

    Args:
        req: Memory add request with messages, user_id, and optional metadata
        request: FastAPI request object

    Returns:
        Dictionary with memory_id and success status

    Raises:
        HTTPException: If Mem0 service is unavailable (503) or returns an error
    """
    mem0_url = _get_mem0_url(request)

    # Convert messages to Mem0 format
    messages_data = [{"role": msg.role, "content": msg.content} for msg in req.messages]

    # Build request payload
    payload = {
        "messages": messages_data,
        "user_id": req.user_id,
    }

    if req.metadata:
        payload["metadata"] = req.metadata

    if req.agent_id:
        # Add agent_id to metadata for scoping
        if "metadata" not in payload:
            payload["metadata"] = {}
        payload["metadata"]["agent_id"] = req.agent_id

    # Call Mem0 service
    result = await _mem0_request(f"{mem0_url}/memories", method="POST", json_data=payload)

    logger.info(f"Added memory for user_id={req.user_id}, agent_id={req.agent_id}")

    return {
        "memory_id": result.get("id", result.get("memory_id", "unknown")),
        "status": "created",
        "user_id": req.user_id,
        "agent_id": req.agent_id,
    }


@router.post("/memory/search", dependencies=[Depends(require_auth)])
async def search_memory(req: MemorySearchRequest, request: Request) -> dict[str, Any]:
    """
    Search memories using semantic similarity.

    Performs vector similarity search across stored memories for the specified
    user and optional agent.

    Args:
        req: Memory search request with query, user_id, and optional agent_id
        request: FastAPI request object

    Returns:
        Dictionary with matching memories and relevance scores

    Raises:
        HTTPException: If Mem0 service is unavailable (503) or returns an error
    """
    mem0_url = _get_mem0_url(request)

    # Build query parameters
    params = {
        "query": req.query,
        "user_id": req.user_id,
        "limit": req.limit,
    }

    if req.agent_id:
        params["agent_id"] = req.agent_id

    # Call Mem0 service
    result = await _mem0_request(f"{mem0_url}/memories/search", json_data=params)

    logger.info(f"Searched memories for user_id={req.user_id}, query='{req.query[:50]}...'")

    return {
        "memories": result.get("results", result.get("memories", [])),
        "count": len(result.get("results", result.get("memories", []))),
        "user_id": req.user_id,
        "agent_id": req.agent_id,
    }


@router.post("/memory/get", dependencies=[Depends(require_auth)])
async def get_all_memories(req: MemoryGetRequest, request: Request) -> dict[str, Any]:
    """
    Retrieve all memories for a user/agent.

    Fetches all stored memories for the specified user and optional agent.

    Args:
        req: Memory get request with user_id and optional agent_id
        request: FastAPI request object

    Returns:
        Dictionary with all memories for the user/agent

    Raises:
        HTTPException: If Mem0 service is unavailable (503) or returns an error
    """
    mem0_url = _get_mem0_url(request)

    # Build query parameters
    params = {
        "user_id": req.user_id,
    }

    if req.agent_id:
        params["agent_id"] = req.agent_id

    # Call Mem0 service
    result = await _mem0_request(f"{mem0_url}/memories", json_data=params)

    logger.info(f"Retrieved all memories for user_id={req.user_id}, agent_id={req.agent_id}")

    return {
        "memories": result.get("results", result.get("memories", [])),
        "count": len(result.get("results", result.get("memories", []))),
        "user_id": req.user_id,
        "agent_id": req.agent_id,
    }


@router.delete("/memory/delete", dependencies=[Depends(require_auth)])
async def delete_memory(req: MemoryDeleteRequest, request: Request) -> dict[str, Any]:
    """
    Delete a specific memory.

    Removes a memory from storage. Requires user_id for authorization.

    Args:
        req: Memory delete request with memory_id and user_id
        request: FastAPI request object

    Returns:
        Success message confirming deletion

    Raises:
        HTTPException: If Mem0 service is unavailable (503) or memory not found (404)
    """
    mem0_url = _get_mem0_url(request)

    # Build request payload
    payload = {
        "memory_id": req.memory_id,
        "user_id": req.user_id,
    }

    # Call Mem0 service
    await _mem0_request(f"{mem0_url}/memories/{req.memory_id}", method="DELETE", json_data=payload)

    logger.info(f"Deleted memory_id={req.memory_id} for user_id={req.user_id}")

    return {
        "message": f"Memory {req.memory_id} deleted successfully",
        "memory_id": req.memory_id,
        "user_id": req.user_id,
    }
