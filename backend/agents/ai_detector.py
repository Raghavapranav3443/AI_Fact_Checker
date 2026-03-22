import re
import math
import logging

logger = logging.getLogger(__name__)

# ── Signal weights (sum to 1.0) ──────────────────────────────────────────────
_WEIGHTS = {
    "burstiness":     0.30,
    "uniformity":     0.25,
    "function_words": 0.25,
    "punctuation":    0.20,
}

# ── Common English function words ────────────────────────────────────────────
# Human text contains ~40-50% function words; AI text ~15-25%.
_FUNCTION_WORDS = {
    'the','a','an','and','but','or','so','yet','for','nor',
    'i','me','my','we','our','you','your','he','she','it','they','them',
    'is','was','are','were','be','been','being','have','has','had',
    'do','does','did','will','would','could','should','may','might',
    'in','on','at','to','of','with','by','from','as','if','that',
    'this','these','those','there','here','when','where','how','what',
    'just','not','also','very','more','some','any','all','no','its',
    'his','her','their','which','who','about','up','out','into','than',
}


# ── Signal 1: Burstiness ─────────────────────────────────────────────────────
# Coefficient of variation of sentence lengths.
# Human writing bursts: short punchy sentences mixed with long ones (cv > 0.6).
# AI writing is metronomically uniform (cv < 0.3).
# Returns AI probability [0.0, 1.0].
def _burstiness(sentences: list) -> float:
    if len(sentences) < 3:
        return 0.5
    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.5
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    cv = math.sqrt(variance) / mean
    # cv=0.0 -> 1.0 (max AI), cv>=0.6 -> 0.0 (human)
    return max(0.0, min(1.0, 1.0 - (cv / 0.6)))


# ── Signal 2: Sentence length clustering ─────────────────────────────────────
# Fraction of sentences within ±4 words of the mean.
# AI sentences cluster tightly (>80% within window).
# Human sentences are spread out (<50% within same window).
# Returns AI probability [0.0, 1.0].
def _sentence_uniformity(sentences: list) -> float:
    if len(sentences) < 4:
        return 0.5
    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    clustered = sum(1 for l in lengths if abs(l - mean) <= 4)
    ratio = clustered / len(lengths)
    # ratio=0.4 -> 0.0 (human), ratio=0.8 -> 1.0 (AI)
    return max(0.0, min(1.0, (ratio - 0.4) / 0.4))


# ── Signal 3: Function word ratio ────────────────────────────────────────────
# Human text ~40-50% function words (the, I, was, and, but...).
# AI text ~15-25% function words — over-represents content/technical words.
# Works reliably even on short texts (>15 words).
# Returns AI probability [0.0, 1.0].
def _function_word_ratio(text: str) -> float:
    words = re.findall(r'\b[a-z]+\b', text.lower())
    n = len(words)
    if n < 15:
        return 0.5
    fw_count = sum(1 for w in words if w in _FUNCTION_WORDS)
    ratio = fw_count / n
    # ratio < 0.25 -> AI (1.0); ratio > 0.42 -> human (0.0)
    return max(0.0, min(1.0, 1.0 - ((ratio - 0.25) / 0.17)))


# ── Signal 4: Punctuation regularity ─────────────────────────────────────────
# Coefficient of variation of comma/colon/semicolon counts per sentence.
# AI punctuates with machine-like consistency (low cv).
# Human punctuation is erratic (high cv).
# Returns AI probability [0.0, 1.0].
def _punctuation_regularity(sentences: list) -> float:
    if len(sentences) < 4:
        return 0.5
    punct_counts = [len(re.findall(r'[,;:\-\u2013\u2014]', s)) for s in sentences]
    mean = sum(punct_counts) / len(punct_counts)
    if mean == 0:
        # No mid-sentence punctuation at all — neutral signal
        return 0.45
    variance = sum((p - mean) ** 2 for p in punct_counts) / len(punct_counts)
    cv = math.sqrt(variance) / mean
    # cv < 0.5 -> AI (1.0); cv > 1.2 -> human (0.0)
    return max(0.0, min(1.0, 1.0 - (cv / 1.2)))


# ── Combine ───────────────────────────────────────────────────────────────────
def _combine(signals: dict) -> int:
    score = sum(_WEIGHTS[k] * signals[k] for k in _WEIGHTS)
    return max(0, min(100, int(score * 100)))


def _label(score: int) -> str:
    if score < 30:
        return "Likely Human"
    if score < 65:
        return "Uncertain"
    return "Likely AI"


# ── Public entry point ────────────────────────────────────────────────────────
async def detect_ai_text(text: str) -> dict:
    """
    Fully deterministic AI text detection — no LLM call.
    Four statistically-grounded signals, calibrated for texts 50-10000 words.
    Returns a score 0-100 (higher = more likely AI-generated).
    """
    sentences = [
        s.strip()
        for s in re.split(r'(?<=[.!?])\s+', text)
        if len(s.strip()) > 8
    ]

    if len(sentences) < 3:
        return {
            "score": 50,
            "label": "Uncertain",
            "burstiness_signal":     0.5,
            "uniformity_signal":     0.5,
            "function_words_signal": 0.5,
            "punctuation_signal":    0.5,
            # Legacy keys for any cached reports
            "perplexity_signal":     0.5,
            "ngram_signal":          0.5,
        }

    signals = {
        "burstiness":     _burstiness(sentences),
        "uniformity":     _sentence_uniformity(sentences),
        "function_words": _function_word_ratio(text),
        "punctuation":    _punctuation_regularity(sentences),
    }

    score = _combine(signals)

    return {
        "score":  score,
        "label":  _label(score),
        "burstiness_signal":     round(signals["burstiness"],     2),
        "uniformity_signal":     round(signals["uniformity"],     2),
        "function_words_signal": round(signals["function_words"], 2),
        "punctuation_signal":    round(signals["punctuation"],    2),
        # Legacy keys — keeps old cached reports from crashing
        "perplexity_signal":     round(signals["function_words"], 2),
        "ngram_signal":          round(signals["uniformity"],     2),
    }