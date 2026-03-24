import logging
import os
import sys
import asyncio

if sys.platform == 'win32':
    # Playwright requires ProactorEventLoop to launch subprocesses on Windows.
    # We set this policy BEFORE the loop is started by uvicorn.
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import time
import uuid
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Silence noisy third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("groq").setLevel(logging.WARNING)
logging.getLogger("slowapi").setLevel(logging.WARNING)
# If in production/silent mode, even our own loggers should be quiet
if LOG_LEVEL in ("ERROR", "CRITICAL"):
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)

from api.routes import router

# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Veritas API",
    version="1.0.0",
    # Disable automatic OpenAPI in production — comment out for dev
    # docs_url=None, redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ───────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,        # no cookies needed
    allow_methods=["GET", "POST"],   # explicit — not wildcard
    allow_headers=["Content-Type", "Accept"],
)

# ── Security headers middleware ────────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]    = "nosniff"
    response.headers["X-Frame-Options"]           = "DENY"
    response.headers["X-XSS-Protection"]          = "1; mode=block"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]        = "geolocation=(), microphone=(), camera=()"
    # CSP: tight for API — no HTML served so mainly guards error pages
    response.headers["Content-Security-Policy"]   = "default-src 'none'; frame-ancestors 'none'"
    # Remove server fingerprinting
    try:
        del response.headers["server"]
    except KeyError:
        pass
    return response

# ── Request ID + timing middleware ────────────────────────────────────────────
@app.middleware("http")
async def request_id_and_timing(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response = await call_next(request)
    duration = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration:.1f}ms"
    logger.info(f"[{request_id}] {request.method} {request.url.path} → {response.status_code} ({duration:.0f}ms)")
    return response

# ── Request body size limit ────────────────────────────────────────────────────
MAX_BODY_SIZE = 1 * 1024 * 1024  # 1MB — more than enough for 10k words

@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"detail": f"Request body too large. Maximum is {MAX_BODY_SIZE // 1024}KB."},
        )
    return await call_next(request)

app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    return {"service": "Veritas Trust Intelligence Platform", "version": "1.0.0"}
