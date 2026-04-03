from fastapi import APIRouter, Depends
from app.services.mcp_client import mcp_client
from app.schemas import ToolCallRequest
from app.middleware.auth import get_current_user

router = APIRouter()


@router.get("/tools")
async def list_tools(current_user: dict = Depends(get_current_user)):
    tools = await mcp_client.list_tools()
    return {"tools": tools, "count": len(tools)}


@router.post("/tools/call")
async def call_tool(request: ToolCallRequest, current_user: dict = Depends(get_current_user)):
    result = await mcp_client.call_tool(request.tool, request.args)
    return {"result": result, "tool": request.tool}
