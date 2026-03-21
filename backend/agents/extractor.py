import os
import logging
import asyncio
import functools
from typing import List
from groq import Groq
from utils.retry import retry_with_backoff, parse_llm_json

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a precision claim extraction engine. Your sole task is to extract every verifiable atomic fact from the article text below.

STRICT RULES:
1. Each claim MUST be a single, standalone verifiable statement. Do NOT combine two facts with "and".
2. Extract ONLY objective, verifiable facts. Do NOT include:
   - Opinions or value judgments ("X is great", "Y is problematic")
   - Predictions or speculation ("X may cause Y", "experts believe")
   - Subjective assessments
3. Classify each claim as EXACTLY one of:
   - Temporal: time-sensitive facts (current officeholders, ongoing events, recent stats)
   - Statistical: numbers, percentages, quantities, measurements
   - Entity-State: current status of a person, organization, or thing
   - Historical-Fact: established past events, founding dates, historical records
4. Preserve the exact source sentence the claim came from.
5. Extract a MAXIMUM of 12 claims. Prioritize the most verifiable and important facts.
6. CRITICAL: If the text contains NO verifiable factual claims (e.g., purely opinion, fiction, or too short), you MUST return an empty array `[]`. Do NOT invent facts.
7. Return ONLY a valid JSON array. Zero preamble. Zero explanation. No markdown fences.

JSON SCHEMA (return this exact structure):
[
  {
    "claim_id": 1,
    "claim_text": "The exact verifiable claim as a clean standalone sentence",
    "claim_type": "Temporal|Statistical|Entity-State|Historical-Fact",
    "source_sentence": "The exact original sentence this claim came from"
  }
]

ARTICLE TEXT:
{article_text}"""


@retry_with_backoff(max_retries=2, base_delay=1.0)
async def _call_groq_extraction(article_text: str) -> str:
    """Call Groq API for claim extraction. Returns raw string response."""
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    loop = asyncio.get_running_loop()

    prompt = EXTRACTION_PROMPT.replace("{article_text}", article_text[:8000])

    response = await loop.run_in_executor(
        None,
        functools.partial(
            client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=3000,
        )
    )
    return response.choices[0].message.content


async def extract_claims(article_text: str) -> List[dict]:
    """
    Main entry point: extract and validate claims from article text.
    Returns a list of validated Claim dicts.
    Always returns a list (empty on failure, never raises).
    """
    try:
        raw = await _call_groq_extraction(article_text)
    except Exception as e:
        logger.error(f"Claim extraction API call failed: {e}")
        return []

    parsed = parse_llm_json(raw, default=[])

    if not isinstance(parsed, list):
        logger.error(f"Extraction returned non-list: {type(parsed)}")
        return []

    valid_claims = []
    valid_types = {"Temporal", "Statistical", "Entity-State", "Historical-Fact"}

    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue

        claim_text = str(item.get("claim_text", "")).strip()
        claim_type = str(item.get("claim_type", "Historical-Fact")).strip()
        source_sentence = str(item.get("source_sentence", "")).strip()

        if not claim_text or len(claim_text) < 10:
            continue
        if claim_type not in valid_types:
            claim_type = "Historical-Fact"

        valid_claims.append({
            "claim_id": len(valid_claims) + 1,
            "claim_text": claim_text,
            "claim_type": claim_type,
            "source_sentence": source_sentence or claim_text,
        })

    logger.info(f"Extracted {len(valid_claims)} valid claims from {len(article_text.split())} words")
    return valid_claims
