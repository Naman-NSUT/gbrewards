import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
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
from app.dealer.bootstrap import ensure_bootstrap_dealer_admin

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


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run the first-run bootstraps at startup, and never let them stop the boot.

    These used to run inline in create_app(), which meant they ran at *import*
    time — before uvicorn had bound a port. Both open a SessionLocal, so a
    database that was briefly unreachable raised OperationalError out of the
    import and the process died. Render starts this container independently of
    the managed Postgres and health-checks /api/v1/healthz, so a blip that lasts
    seconds turned into a crash loop that outlived it.

    Hence: startup, not import, and a failure here is logged rather than fatal.
    The trade is deliberate. A bootstrap that did not run costs one redeploy
    once someone notices there is no admin account. An API that refuses to start
    takes every dealer offline — no sales registered, no warranties issued, no
    lookups — for as long as the database is unhappy, and for a while after.

    The bootstraps still run on every healthy boot; both are idempotent and both
    return early unless their env vars are set.
    """
    steps: tuple[tuple[str, Callable[[], None]], ...] = (
        ("admin", ensure_bootstrap_admin),
        ("dealer_admin", ensure_bootstrap_dealer_admin),
    )
    for name, step in steps:
        try:
            step()
        except Exception:
            logger.exception("bootstrap_failed step=%s", name)
    yield


def create_app() -> FastAPI:
    configure_logging()
    settings.assert_production_ready()
    for _warning in settings.startup_warnings:
        logger.warning("startup_warning %s", _warning)
    _init_sentry()

    app = FastAPI(title="GB Rewards API", version="0.1.0", lifespan=_lifespan)

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
