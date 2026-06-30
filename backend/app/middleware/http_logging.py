import logging
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class HttpLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started_at = time.perf_counter()
        client_host = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        logger.info("HTTP request started method=%s path=%s client=%s", method, path, client_host)

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                "HTTP request failed method=%s path=%s client=%s duration_ms=%s",
                method,
                path,
                client_host,
                elapsed_ms,
            )
            raise

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "HTTP request completed method=%s path=%s status=%s duration_ms=%s client=%s",
            method,
            path,
            response.status_code,
            elapsed_ms,
            client_host,
        )
        return response
