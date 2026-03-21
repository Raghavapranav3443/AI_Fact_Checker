import os
import asyncio
import logging
import functools
from typing import List
from groq import Groq
from utils.retry import retry_with_backoff, parse_llm_json

logger = logging.getLogger(__name__)

import json

BATCH_QUERY_GEN_PROMPT = """Generate search queries to fact-check multiple claims at once.
For each claim, generate EXACTLY 3 query types:
1. DIRECT: A straightforward query to find evidence confirming or explaining the claim.
2. ADVERSARIAL: A query specifically designed to find counter-evidence, corrections, or debunking.
3. CONTEXTUAL: A query adding temporal/topical context.

CLAIMS:
{claims_json}

Return ONLY a JSON object mapping each claim_id to a list of its 3 query strings. No preamble. No markdown blocks.
Example:
{{
  "1": ["direct query", "adversarial query", "contextual query"],
  "2": ["...", "...", "..."]
}}"""

@retry_with_backoff(max_retries=1, base_delay=0.5)
async def _call_batch_groq_queries(claims: List[dict]) -> str:
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    loop = asyncio.get_running_loop()
    
    # Simplify for token efficiency
    simplified = [
        {"claim_id": c["claim_id"], "claim_text": c["claim_text"], "type": c.get("claim_type", "")}
        for c in claims
    ]
    prompt = BATCH_QUERY_GEN_PROMPT.format(claims_json=json.dumps(simplified))
    
    response = await loop.run_in_executor(
        None,
        functools.partial(
            client.chat.completions.create,
            model="llama-3.1-8b-instant",  # fast model for simple task
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000,
        )
    )
    return response.choices[0].message.content

def _heuristic_fallback(claim_text: str) -> List[str]:
    short = claim_text[:80]
    return [
        short,
        f"{short} false incorrect wrong",
        f"{short} fact check verification",
    ]

async def generate_all_queries(claims: List[dict]) -> dict:
    """
    Generate queries for all claims concurrently using a single batch request.
    Returns dict: { claim_id -> [q1, q2, q3] }
    """
    if not claims:
        return {}

    try:
        raw = await _call_batch_groq_queries(claims)
        parsed = parse_llm_json(raw, default={})

        if isinstance(parsed, dict) and len(parsed) > 0:
            query_map = {}
            for claim in claims:
                cid = str(claim["claim_id"])
                # Extract valid queries from the batch response
                if cid in parsed and isinstance(parsed[cid], list):
                    valid_qs: list[str] = [str(q).strip() for q in parsed[cid] if str(q).strip() and len(str(q)) > 5]
                    if len(valid_qs) >= 2:
                        query_map[claim["claim_id"]] = valid_qs[:3]
                        continue
                
                # If specific claim is missing or invalid in batch, fallback
                logger.warning(f"Query gen missed claim {cid}, using heuristic.")
                query_map[claim["claim_id"]] = _heuristic_fallback(claim["claim_text"])
            
            return query_map

    except Exception as e:
        logger.warning(f"Batch query generation failed, falling back to heuristics: {e}")

    # Complete global fallback if API call fails entirely
    return {c["claim_id"]: _heuristic_fallback(c["claim_text"]) for c in claims}

# Backward compatibility wrapper for legacy tools and tests
async def generate_queries(claim_text: str, claim_type: str = "") -> List[str]:
    """Legacy single-claim entry point."""
    claims = [{"claim_id": "legacy_compat", "claim_text": claim_text, "claim_type": claim_type}]
    res = await generate_all_queries(claims)
    return res.get("legacy_compat", _heuristic_fallback(claim_text))
