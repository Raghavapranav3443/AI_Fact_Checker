import os
import re
import math
import asyncio
import logging
from groq import Groq
from utils.retry import retry_with_backoff, parse_llm_json

logger = logging.getLogger(__name__)

PERPLEXITY_PROMPT = """Rate each sentence below on how PREDICTABLE it is for an AI language model to generate.
Score 1 = highly predictable / generic / AI-like phrasing
Score 10 = surprising / idiosyncratic / distinctly human phrasing

Return ONLY a JSON array of scores (one integer per sentence, in order):
[score1, score2, score3, ...]

SENTENCES:
{sentences}"""


@retry_with_backoff(max_retries=2, base_delay=0.5)
async def _get_perplexity_scores(sentences: list) -> list:
    """Ask Groq to score sentence predictability."""
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    loop = asyncio.get_running_loop()

    # Use first 20 sentences max
    sample = sentences[:20]
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sample))

    response = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": PERPLEXITY_PROMPT.format(sentences=numbered)}],
            temperature=0.1,
            max_tokens=200,
        )
    )
    scores = parse_llm_json(response.choices[0].message.content, default=[])
    if isinstance(scores, list):
        return [max(1, min(10, int(s))) for s in scores if isinstance(s, (int, float))]
    return []


def _burstiness_score(sentences: list) -> float:
    """
    Coefficient of variation of sentence lengths.
    AI text: low variance (uniform). Human text: high variance (bursty).
    Returns 0-1 where 0 = very AI-like, 1 = very human-like.
    """
    if len(sentences) < 3:
        return 0.5

    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.5

    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    std = math.sqrt(variance)
    cv = std / mean  # coefficient of variation

    # Normalize: CV < 0.3 = AI-like, CV > 0.7 = human-like
    normalized = min(1.0, cv / 0.7)
    return normalized


def _ngram_repetition_score(text: str) -> float:
    """
    Measures 4-gram repetition ratio.
    AI text tends to reuse phrases; human text is more varied.
    Returns 0-1 where 0 = very AI-like (high repetition), 1 = very human-like.
    """
    words = text.lower().split()
    if len(words) < 8:
        return 0.5

    ngrams = [tuple(words[i:i+4]) for i in range(len(words) - 3)]
    total = len(ngrams)
    unique = len(set(ngrams))

    if total == 0:
        return 0.5

    repetition_ratio = 1 - (unique / total)
    # Higher repetition = more AI-like = lower human score
    human_score = 1.0 - (repetition_ratio * 2)  # scale up repetition penalty
    return max(0.0, min(1.0, human_score))


def _combine_signals(perplexity_avg: float, burstiness: float, ngram: float) -> int:
    """
    Combine three signals into 0-100 AI probability score.
    Higher score = more likely AI-generated.
    Perplexity avg: 1-10 where low=AI. Normalize to 0-1 where 1=AI.
    """
    # Normalize perplexity: score 1 = AI (1.0), score 10 = human (0.0)
    perplexity_ai = 1.0 - ((perplexity_avg - 1) / 9.0) if perplexity_avg > 0 else 0.5

    # Burstiness: 0=AI, 1=human → invert for AI score
    burstiness_ai = 1.0 - burstiness

    # Ngram: 0=AI, 1=human → invert
    ngram_ai = 1.0 - ngram

    # Weighted average: perplexity most important, then burstiness, then ngram
    ai_probability = (perplexity_ai * 0.5) + (burstiness_ai * 0.3) + (ngram_ai * 0.2)
    return max(0, min(100, int(ai_probability * 100)))


def _label(score: int) -> str:
    if score < 31:
        return "Likely Human"
    if score < 71:
        return "Uncertain"
    return "Likely AI"


async def detect_ai_text(text: str) -> dict:
    """
    Main entry: analyze text for AI-generation probability.
    Returns AITextDetection dict.
    """
    # Split into sentences
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 10]

    if len(sentences) < 3:
        return {
            "score": 50,
            "label": "Uncertain",
            "perplexity_signal": 0.5,
            "burstiness_signal": 0.5,
            "ngram_signal": 0.5,
        }

    # Run perplexity scoring and local signals concurrently
    try:
        perplexity_scores = await _get_perplexity_scores(sentences)
        perplexity_avg = sum(perplexity_scores) / len(perplexity_scores) if perplexity_scores else 5.0
    except Exception as e:
        logger.warning(f"Perplexity scoring failed: {e}")
        perplexity_avg = 5.0

    burstiness = _burstiness_score(sentences)
    ngram = _ngram_repetition_score(text)

    score = _combine_signals(perplexity_avg, burstiness, ngram)

    logger.info(
        f"AI text detection: score={score}, "
        f"perplexity_avg={perplexity_avg:.1f}, "
        f"burstiness={burstiness:.2f}, ngram={ngram:.2f}"
    )

    return {
        "score": score,
        "label": _label(score),
        "perplexity_signal": round(1.0 - ((perplexity_avg - 1) / 9.0), 2),
        "burstiness_signal": round(1.0 - burstiness, 2),
        "ngram_signal": round(1.0 - ngram, 2),
    }
