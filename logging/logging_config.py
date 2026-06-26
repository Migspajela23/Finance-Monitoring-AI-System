"""
backend/app/core/logging_config.py
Structured JSON logging for FastAPI.
- Local dev: colored console output
- Production: JSON → Logtail (Better Stack)
- AI API failures get special structured fields for alerting
"""

from __future__ import annotations
import logging
import os
import sys
import time
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# ── Logtail handler (production) ─────────────────────────────────────────────
def _get_logtail_handler() -> logging.Handler | None:
    token = os.getenv("LOGTAIL_TOKEN")
    if not token:
        return None
    try:
        from logtail import LogtailHandler  # pip install logtail-python
        handler = LogtailHandler(source_token=token)
        handler.setLevel(logging.INFO)
        return handler
    except ImportError:
        return None


# ── Structlog setup ───────────────────────────────────────────────────────────
def configure_logging() -> None:
    is_production = os.getenv("ENV", "development") == "production"

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if is_production:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
        renderer = logging.StreamHandler(sys.stdout)
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
        renderer = logging.StreamHandler(sys.stdout)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Standard logging → structlog bridge
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(renderer)

    logtail = _get_logtail_handler()
    if logtail:
        root_logger.addHandler(logtail)

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ── Request logging middleware ────────────────────────────────────────────────
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and latency."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        log = structlog.get_logger()

        # Bind request context so all logs within this request include these fields
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            method=request.method,
            path=request.url.path,
            request_id=request.headers.get("x-request-id", "-"),
        )

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        log.info(
            "request",
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response


# ── AI API logging helper ─────────────────────────────────────────────────────
class AILogger:
    """
    Structured logger for Gemini API calls.
    Use this wherever you call Gemini so failures are queryable in Logtail.
    """

    def __init__(self) -> None:
        self._log = structlog.get_logger("ai.gemini")
        self.LATENCY_THRESHOLD_MS = 2000

    def log_success(
        self,
        upload_id: str,
        latency_ms: float,
        confidence: float,
    ) -> None:
        level = "warn" if latency_ms > self.LATENCY_THRESHOLD_MS else "info"
        getattr(self._log, level)(
            "gemini_extraction_success",
            upload_id=upload_id,
            latency_ms=round(latency_ms, 2),
            confidence=round(confidence, 4),
            slow=latency_ms > self.LATENCY_THRESHOLD_MS,
        )

    def log_failure(
        self,
        upload_id: str,
        error: str,
        latency_ms: float,
        retry_count: int = 0,
    ) -> None:
        self._log.error(
            "gemini_extraction_failed",
            upload_id=upload_id,
            error=error,
            latency_ms=round(latency_ms, 2),
            retry_count=retry_count,
            alert=True,   # field used to trigger Logtail alert rule
        )

    def log_rate_limit(self, upload_id: str, retry_after: int) -> None:
        self._log.warning(
            "gemini_rate_limited",
            upload_id=upload_id,
            retry_after_seconds=retry_after,
            alert=True,
        )


ai_logger = AILogger()
