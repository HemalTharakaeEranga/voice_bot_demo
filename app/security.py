import time
from collections import OrderedDict, deque
from collections.abc import Callable, Sequence
from math import ceil
from threading import Lock
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

Clock = Callable[[], float]
DEFAULT_MAX_RATE_LIMIT_CLIENTS = 4096
DEFAULT_MAX_RATE_LIMIT_TIMESTAMPS = 262_144
DEFAULT_REQUEST_BODY_LIMIT = 64 * 1024
VOICE_UPLOAD_BODY_LIMIT = 11 * 1024 * 1024


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, enable_hsts: bool = False) -> None:
        super().__init__(app)
        self.enable_hsts = enable_hsts

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self' data:; media-src 'self' blob:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if request.url.path.startswith("/api/") or request.url.path == "/":
            response.headers["Cache-Control"] = "no-store"
        elif request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response


class SameOriginMiddleware(BaseHTTPMiddleware):
    """Reject browser-initiated cross-origin writes to the same-origin API.

    Non-browser clients commonly omit Origin and Sec-Fetch-Site, so missing
    browser headers are allowed. Host validation remains a separate control.
    """

    _SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
    _ALLOWED_FETCH_SITES = frozenset({"same-origin", "none"})

    async def dispatch(self, request: Request, call_next):
        if request.method in self._SAFE_METHODS or not request.url.path.startswith("/api/"):
            return await call_next(request)

        fetch_site = request.headers.get("sec-fetch-site", "").strip().lower()
        if fetch_site and fetch_site not in self._ALLOWED_FETCH_SITES:
            return self._rejected_response()

        origin = request.headers.get("origin")
        host = request.headers.get("host")
        if origin is not None and not self._origin_matches_host(origin, host):
            return self._rejected_response()

        return await call_next(request)

    @staticmethod
    def _origin_matches_host(origin: str, host: str | None) -> bool:
        if not host or origin == "null":
            return False
        try:
            parsed_origin = urlsplit(origin)
            parsed_host = urlsplit(f"//{host}")
            origin_port = parsed_origin.port
            host_port = parsed_host.port
        except ValueError:
            return False

        if (
            parsed_origin.scheme not in {"http", "https"}
            or not parsed_origin.hostname
            or not parsed_host.hostname
            or parsed_origin.username is not None
            or parsed_origin.password is not None
            or parsed_origin.path not in {"", "/"}
            or parsed_origin.query
            or parsed_origin.fragment
        ):
            return False
        if parsed_origin.hostname.casefold() != parsed_host.hostname.casefold():
            return False

        default_origin_port = 443 if parsed_origin.scheme == "https" else 80
        effective_origin_port = origin_port or default_origin_port
        effective_host_port = host_port or default_origin_port
        return effective_origin_port == effective_host_port

    @staticmethod
    def _rejected_response() -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": "Cross-origin request rejected"})


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    """Small, bounded in-memory demo rate limiter.

    Production deployments should replace this with a distributed limiter at
    the reverse proxy/API gateway layer. X-Forwarded-For is deliberately not
    trusted because this application does not configure trusted proxy networks.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int,
        window_seconds: int,
        *,
        max_clients: int = DEFAULT_MAX_RATE_LIMIT_CLIENTS,
        max_timestamps: int = DEFAULT_MAX_RATE_LIMIT_TIMESTAMPS,
        path_prefixes: Sequence[str] = (),
        clock: Clock = time.monotonic,
    ) -> None:
        super().__init__(app)
        if (
            max_requests <= 0
            or window_seconds <= 0
            or max_clients <= 0
            or max_timestamps < max_requests
        ):
            raise ValueError("Rate-limit values are invalid")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_clients = min(max_clients, max_timestamps // max_requests)
        self.path_prefixes = tuple(path_prefixes)
        self.clock = clock
        self.requests_by_ip: OrderedDict[str, deque[float]] = OrderedDict()
        self.lock = Lock()

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/health", "/favicon.ico"} or not self._limits_path(
            request.url.path
        ):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = self.clock()
        cutoff = now - self.window_seconds

        with self.lock:
            timestamps = self.requests_by_ip.get(client_ip)
            if timestamps is None:
                self._prune_inactive_clients(cutoff)
                if len(self.requests_by_ip) >= self.max_clients:
                    return self._rate_limited_response(self.window_seconds)
                timestamps = deque()
                self.requests_by_ip[client_ip] = timestamps

            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= self.max_requests:
                retry_after = max(1, ceil(timestamps[0] + self.window_seconds - now))
                return self._rate_limited_response(retry_after)

            timestamps.append(now)
            self.requests_by_ip.move_to_end(client_ip)

        return await call_next(request)

    def _limits_path(self, path: str) -> bool:
        return not self.path_prefixes or any(
            path.startswith(prefix) for prefix in self.path_prefixes
        )

    def _prune_inactive_clients(self, cutoff: float) -> None:
        while self.requests_by_ip:
            oldest_ip = next(iter(self.requests_by_ip))
            timestamps = self.requests_by_ip[oldest_ip]
            if timestamps and timestamps[-1] > cutoff:
                break
            self.requests_by_ip.popitem(last=False)

    @staticmethod
    def _rate_limited_response(retry_after: int) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again shortly."},
            headers={"Retry-After": str(retry_after)},
        )


class _RequestBodyTooLarge(Exception):
    pass


class RequestSizeLimitMiddleware:
    """Enforce body limits from Content-Length and streamed request chunks."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        default_max_bytes: int = DEFAULT_REQUEST_BODY_LIMIT,
        limits_by_path: dict[str, int] | None = None,
    ) -> None:
        if default_max_bytes <= 0:
            raise ValueError("default_max_bytes must be greater than zero")
        if limits_by_path and any(limit <= 0 for limit in limits_by_path.values()):
            raise ValueError("Request body limits must be greater than zero")
        self.app = app
        self.default_max_bytes = default_max_bytes
        self.limits_by_path = limits_by_path or {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        max_bytes = self.limits_by_path.get(scope["path"], self.default_max_bytes)
        content_length = self._content_length(scope)
        if content_length is not None and content_length > max_bytes:
            await self._too_large_response(scope, receive, send)
            return

        total_bytes = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal total_bytes
            message = await receive()
            if message["type"] == "http.request":
                total_bytes += len(message.get("body", b""))
                if total_bytes > max_bytes:
                    raise _RequestBodyTooLarge
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _RequestBodyTooLarge:
            if response_started:
                raise
            await self._too_large_response(scope, receive, send)

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        values = [value for key, value in scope["headers"] if key.lower() == b"content-length"]
        if len(values) != 1:
            return None
        try:
            value = int(values[0])
        except ValueError:
            return None
        return value if value >= 0 else None

    @staticmethod
    async def _too_large_response(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": "Request body is too large"},
        )
        await response(scope, receive, send)
