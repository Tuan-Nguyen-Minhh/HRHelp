from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.agents.http import router as template_router
from src.common.auth import router as auth_router
from src.common.errors import AppError
from src.core.config import settings
from src.core.security.seeder import seed_rbac
from src.db.session import SessionLocal
from src.features.answer.controller import router as answer_router
from src.features.clarify.controller import router as clarify_router
from src.features.opencase.controller import router as opencase_router


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
app.include_router(answer_router, prefix="/api/v1")
app.include_router(template_router, prefix="/api/v1")


@app.exception_handler(AppError)
async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.APP_ENV}
