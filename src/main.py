import logging
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.http import router as template_router
from src.common.auth import router as auth_router
from src.common.deps import get_session
from src.common.errors import AppError, error_body
from src.core.config import settings
from src.core.security.seeder import seed_rbac
from src.db.session import SessionLocal
from src.features.accounts.controller import router as accounts_router
from src.features.answer.controller import officers_router
from src.features.answer.controller import router as answer_router
from src.features.assessment.controller import router as assessment_router
from src.features.clarify.controller import router as clarify_router
from src.features.dashboard.controller import router as dashboard_router
from src.features.decision.controller import manager_router
from src.features.decision.controller import router as decision_router
from src.features.export.controller import router as export_router
from src.features.health.model import readiness
from src.features.ingestion.controller import router as ingestion_router
from src.features.knowledge.controller import router as knowledge_router
from src.features.legal_review.controller import router as legal_router
from src.features.notification.controller import router as notification_router
from src.features.opencase.controller import router as opencase_router
from src.features.recidivism.controller import router as recidivism_router
from src.features.standalone_chat.controller import router as standalone_chat_router
from src.features.timeline.controller import router as timeline_router

logger = logging.getLogger("src.main")


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )


_configure_logging()

_HTTP_CODES = {
    401: "AUTH_REQUIRED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "UNPROCESSABLE",
    503: "UNAVAILABLE",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    try:
        async with SessionLocal() as session:
            await seed_rbac(session)
    except Exception as exc:
        print(f"[RBAC] Seed skipped: {type(exc).__name__}")
    yield
    print("Shutting down...")


app = FastAPI(
    title="AI20K Agent",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(opencase_router, prefix="/api/v1")
app.include_router(clarify_router, prefix="/api/v1")
app.include_router(standalone_chat_router, prefix="/api/v1")
app.include_router(answer_router, prefix="/api/v1")
app.include_router(officers_router, prefix="/api/v1")
app.include_router(assessment_router, prefix="/api/v1")
app.include_router(legal_router, prefix="/api/v1")
app.include_router(decision_router, prefix="/api/v1")
app.include_router(manager_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(timeline_router, prefix="/api/v1")
app.include_router(recidivism_router, prefix="/api/v1")
app.include_router(export_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(notification_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(template_router, prefix="/api/v1")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Stamp every request. Error bodies echo the same id. Credentials stay out of the log."""
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, str(exc.detail), exc.details, _request_id(request)),
    )


@app.exception_handler(HTTPException)
async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Yêu cầu không hợp lệ."
    body = error_body(
        _HTTP_CODES.get(exc.status_code, "INTERNAL"),
        message,
        {},
        _request_id(request),
    )
    if not isinstance(exc.detail, str):
        body["detail"] = jsonable_encoder(exc.detail)
    return JSONResponse(status_code=exc.status_code, content=body, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    body = error_body("UNPROCESSABLE", "Dữ liệu không hợp lệ.", {}, _request_id(request))
    body["detail"] = jsonable_encoder(exc.errors())
    return JSONResponse(status_code=422, content=body)


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("request failed request_id=%s", _request_id(request))
    return JSONResponse(
        status_code=500,
        content=error_body("INTERNAL", "Lỗi hệ thống.", {}, _request_id(request)),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.APP_ENV}


@app.get("/ready")
async def ready(session: Annotated[AsyncSession, Depends(get_session)]):
    """Required dependencies. The body lists booleans and never credentials."""
    ok, checks = await readiness(session)
    payload = {"status": "ready" if ok else "not_ready", "checks": checks}
    return JSONResponse(status_code=200 if ok else 503, content=payload)
