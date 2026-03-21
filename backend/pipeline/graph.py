import os
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import AsyncGenerator

from agents.extractor import extract_claims
from agents.query_generator import generate_all_queries
from agents.verifier import verify_all_claims, verify_claim
from agents.reflector import reflect_all
from agents.conflict_detector import detect_conflicts
from agents.ai_detector import detect_ai_text
from agents.media_detector import detect_media
from utils.tavily_search import search_parallel
from utils.knowledge_apis import query_all_knowledge_apis
from utils.evidence_bundler import build_evidence_bundle

logger = logging.getLogger(__name__)

# ── Session store with TTL eviction ───────────────────────────────────────────
# Each entry: { status, report, errors, created_at, event_log }
_sessions: dict = {}
_sse_queues: dict = {}

SESSION_TTL_SECONDS = 3600        # 1 hour
MAX_SESSIONS        = 500         # hard cap — evict oldest when exceeded
SESSION_CLEANUP_EVERY = 50        # run eviction every N creates


def _evict_old_sessions():
    """Remove sessions older than TTL or if over MAX_SESSIONS cap."""
    now = time.time()
    expired = [
        sid for sid, s in _sessions.items()
        if now - s.get("created_at", 0) > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _sessions.pop(sid, None)
        _sse_queues.pop(sid, None)

    # Hard cap: evict oldest if still over limit
    if len(_sessions) > MAX_SESSIONS:
        sorted_ids = sorted(_sessions, key=lambda s: _sessions[s].get("created_at", 0))
        for sid in sorted_ids[:len(_sessions) - MAX_SESSIONS]:
            _sessions.pop(sid, None)
            _sse_queues.pop(sid, None)


_create_count = [0]

def get_session(session_id: str) -> dict | None:
    s = _sessions.get(session_id)
    if s is None:
        return None
    # Lazy TTL check on read
    if time.time() - s.get("created_at", 0) > SESSION_TTL_SECONDS:
        _sessions.pop(session_id, None)
        _sse_queues.pop(session_id, None)
        return None
    return s


def create_session(session_id: str):
    _create_count[0] += 1
    if _create_count[0] % SESSION_CLEANUP_EVERY == 0:
        _evict_old_sessions()

    _sessions[session_id] = {
        "status": "pending",
        "report": None,
        "errors": [],
        "created_at": time.time(),
        "event_log": [],        # replay buffer for SSE reconnects
    }
    _sse_queues[session_id] = asyncio.Queue(maxsize=200)


async def emit(session_id: str, event: dict):
    """Emit SSE event: put on queue AND append to replay log."""
    session = _sessions.get(session_id)
    if session is not None:
        session["event_log"].append(event)   # for reconnect replay

    q = _sse_queues.get(session_id)
    if q:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(f"SSE queue full for session {session_id} — dropping event")


async def sse_stream(session_id: str, last_event_index: int = 0) -> AsyncGenerator[str, None]:
    """
    SSE stream with reconnect support via Last-Event-ID.
    Replays missed events on reconnect, then continues live.
    """
    session: dict | None = _sessions.get(session_id)
    q: asyncio.Queue | None = _sse_queues.get(session_id)
    if q is None or session is None:
        yield f"data: {json.dumps({'stage': 'error', 'message': 'Session not found'})}\n\n"
        return

    # Replay any events missed before reconnect
    event_log = session.get("event_log", [])
    for i, event in enumerate(event_log[last_event_index:], start=last_event_index):
        yield f"id: {i}\ndata: {json.dumps(event)}\n\n"
        if event.get("stage") in ("report_complete", "error"):
            return

    # If pipeline already finished, we're done
    if session.get("status") in ("complete", "error"):
        return

    # Live streaming
    event_index: int = int(len(event_log))
    while True:
        try:
            event = await asyncio.wait_for(q.get(), timeout=30.0)
            yield f"id: {event_index}\ndata: {json.dumps(event)}\n\n"
            event_index += 1
            if event.get("stage") in ("report_complete", "error"):
                break
        except asyncio.TimeoutError:
            yield ": heartbeat\n\n"   # SSE comment — keeps connection alive, not parsed by client


async def run_pipeline(
    session_id: str,
    input_text: str,
    input_type: str,
    original_url: str | None = None,
    image_urls: list | None = None,
    word_count: int = 0,
    opinion_flag: bool = False,
):
    """
    Main pipeline orchestrator. Rule C-1: never blocks on single failure.
    """
    image_urls = image_urls or []
    errors = []

    # ── DEMO CACHE MODE (Rule E-1) ─────────────────────────────────────────
    if os.getenv("DEMO_CACHE_MODE", "false").lower() == "true":
        try:
            from utils.demo_cache import DEMO_SCENARIOS, load_cached_report
            matched_report = None
            for scenario in DEMO_SCENARIOS:
                if scenario["content"][:80].strip() == input_text[:80].strip():
                    matched_report = load_cached_report(scenario["id"])
                    break
            if not matched_report:
                matched_report = load_cached_report(DEMO_SCENARIOS[0]["id"])
            if matched_report:
                matched_report["session_id"] = session_id
                matched_report["opinion_flag"] = opinion_flag
                _sessions[session_id]["status"] = "complete"
                _sessions[session_id]["report"] = matched_report
                await emit(session_id, {"stage": "extraction_complete",
                    "claim_count": len(matched_report.get("claims", [])),
                    "claims": matched_report.get("claims", [])})
                await asyncio.sleep(0.3)
                for claim in matched_report.get("claims", []):
                    cid = claim["claim_id"]
                    await emit(session_id, {"stage": "evidence_retrieved", "claim_id": cid,
                        "source_count": len(claim.get("all_sources", []))})
                    await emit(session_id, {"stage": "verdict_ready", "claim_id": cid,
                        "verdict": claim.get("verdict"), "confidence": claim.get("confidence"),
                        "conflict_flag": claim.get("conflict_flag", False)})
                    await asyncio.sleep(0.05)
                await asyncio.sleep(0.3)
                await emit(session_id, {"stage": "report_complete", "report": matched_report})
                logger.info(f"Demo cache mode: served session {session_id}")
                return
        except Exception as e:
            logger.warning(f"Demo cache failed, using live pipeline: {e}")

    try:
        # ── STAGE 1: Claim Extraction ──────────────────────────────────────
        await emit(session_id, {"stage": "extracting", "message": "Extracting claims..."})
        try:
            claims = await extract_claims(input_text)
        except Exception as e:
            errors.append(f"Extraction failed: {e}")
            claims = []

        if not claims:
            await emit(session_id, {"stage": "error",
                "message": "Could not extract any verifiable claims from this text.",
                "recoverable": False})
            _sessions[session_id]["status"] = "error"
            _sessions[session_id]["errors"] = errors
            return

        await emit(session_id, {"stage": "extraction_complete",
            "claim_count": len(claims), "claims": claims})

        # ── STAGE 2: Evidence Retrieval ────────────────────────────────────
        await emit(session_id, {"stage": "retrieving", "message": "Retrieving evidence..."})
        try:
            query_map = await generate_all_queries(claims)
        except Exception as e:
            errors.append(f"Query generation failed: {e}")
            query_map = {c["claim_id"]: [c["claim_text"]] for c in claims}

        async def retrieve_for_claim(claim):
            cid = claim["claim_id"]
            queries = query_map.get(cid, [claim["claim_text"]])
            try:
                tavily_sources, kb_facts = await asyncio.gather(
                    search_parallel(queries),
                    query_all_knowledge_apis(claim["claim_text"], claim["claim_type"]),
                    return_exceptions=True
                )
                if isinstance(tavily_sources, BaseException):
                    tavily_sources = []
                if isinstance(kb_facts, BaseException):
                    kb_facts = []
            except Exception as e:
                errors.append(f"Evidence retrieval failed for claim {cid}: {e}")
                tavily_sources, kb_facts = [], []
            bundle = build_evidence_bundle(cid, tavily_sources, kb_facts, queries)
            await emit(session_id, {"stage": "evidence_retrieved", "claim_id": cid,
                "source_count": len(tavily_sources), "queries": queries})
            return cid, bundle

        retrieval_results = await asyncio.gather(
            *[retrieve_for_claim(c) for c in claims], return_exceptions=True)
        evidence_bundles = {}
        for r in retrieval_results:
            if isinstance(r, BaseException):
                errors.append(f"Retrieval error: {r}")
                continue
            cid, bundle = r
            evidence_bundles[cid] = bundle

        # ── STAGE 3: Verification Jury ─────────────────────────────────────
        await emit(session_id, {"stage": "verifying", "message": "Verifying claims..."})
        try:
            verdicts = await verify_all_claims(claims, evidence_bundles)
        except Exception as e:
            errors.append(f"Verification failed: {e}")
            verdicts = {}

        # Re-search contested claims
        contested = [
            c for c in claims
            if verdicts.get(c["claim_id"], {}).get("verdict") == "CONTESTED"
            and verdicts.get(c["claim_id"], {}).get("retry_count", 0) < 2
        ]
        for claim in contested:
            cid = claim["claim_id"]
            try:
                extra_q = claim["claim_text"][:120]
                extra = await search_parallel([extra_q])
                if extra:
                    old = evidence_bundles.get(cid, {"sources": [], "structured_facts": [], "queries_used": []})
                    merged = sorted(old["sources"] + extra, key=lambda x: x.get("authority_score", 0), reverse=True)
                    evidence_bundles[cid] = {**old, "sources": merged[:5]}
                    new_v = await verify_claim(claim, evidence_bundles[cid])
                    new_v["retry_count"] = verdicts[cid].get("retry_count", 0) + 1
                    verdicts[cid] = new_v
            except Exception as e:
                errors.append(f"Re-search failed for claim {cid}: {e}")

        for cid, v in verdicts.items():
            await emit(session_id, {"stage": "verdict_ready", "claim_id": cid,
                "verdict": v["verdict"], "confidence": v["confidence"],
                "conflict_flag": v.get("conflict_flag", False)})

        # ── STAGE 4: Self-Reflection ───────────────────────────────────────
        try:
            verdicts = await reflect_all(verdicts, claims)
        except Exception as e:
            errors.append(f"Reflection failed: {e}")

        for cid, v in verdicts.items():
            if v.get("needs_recheck") and v.get("retry_count", 0) < 2:
                claim = next((c for c in claims if c["claim_id"] == cid), None)
                if claim:
                    try:
                        extra_q = f"{claim['claim_text']} {v.get('self_reflection_critique', '')}"[:120]
                        extra = await search_parallel([extra_q])
                        if extra:
                            old = evidence_bundles.get(cid, {"sources": [], "structured_facts": [], "queries_used": []})
                            merged = sorted(old["sources"] + extra, key=lambda x: x.get("authority_score", 0), reverse=True)
                            evidence_bundles[cid] = {**old, "sources": merged[:5]}
                            new_v = await verify_claim(claim, evidence_bundles[cid])
                            new_v["retry_count"] = v.get("retry_count", 0) + 1
                            new_v["self_reflection_critique"] = v["self_reflection_critique"]
                            new_v["critique_strength"] = v["critique_strength"]
                            verdicts[cid] = new_v
                    except Exception as e:
                        errors.append(f"Post-reflection re-verify failed for claim {cid}: {e}")

        # ── STAGE 5: Conflict Detection ────────────────────────────────────
        for claim in claims:
            cid = claim["claim_id"]
            if cid in verdicts:
                verdicts[cid]["claim_text"] = claim["claim_text"]
        try:
            conflicts = detect_conflicts(verdicts, evidence_bundles)
        except Exception as e:
            errors.append(f"Conflict detection failed: {e}")
            conflicts = []

        # ── STAGE 6: AI + Media Detection ─────────────────────────────────
        await emit(session_id, {"stage": "analyzing", "message": "Analysing content..."})
        try:
            ai_detection = await detect_ai_text(input_text)
        except Exception as e:
            errors.append(f"AI detection failed: {e}")
            ai_detection = None

        media_results = []
        if image_urls:
            try:
                media_results = await detect_media(image_urls)
            except Exception as e:
                errors.append(f"Media detection failed: {e}")

        # ── STAGE 7: Assemble Report ───────────────────────────────────────
        claim_map = {c["claim_id"]: c for c in claims}
        merged_claims = []
        for cid, v in verdicts.items():
            claim = claim_map.get(cid, {})
            merged = {**claim, **v}
            bundle = evidence_bundles.get(cid, {})
            merged["all_sources"] = bundle.get("sources", [])
            merged["structured_facts"] = bundle.get("structured_facts", [])
            merged["queries_used"] = bundle.get("queries_used", [])
            merged_claims.append(merged)
        merged_claims.sort(key=lambda x: x.get("claim_id", 0))

        verdict_counts = {"TRUE": 0, "FALSE": 0, "PARTIALLY TRUE": 0, "UNVERIFIABLE": 0, "CONTESTED": 0}
        for v in verdicts.values():
            vtype = v.get("verdict", "UNVERIFIABLE")
            verdict_counts[vtype] = verdict_counts.get(vtype, 0) + 1

        weight_map = {"TRUE": 100, "PARTIALLY TRUE": 60, "CONTESTED": 40, "UNVERIFIABLE": 30, "FALSE": 0}
        if verdicts:
            raw_scores = [
                (v.get("confidence", 50) * weight_map.get(v.get("verdict", "UNVERIFIABLE"), 30)) / 100
                for v in verdicts.values()
            ]
            overall_trust = int(sum(raw_scores) / len(raw_scores))
        else:
            overall_trust = 0

        report = {
            "session_id": session_id,
            "input_text": input_text,
            "word_count": word_count,
            "opinion_flag": opinion_flag,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "overall_trust_score": overall_trust,
            "claim_breakdown": verdict_counts,
            "claims": merged_claims,
            "conflicts": conflicts,
            "ai_text_detection": ai_detection,
            "media_detection": media_results,
            "errors": errors,
        }

        _sessions[session_id]["status"] = "complete"
        _sessions[session_id]["report"] = report
        _sessions[session_id]["errors"] = errors
        await emit(session_id, {"stage": "report_complete", "report": report})
        logger.info(f"Pipeline complete for session {session_id}: {len(claims)} claims, trust={overall_trust}")

    except Exception as e:
        logger.error(f"Pipeline fatal error for session {session_id}: {e}", exc_info=True)
        errors.append(f"Fatal pipeline error: {e}")
        _sessions[session_id]["status"] = "error"
        _sessions[session_id]["errors"] = errors
        await emit(session_id, {"stage": "error", "message": str(e), "recoverable": False})
