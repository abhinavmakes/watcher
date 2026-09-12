from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

# slowapi injects these onto the response when headers_enabled=True; we mirror them onto
# the custom 429 so the frontend can read the countdown for a toast.
_RATE_LIMIT_HEADERS = (
    "Retry-After",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
)


def _client_ip(request: Request) -> str:
    # X-Forwarded-For is client-supplied and each proxy *appends* the peer it received
    # from, so trustworthy entries sit at the right-hand end. With hops=0 (nothing in
    # front of this app) the header is entirely attacker-controlled and must be ignored;
    # with hops=N, the real client is N entries from the right.
    hops = settings.trusted_proxy_hops
    if hops == 0:
        return get_remote_address(request)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return get_remote_address(request)


limiter = Limiter(
    key_func=_client_ip,
    default_limits=[settings.rate_limit],
    headers_enabled=True,
    enabled=settings.rate_limit_enabled,
)


def rate_limit_handler(request: Request, exc: Exception) -> Response:
    # slowapi computes Retry-After / X-RateLimit-* onto a Response; use a throwaway probe
    # to read them, mirror the countdown into the JSON body, and copy the headers onto the
    # real 429 so the browser gets both a machine-readable body and standard headers.
    probe = limiter._inject_headers(Response(), request.state.view_rate_limit)
    retry_after = probe.headers.get("Retry-After")
    body: dict[str, object] = {
        "detail": "Rate limit exceeded",
        "limit": str(getattr(exc, "detail", "")),
    }
    if retry_after is not None and retry_after.isdigit():
        body["retry_after_seconds"] = int(retry_after)
    response = JSONResponse(status_code=429, content=body)
    for header in _RATE_LIMIT_HEADERS:
        value = probe.headers.get(header)
        if value is not None:
            response.headers[header] = value
    return response
