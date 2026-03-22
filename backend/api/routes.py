import uuid
import re
import asyncio
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from utils.scraper import scrape_url
from utils.validator import validate_input
from pipeline.graph import run_pipeline, get_session, create_session, sse_stream
from agents.classifier import classify_intent

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)

def _validate_session_id(session_id: str) -> str:
    if not _UUID_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    return session_id

class IngestRequest(BaseModel):
    type: str
    content: str

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in ("text", "url"):
            raise ValueError("type must be 'text' or 'url'")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("content cannot be empty")
        if len(v.encode("utf-8")) > 60 * 1024:
            raise ValueError("Content too large. Maximum is approximately 10,000 words.")
        return v

@router.post("/ingest")
@limiter.limit("10/minute;30/hour")
async def ingest(request: Request, req: IngestRequest, background_tasks: BackgroundTasks):
    session_id = str(uuid.uuid4())
    image_urls = []
    original_url = None

    if req.type == "url":
        try:
            scraped = await scrape_url(req.content)
            text = scraped["text"]
            image_urls = scraped.get("images", [])
            original_url = req.content
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Failed to scrape URL: {e}")
    else:
        text = req.content

    try:
        meta = validate_input(text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    intent = await classify_intent(text)
    if intent["category"] in ("INSUFFICIENT_FACTS", "OFF_TOPIC"):
        raise HTTPException(status_code=400, detail=f"Content rejected ({intent['category']}): {intent.get('reason', '')}")
    opinion_flag = (intent["category"] == "OPINION")

    create_session(session_id)
    background_tasks.add_task(run_pipeline, session_id=session_id, input_text=text,
        input_type=req.type, original_url=original_url, image_urls=image_urls,
        word_count=meta["word_count"], opinion_flag=opinion_flag)

    return {"session_id": session_id, "word_count": meta["word_count"],
        "estimated_time_seconds": meta["estimated_time_seconds"], "opinion_flag": opinion_flag, "status": "ok"}

@router.get("/stream/{session_id}")
@limiter.limit("20/minute")
async def stream(request: Request, session_id: str, last_event_id: int = Query(default=0, alias="lastEventId", ge=0)):
    session_id = _validate_session_id(session_id)
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    header_last = request.headers.get("Last-Event-ID")
    if header_last is not None:
        try:
            last_event_id = max(last_event_id, int(header_last))
        except ValueError:
            pass
    return StreamingResponse(sse_stream(session_id, last_event_index=last_event_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no", "Connection": "keep-alive", "Access-Control-Allow-Origin": "*"})

@router.get("/report/{session_id}")
@limiter.limit("30/minute")
async def get_report(request: Request, session_id: str):
    session_id = _validate_session_id(session_id)
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if session.get("status") == "pending":
        raise HTTPException(status_code=202, detail="Pipeline still running")
    if session.get("status") == "error":
        raise HTTPException(status_code=500, detail={"message": "Pipeline failed", "errors": session.get("errors", [])})
    report = session.get("report", {})
    safe_report = dict(report)
    safe_report["word_count"] = report.get("word_count", 0)
    return safe_report

@router.get("/health")
async def health():
    from pipeline.graph import _sessions
    return {"status": "ok", "service": "veritas-api", "active_sessions": len(_sessions)}