import os
import asyncio
import logging
from groq import Groq
from utils.retry import retry_with_backoff, parse_llm_json

logger = logging.getLogger(__name__)

REFLECTION_PROMPT = """You just concluded that the following claim is {verdict} with {confidence}% confidence.

CLAIM: {claim_text}
YOUR REASONING: {reasoning}
CITED PASSAGE: {cited_passage}

Now act as a skeptical peer reviewer. What are the 1-2 strongest reasons this verdict could be WRONG?
Consider: outdated sources, missing context, ambiguous wording, conflicting interpretations, or edge cases.

Rate the strength of your critique from 0 (trivial, verdict is solid) to 100 (compelling, verdict is questionable).

Return ONLY valid JSON:
{{"critique": "<1-2 sentences describing the strongest counter-argument>", "critique_strength": <0-100>}}"""


@retry_with_backoff(max_retries=2, base_delay=0.5)
async def _call_reflection(verdict: dict) -> dict:
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    loop = asyncio.get_running_loop()
    prompt = REFLECTION_PROMPT.format(
        verdict=verdict["verdict"],
        confidence=verdict["confidence"],
        claim_text=verdict.get("claim_text", ""),
        reasoning=verdict.get("reasoning", ""),
        cited_passage=verdict.get("cited_passage", ""),
    )
    response = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=250,
        )
    )
    return parse_llm_json(response.choices[0].message.content, default={})


async def reflect_on_verdict(verdict: dict, claim: dict) -> dict:
    """
    Run self-reflection on a verdict. Updates verdict with critique fields.
    If critique_strength > 60, marks needs_recheck=True for the pipeline.
    Never raises.
    """
    enriched = {**verdict, "claim_text": claim["claim_text"]}

    try:
        result = await _call_reflection(enriched)
        critique = str(result.get("critique", "")).strip()
        strength = max(0, min(100, int(result.get("critique_strength", 0))))
    except Exception as e:
        logger.warning(f"Reflection failed for claim {verdict['claim_id']}: {e}")
        critique = ""
        strength = 0

    updated = {
        **verdict,
        "self_reflection_critique": critique,
        "critique_strength": strength,
        "needs_recheck": strength > 60,
    }

    if strength > 60:
        logger.info(
            f"Claim {verdict['claim_id']}: strong critique (strength={strength}), "
            f"flagging for re-search. Critique: {critique[:100]}"
        )

    return updated


async def reflect_all(verdicts: dict, claims: list) -> dict:
    """
    Run reflection on all verdicts concurrently.
    Returns updated verdicts dict.
    """
    claim_map = {c["claim_id"]: c for c in claims}

    async def _reflect_one(v):
        claim = claim_map.get(v["claim_id"], {"claim_text": ""})
        return await reflect_on_verdict(v, claim)

    results = await asyncio.gather(
        *[_reflect_one(v) for v in verdicts.values()],
        return_exceptions=True
    )

    updated = {}
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Reflection gather exception: {r}")
            continue
        updated[r["claim_id"]] = r

    # Keep any verdicts that failed reflection unchanged
    for cid, v in verdicts.items():
        if cid not in updated:
            updated[cid] = v

    return updated
