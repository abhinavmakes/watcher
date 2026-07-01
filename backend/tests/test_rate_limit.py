import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.rate_limit import _client_ip, rate_limit_handler
from app.main import app as real_app


def _tiny_app() -> FastAPI:
    # Mirror the real wiring but at 1/minute so the second call trips the limit.
    limiter = Limiter(key_func=_client_ip, default_limits=["1/minute"], headers_enabled=True)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "yes"}

    return app


async def test_429_contract_and_cors_land_on_the_limit_response() -> None:
    transport = httpx.ASGITransport(app=_tiny_app())
    origin = {"origin": "http://localhost:3000"}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.get("/ping", headers=origin)
        second = await client.get("/ping", headers=origin)

    assert first.status_code == 200
    assert second.status_code == 429
    # machine-readable countdown for the toast
    assert second.headers["retry-after"].isdigit()
    body = second.json()
    assert body["detail"] == "Rate limit exceeded"
    assert body["retry_after_seconds"] >= 0
    # CORS header must be present on the 429, or the browser can't read it to toast
    assert second.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_real_app_wires_rate_limiting() -> None:
    assert any(m.cls is SlowAPIMiddleware for m in real_app.user_middleware)
    assert RateLimitExceeded in real_app.exception_handlers
