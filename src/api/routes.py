"""HTTP routes mounted at /api/v1.

Case features live on their own controllers. The template chat graph stays
here so POST /chat and GET /status keep their old paths.
"""

from fastapi import APIRouter, HTTPException

from src.agents.graph import agent
from src.features.answer.controller import router as answer_router
from src.features.clarify.controller import router as clarify_router
from src.features.opencase.controller import router as opencase_router
from src.models.schemas import ChatRequest, ChatResponse

router = APIRouter()
router.include_router(opencase_router)
router.include_router(clarify_router)
router.include_router(answer_router)


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
