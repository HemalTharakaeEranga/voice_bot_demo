from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import router
from app.config import get_settings
from app.db import Base, engine
from app.security import (
    DEFAULT_REQUEST_BODY_LIMIT,
    VOICE_UPLOAD_BODY_LIMIT,
    RequestSizeLimitMiddleware,
    SameOriginMiddleware,
    SecurityHeadersMiddleware,
    SimpleRateLimitMiddleware,
)
from app.voice import router as voice_router

settings = get_settings()
static_directory = Path(__file__).parent / "static"


def create_app(
    *,
    initialize_database: bool = True,
    default_request_body_limit: int = DEFAULT_REQUEST_BODY_LIMIT,
    voice_rate_limit_requests: int | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        if initialize_database:
            Base.metadata.create_all(bind=engine)
        yield

    development_mode = settings.app_env.casefold() == "development"
    application = FastAPI(
        title="Clinic Voicebot Demo",
        version="1.0.0",
        docs_url="/docs" if development_mode else None,
        redoc_url=None,
        openapi_url="/openapi.json" if development_mode else None,
        lifespan=lifespan,
    )

    # Middleware is added inside-out. Security headers are outermost so host,
    # origin, rate-limit and body-size rejection responses receive them too.
    application.add_middleware(
        RequestSizeLimitMiddleware,
        default_max_bytes=default_request_body_limit,
        limits_by_path={"/api/voice/transcribe": VOICE_UPLOAD_BODY_LIMIT},
    )
    application.add_middleware(
        SimpleRateLimitMiddleware,
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
        path_prefixes=("/api/",),
    )
    application.add_middleware(
        SimpleRateLimitMiddleware,
        max_requests=(
            settings.voice_rate_limit_requests
            if voice_rate_limit_requests is None
            else voice_rate_limit_requests
        ),
        window_seconds=settings.rate_limit_window_seconds,
        path_prefixes=("/api/voice/", "/api/tts/"),
    )
    application.add_middleware(SameOriginMiddleware)
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
    application.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=settings.app_env.casefold() == "production",
    )
    application.include_router(router)
    application.include_router(voice_router)
    application.mount("/static", StaticFiles(directory=static_directory), name="static")

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_directory / "index.html")

    return application


app = create_app()
