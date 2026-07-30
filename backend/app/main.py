"""FastAPI application factory for the VLearn backend."""

from __future__ import annotations

import logging
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.ai.core_adapter import VLearnAICoreAdapter
from backend.app.api.compatibility import router as compatibility_router
from backend.app.api.v1 import router as v1_router
from backend.app.application.turn_service import TurnService
from backend.app.config import BackendSettings, get_backend_settings
from backend.app.errors import BackendError
from backend.app.persistence.memory import MemoryRepository
from backend.app.retrieval.local_slides import LocalSlideRepository
from backend.app.session import AnonymousSessionMiddleware

logger = logging.getLogger("vlearn.backend")
ROOT_DIR = Path(__file__).resolve().parents[2]
AI_CORE_DIR = ROOT_DIR / "ai_core"

if str(AI_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_CORE_DIR))


def create_app(
    *,
    settings: BackendSettings | None = None,
    turn_service: TurnService | None = None,
    slide_repository: LocalSlideRepository | None = None,
) -> FastAPI:
    settings = settings or get_backend_settings()
    slides = slide_repository or LocalSlideRepository()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if turn_service is None:
            repository = MemoryRepository()
            ai_core = VLearnAICoreAdapter()
            service = TurnService(repository, ai_core, slides)
        else:
            service = turn_service
        application.state.turn_service = service
        application.state.slide_repository = slides
        yield

    application = FastAPI(
        title=settings.api_title,
        description="Versioned backend powered by the VLearn AI Core learning loop.",
        version=settings.api_version,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "Idempotency-Key", "X-Request-ID"],
    )
    application.add_middleware(AnonymousSessionMiddleware, settings=settings)

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex}"
        request.state.request_id = request_id[:100]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @application.exception_handler(BackendError)
    async def backend_error_handler(request: Request, exc: BackendError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "request_id": getattr(request.state, "request_id", None),
                "error": {"code": exc.code, "message": exc.public_message},
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ):
        safe_errors = [
            {
                "location": list(item.get("loc") or []),
                "type": item.get("type"),
                "message": item.get("msg"),
            }
            for item in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "request_id": getattr(request.state, "request_id", None),
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Dữ liệu request không hợp lệ.",
                    "details": safe_errors,
                },
            },
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.exception("Unhandled backend error request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={
                "request_id": request_id,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Không thể hoàn tất yêu cầu.",
                },
            },
        )

    application.include_router(v1_router)
    application.include_router(compatibility_router)

    frontend_dir = ROOT_DIR / "frontend"
    if settings.serve_frontend and frontend_dir.exists():
        application.mount(
            "/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend"
        )
    return application


app = create_app()
