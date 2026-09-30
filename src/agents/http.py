"""HTTP of the template graph.

``POST /chat`` and ``GET /status`` belong to the boilerplate agent in
``src.agents.graph``. They are not one of the four product features.
"""

from fastapi import APIRouter, HTTPException

from src.agents.graph import agent
from src.models.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat với AI agent mẫu."""
    try:
        result = await agent.ainvoke({"query": request.message})
        return ChatResponse(
            response=result.get("response", ""),
            analysis=result.get("analysis", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/status")
async def agent_status():
    """Kiểm tra trạng thái agent mẫu."""
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}
