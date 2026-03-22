import os
import asyncio
import logging
from groq import Groq
from utils.retry import parse_llm_json

logger = logging.getLogger(__name__)

# Token budget per reflection call (prompt + response):
# ~150 tokens prompt template + 120 chars claim + 120 chars reasoning + 300 chars passage + 250 output
# = ~550 tokens per call. At 6000 TPM, safe concurrency = 1 at a time with headroom for other agents.
_MAX_CLAIM_CHARS     = 200
_MAX_REASONING_CHARS = 200
_MAX_PASSAGE_CHARS   = 300

REFLECTION_PROMPT = """You concluded that the following claim is {verdict} with {confidence}% confidence.

CLAIM: {claim_text}
REASONING: {reasoning}
CITED PASSAGE: {cited_passage}

As a skeptical peer reviewer, give the 1-2 strongest reasons this verdict could be WRONG.
Consider: outdated sources, missing context, ambiguous wording, conflicting interpretations.

Rate critique strength 0 (verdict is solid) to 100 (verdict is questionable).

Return ONLY valid JSON:
{{"critique": "<1-2 sentences>", "critique_strength": <integer 0-100>}}"""


async def _call_reflection(verdict: dict) -> dict:
    """
    Single reflection call with no decorator retry wrapper.
    Groq's own SDK already handles 429 retries with correct retry-after headers.
    Adding our own retry_with_backoff on top causes doubled retry loops and
    compounds the TPM exhaustion problem rather than solving it.
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    loop = asyncio.get_running_loop()

    # Truncate all variable-length fields to keep each call under ~550 tokens.
    # This is the root cause of TPM exhaustion — long cited_passages from Tavily
    # can push a single call to 800+ tokens.
    claim_text    = str(verdict.get("claim_text",    "")).strip()[:_MAX_CLAIM_CHARS]
    reasoning     = str(verdict.get("reasoning",     "")).strip()[:_MAX_REASONING_CHARS]
    cited_passage = str(verdict.get("cited_passage", "")).strip()[:_MAX_PASSAGE_CHARS]
    verdict_str   = str(verdict.get("verdict",       "UNVERIFIABLE"))
    confidence    = int(verdict.get("confidence",    50))

    prompt = REFLECTION_PROMPT.format(
        verdict=verdict_str,
        confidence=confidence,
        claim_text=claim_text,
        reasoning=reasoning,
        cited_passage=cited_passage,
    )

    response = await loop.run_in_executor(None, lambda: client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=200,
    ))
    return parse_llm_json(response.choices[0].message.content, default={})


async def reflect_on_verdict(verdict: dict, claim: dict) -> dict:
    enriched = {**verdict, "claim_text": claim.get("claim_text", "")}
    try:
        result = await _call_reflection(enriched)
        critique = str(result.get("critique", "")).strip()
        # float() first — model sometimes returns "80.0" or 80.5
        raw_strength = result.get("critique_strength", 0)
        strength = max(0, min(100, int(float(raw_strength))))
    except Exception as e:
        logger.warning(f"Reflection failed for claim {verdict.get('claim_id', '?')}: {e}")
        critique = ""
        strength = 0
    return {
        **verdict,
        "self_reflection_critique": critique,
        "critique_strength": strength,
        "needs_recheck": strength > 60,
    }


async def reflect_all(verdicts: dict, claims: list) -> dict:
    """
    Runs reflections sequentially with a token-budget-aware stagger.

    Why sequential instead of asyncio.gather:
      - llama-3.1-8b-instant free tier: 6,000 TPM
      - Each reflection call: ~550 tokens
      - 12 claims concurrent = 6,600 tokens → guaranteed 429 storm
      - Sequential with stagger keeps us comfortably under the window

    Why 1.2s stagger (not 0.4s):
      - 6,000 TPM = 100 tokens/second budget
      - Each call = ~550 tokens → needs 5.5s to fully clear the window
      - But calls complete in ~1-2s, so the budget replenishes as we go
      - 1.2s between calls gives the TPM window time to partially recover
        while keeping total reflection time under 15s for 12 claims
      - Far more robust than 0.4s which still triggers 429s under load
    """
    claim_map = {c["claim_id"]: c for c in claims}
    updated = {}

    for i, v in enumerate(verdicts.values()):
        if i > 0:
            await asyncio.sleep(1.2)

        claim = claim_map.get(v["claim_id"], {"claim_text": ""})
        try:
            result = await reflect_on_verdict(v, claim)
            updated[result["claim_id"]] = result
        except Exception as e:
            # Never let a single reflection failure kill the whole pipeline.
            # The verdict is preserved as-is without critique.
            logger.warning(f"Reflection skipped for claim {v.get('claim_id', '?')}: {e}")
            updated[v["claim_id"]] = v

    # Preserve any verdicts not processed (defensive — shouldn't happen)
    for cid, v in verdicts.items():
        if cid not in updated:
            updated[cid] = v

    return updated