"""
backend/app/main.py
FastAPI application entrypoint.
"""

from __future__ import annotations
import os

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.logging_config import RequestLoggingMiddleware, configure_logging
from app.routers import review_queue  # your router from previous file

# ── Sentry (production error tracking) ───────────────────────────────────────
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[StarletteIntegration(), FastApiIntegration()],
    traces_sample_rate=0.2,       # 20% of requests traced for performance
    environment=os.getenv("ENV", "development"),
    send_default_pii=False,       # GDPR: no PII in error reports
)

# ── Logging ───────────────────────────────────────────────────────────────────
configure_logging()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Finance Monitor API",
    version="1.0.0",
    docs_url="/docs" if os.getenv("ENV") != "production" else None,
    redoc_url=None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logger
app.add_middleware(RequestLoggingMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(review_queue.router, prefix="/api/v1")
# Add more routers here: uploads, transactions, auth, etc.

# ── Health check (pinged by UptimeRobot every 5 min) ─────────────────────────
@app.get("/health", tags=["infra"])
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}
