import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.api.v1 import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.bootstrap import ensure_bootstrap_admin

logger = get_logger("request")


def _init_sentry() -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )


def create_app() -> FastAPI:
    configure_logging()
    settings.assert_production_ready()
    for _warning in settings.startup_warnings:
        logger.warning('startup_warning %s', _warning)
    _init_sentry()
    ensure_bootstrap_admin()

    app = FastAPI(title="GB Rewards API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.env == "dev" else settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %s %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    register_exception_handlers(app)
    app.include_router(api_router)

    # Serve backend-hosted static assets (e.g. ad-carousel banner posters).
    # Relative image_urls like '/static/banners/goodbed-poster.jpg' resolve here.
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    return app


app = create_app()
