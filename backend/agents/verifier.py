import os
import asyncio
import logging
import functools
from groq import Groq
from utils.retry import retry_with_backoff, parse_llm_json
from utils.evidence_bundler import format_evidence_for_prompt

logger = logging.getLogger(__name__)

# ── Concurrency control ───────────────────────────────────────────────────────
# Groq free tier: llama-3.1-8b-instant — 6,000 TPM limit.
# Each verify_claim call makes one 8b request (~1,200 tokens).
# Semaphore(3): max 3 claims verifying simultaneously = 3,600 token burst < 6,000 TPM.
# Without this, 7+ concurrent claims = 8,400+ token burst → guaranteed 429 storm.
# The inner asyncio.gather (70b + 8b per claim) stays concurrent — they have
# separate rate limit pools and the parallelism saves ~2s per claim.
_VERIFY_SEMAPHORE = asyncio.Semaphore(3)

VERIFICATION_PROMPT = """You are a fact verification agent. Determine whether the CLAIM below is TRUE, FALSE, PARTIALLY TRUE, or UNVERIFIABLE based EXCLUSIVELY on the EVIDENCE provided.

ABSOLUTE RULES:
1. Your verdict MUST be based SOLELY on the EVIDENCE TEXT below. Your own training knowledge is INADMISSIBLE.
2. You MUST quote a specific verbatim passage from the EVIDENCE that justifies your verdict.
3. If you cannot find a specific passage to quote, your verdict MUST be UNVERIFIABLE. No exceptions.
4. Return ONLY valid JSON. Zero preamble. Zero explanation outside the JSON.

CLAIM: {claim_text}
CLAIM TYPE: {claim_type}

EVIDENCE:
{evidence_text}

Return EXACTLY this JSON schema:
{{
  "verdict": "TRUE" or "FALSE" or "PARTIALLY TRUE" or "UNVERIFIABLE",
  "precision": "EXACT" or "APPROXIMATE" or "MISLEADING" or "N/A",
  "confidence": <integer 0-100>,
  "cited_passage": "<exact quote from evidence above, or 'No supporting passage found'>",
  "reasoning": "<1-2 sentence explanation referencing the evidence>",
  "source_url": "<URL of the cited source, or empty string>"
}}"""

VALID_VERDICTS = {"TRUE", "FALSE", "PARTIALLY TRUE", "UNVERIFIABLE"}


@retry_with_backoff(max_retries=2, base_delay=1.0)
async def _verify_with_groq_alt(claim_text, claim_type, evidence_text):
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    prompt = VERIFICATION_PROMPT.format(
        claim_text=claim_text,
        claim_type=claim_type,
        evidence_text=evidence_text[:6000],
    )
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, lambda: client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1, max_tokens=600,
    ))
    return parse_llm_json(response.choices[0].message.content, default={})


@retry_with_backoff(max_retries=2, base_delay=1.0)
async def _verify_with_groq(claim_text, claim_type, evidence_text):
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    prompt = VERIFICATION_PROMPT.format(
        claim_text=claim_text,
        claim_type=claim_type,
        evidence_text=evidence_text[:6000],
    )
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, lambda: client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1, max_tokens=600,
    ))
    return parse_llm_json(response.choices[0].message.content, default={})


def _normalize_verdict(raw: dict) -> dict:
    verdict = str(raw.get("verdict", "UNVERIFIABLE")).upper().strip()
    if verdict not in VALID_VERDICTS:
        verdict = "UNVERIFIABLE"
    cited = str(raw.get("cited_passage", "")).strip()
    if not cited or cited.lower() in {"", "none", "n/a", "no supporting passage found"}:
        verdict = "UNVERIFIABLE"
        cited = "No supporting passage found"
    precision = str(raw.get("precision", "N/A")).upper().strip()
    if precision not in {"EXACT", "APPROXIMATE", "MISLEADING", "N/A"}:
        precision = "N/A"
    if verdict == "UNVERIFIABLE":
        precision = "N/A"
    return {
        "verdict":       verdict,
        "precision":     precision,
        "confidence":    max(0, min(100, int(float(raw.get("confidence", 50))))),
        "cited_passage": cited,
        "reasoning":     str(raw.get("reasoning", "")).strip(),
        "source_url":    str(raw.get("source_url", "")).strip(),
    }


def _calculate_confidence_and_drift(m1, m2, jury_agreed, sources_raw, claim_type):
    sources = sources_raw[:3] if sources_raw else []
    base = (m1["confidence"] + m2["confidence"]) / 2
    jury_bonus = 10 if jury_agreed else -10
    authority_scores = [float(s.get("authority_score", 0.4)) for s in sources]
    authority_multiplier = (sum(authority_scores) / max(len(authority_scores), 1)) * 20
    recency_bonus = 0
    for s in sources:
        pub = s.get("publish_date", "")
        if pub and any(y in pub for y in ("2024", "2025", "2026")):
            recency_bonus = 5
            break
    temporal_drift_flag = False
    temporal_penalty = 0
    if "Temporal" in claim_type:
        if sources:
            best_pub = sources[0].get("publish_date", "")
            if best_pub and not any(y in best_pub for y in ("2025", "2026")):
                temporal_drift_flag = True
                temporal_penalty = -15
    final = base + jury_bonus + authority_multiplier + recency_bonus + temporal_penalty
    return max(0, min(100, int(final))), temporal_drift_flag


async def verify_claim(claim: dict, bundle: dict) -> dict:
    claim_id   = claim.get("claim_id", "Unknown")
    claim_text = str(claim.get("claim_text", ""))
    claim_type = str(claim.get("claim_type", "Historical Fact"))
    sources    = bundle.get("sources", [])
    evidence_text = format_evidence_for_prompt(bundle)

    # return_exceptions=True means exceptions are returned as values, never raised.
    # No try/except needed here — exceptions are handled by isinstance checks below.
    groq_alt_raw, groq_raw = await asyncio.gather(
        _verify_with_groq_alt(claim_text, claim_type, evidence_text),
        _verify_with_groq(claim_text, claim_type, evidence_text),
        return_exceptions=True,
    )

    # Classify each result: successful dict vs exception/failure
    alt_ok = isinstance(groq_alt_raw, dict) and groq_alt_raw
    main_ok = isinstance(groq_raw, dict) and groq_raw

    # Both models failed — return confident zero, not ambiguous 50
    if not alt_ok and not main_ok:
        return _unverifiable_verdict(claim_id, sources, "Both verification models failed")

    m1_raw = groq_alt_raw if alt_ok else {}
    m2_raw = groq_raw     if main_ok else {}
    m1 = _normalize_verdict(m1_raw)
    m2 = _normalize_verdict(m2_raw)

    # One model failed: use only the working model, don't label it CONTESTED
    # (CONTESTED means the two models genuinely disagreed, not that one errored)
    if not alt_ok:
        logger.warning(f"Claim {claim_id}: 8b model failed, using 70b result only")
        jury_agreed = True  # only one verdict — no disagreement possible
        primary     = m2
    elif not main_ok:
        logger.warning(f"Claim {claim_id}: 70b model failed, using 8b result only")
        jury_agreed = True
        primary     = m1
    else:
        jury_agreed = (m1["verdict"] == m2["verdict"])
        primary     = m1  # 8b is primary (faster, used as first juror)

    final_verdict = primary["verdict"] if jury_agreed else "CONTESTED"
    confidence, drift_flag = _calculate_confidence_and_drift(m1, m2, jury_agreed, sources, claim_type)

    return {
        "claim_id":               claim_id,
        "verdict":                final_verdict,
        "precision":              primary.get("precision", "N/A"),
        "confidence":             confidence,
        "temporal_drift_flag":    drift_flag,
        "cited_passage":          primary["cited_passage"],
        "reasoning":              primary["reasoning"],
        "source_url":             primary["source_url"],
        "jury_agreed":            jury_agreed,
        "model_1_verdict":        m1["verdict"],
        "model_2_verdict":        m2["verdict"],
        "model_1_confidence":     m1["confidence"],
        "model_2_confidence":     m2["confidence"],
        "conflict_flag":          False,
        "self_reflection_critique": "",
        "critique_strength":      0,
        "all_sources":            sources,
        "retry_count":            0,
    }


def _unverifiable_verdict(claim_id, sources, reason):
    return {
        "claim_id":               claim_id,
        "verdict":                "UNVERIFIABLE",
        "precision":              "N/A",
        "confidence":             0,
        "temporal_drift_flag":    False,
        "cited_passage":          "No supporting passage found",
        "reasoning":              reason,
        "source_url":             "",
        "jury_agreed":            False,
        "model_1_verdict":        "UNVERIFIABLE",
        "model_2_verdict":        "UNVERIFIABLE",
        "model_1_confidence":     0,
        "model_2_confidence":     0,
        "conflict_flag":          False,
        "self_reflection_critique": "",
        "critique_strength":      0,
        "all_sources":            sources,
        "retry_count":            0,
    }


async def verify_all_claims(claims: list, evidence_bundles: dict) -> dict:
    """
    Verify all claims with bounded concurrency.

    Why semaphore(3) and not asyncio.gather(*all):
      - Each verify_claim makes one llama-3.1-8b-instant call (~1,200 tokens)
      - Free tier limit: 6,000 TPM
      - 7 claims × 1,200 = 8,400 tokens burst → guaranteed 429 storm
      - Semaphore(3): max 3,600 token burst at any moment → under the limit
      - ceil(7/3) = 3 batches × ~3s each ≈ 9s total vs 140s of retries

    The inner asyncio.gather (70b + 8b) inside verify_claim is intentionally
    kept concurrent — those two models have separate rate limit pools.
    """
    async def _verify_one(claim):
        async with _VERIFY_SEMAPHORE:
            bundle = evidence_bundles.get(claim["claim_id"], {"sources": [], "structured_facts": []})
            try:
                return await verify_claim(claim, bundle)
            except Exception as e:
                return _unverifiable_verdict(claim["claim_id"], [], str(e))

    results = await asyncio.gather(*[_verify_one(c) for c in claims], return_exceptions=True)
    verdicts = {}
    for r in results:
        if isinstance(r, BaseException):
            continue
        if isinstance(r, dict):
            verdicts[r["claim_id"]] = r
    return verdicts