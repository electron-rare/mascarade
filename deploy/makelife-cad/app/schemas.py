from datetime import datetime
from typing import Any
from pydantic import BaseModel


class ToolCallRequest(BaseModel):
    tool: str
    args: dict = {}


class ToolCallResponse(BaseModel):
    result: Any
    tool: str


class ProjectInfo(BaseModel):
    id: str
    name: str
    path: str
    created: datetime


class HealthResponse(BaseModel):
    ok: bool
    service: str
    version: str
