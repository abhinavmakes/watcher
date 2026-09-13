from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.clusters import router as clusters_router
from app.api.health import router as health_router
from app.api.runs import router as runs_router
from app.core.config import settings
from app.core.rate_limit import limiter, rate_limit_handler

# Vercel routes /api/* to this service without stripping the prefix, so the routes carry
# it too. Keeping it in code rather than in a platform path transform means local dev
# and production serve identical paths.
API_PREFIX = "/api"


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    # SlowAPIMiddleware added first (inner) so CORS wraps it (outer) — CORS headers must
    # land on the 429 or the browser can't read it to show a rate-limit toast.
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        # No cookies, no auth header on this API, so credentialed CORS buys nothing and
        # costs surface: Starlette echoes the caller's Origin instead of "*" when
        # allow_origins contains "*" AND allow_credentials=True, so the day CORS_ORIGINS=*
        # unblocks a deploy, every origin gets credentialed access.
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    for router in (health_router, clusters_router, runs_router):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
