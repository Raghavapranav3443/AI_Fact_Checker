import os
import re
import logging
import asyncio
import functools
from typing import List
from groq import Groq
from utils.retry import retry_with_backoff, parse_llm_json

logger = logging.getLogger(__name__)

# ── Sentence segmentation ─────────────────────────────────────────────────────
# Pre-segment the article server-side so the model only has to output
# a sentence INDEX rather than reproduce text verbatim.
# This eliminates the #1 source of extraction unreliability: the model
# paraphrasing or hallucinating source_sentence.

_PA = "\x00"  # placeholder: protected period (abbreviation internal)
_PD = "\x01"  # placeholder: protected period (decimal)
_PE = "\x02"  # placeholder: ellipsis

_ABBREVS = (
    r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|approx|est|'
    r'Corp|Inc|Ltd|Co|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
)

def _segment_sentences(text: str) -> list:
    """
    Split text into sentences robustly.
    Handles: U.S./U.K. abbreviations, Dr./Mr. titles,
    decimal numbers, ellipsis, ?/! terminators.
    Returns list of non-empty sentence strings.
    """
    p = text

    # Protect X.Y. abbreviations — only internal period, keep trailing period
    # 'U.S.' → 'U\x00S.'  so the trailing '.' can still be a sentence boundary
    p = re.sub(
        r'\b([A-Z])\.([A-Z])\.',
        lambda m: m.group(1) + _PA + m.group(2) + '.',
        p
    )

    # Protect word abbreviations (Dr. Mr. Inc. etc.)
    p = re.sub(
        _ABBREVS + r'\.',
        lambda m: m.group(0).replace('.', _PA),
        p
    )

    # Protect decimal numbers: 3.14 → 3\x0114
    p = re.sub(r'(\d)\.(\d)', lambda m: m.group(1) + _PD + m.group(2), p)

    # Protect ellipsis
    p = p.replace('...', _PE)

    # Split on real sentence boundary: [.!?] + optional close-quote + space + uppercase
    parts = re.split(r'(?<=[.!?])[)\"\u2019\u201d]?\s+(?=[A-Z\"\u2018\u201c])', p)

    result = []
    for s in parts:
        s = s.replace(_PA, '.').replace(_PD, '.').replace(_PE, '...').strip()
        if s and len(s) > 5:
            result.append(s)
    return result


# ── Extraction prompt ─────────────────────────────────────────────────────────
# Key design decisions:
# 1. Model outputs sentence_index (an integer) not source_sentence text.
#    source_sentence is retrieved deterministically from the pre-segmented list.
#    This eliminates paraphrasing/hallucination of source text entirely.
# 2. Few-shot examples calibrate what counts as a valid claim and how to classify.
# 3. 'independently verifiable' replaces 'important' — testable, not subjective.
# 4. Rule conflict resolved: model splits claims atomically; index cites origin sentence.

EXTRACTION_PROMPT = """You are a fact extraction engine. The article has been pre-split into numbered sentences below.

Your task: extract verifiable atomic facts and cite which sentence each came from by its index number.

RULES:
1. Each claim must be a single, standalone verifiable statement. If one sentence contains two facts, extract two separate claims both citing the same sentence index.
2. Extract ONLY objective facts that are independently verifiable with a web search. Exclude opinions, predictions, and speculation.
3. Classify each claim as exactly one of:
   - Temporal: current officeholders, ongoing events, recent statistics (may change over time)
   - Statistical: specific numbers, percentages, quantities, measurements
   - Entity-State: current status/condition of a person, company, or thing
   - Historical-Fact: past events, founding dates, historical records that do not change
4. Extract a MAXIMUM of 12 claims. Prioritise claims with specific numbers, names, or dates — these are the most independently verifiable.
5. Return ONLY a valid JSON array. No preamble. No markdown fences.

EXAMPLES OF GOOD vs BAD CLAIMS:
Good: "The WHO was established on April 7, 1948." (Historical-Fact — specific date, verifiable)
Good: "The WHO has 194 member states." (Statistical — specific number, verifiable)
Bad:  "The WHO plays an important role in global health." (opinion, not verifiable)
Bad:  "Experts believe AI may transform healthcare." (speculation)
Bad:  "The organization was founded and is headquartered in Geneva." (two facts — split into two claims)

CLAIM TYPES — ONE EXAMPLE EACH:
Temporal:        "Dr. Tedros Adhanom Ghebreyesus is the current WHO Director-General." (could change)
Statistical:     "Microsoft invested $13 billion in OpenAI in 2023." (specific number)
Entity-State:    "OpenAI is structured as a capped-profit company." (current status)
Historical-Fact: "Apple was founded by Steve Jobs and Steve Wozniak in 1976." (past event, fixed)

JSON SCHEMA — output exactly this structure:
[
  {{
    "claim_id": 1,
    "claim_text": "Single atomic verifiable fact as a clean sentence.",
    "claim_type": "Temporal|Statistical|Entity-State|Historical-Fact",
    "sentence_index": 0
  }}
]

NUMBERED SENTENCES:
{numbered_sentences}"""


# ── API call ──────────────────────────────────────────────────────────────────
@retry_with_backoff(max_retries=2, base_delay=1.0)
async def _call_groq_extraction(numbered_sentences: str) -> str:
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    loop = asyncio.get_running_loop()
    prompt = EXTRACTION_PROMPT.replace("{numbered_sentences}", numbered_sentences)
    response = await loop.run_in_executor(
        None,
        functools.partial(
            client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4096,  # raised from 3000 — 12 claims × ~80 tokens each + overhead
        )
    )
    return response.choices[0].message.content


# ── Main extraction function ──────────────────────────────────────────────────
async def extract_claims(article_text: str) -> List[dict]:
    # Step 1: segment article into sentences server-side
    sentences = _segment_sentences(article_text)

    if not sentences:
        logger.warning("No sentences could be extracted from article text")
        return []

    # Step 2: build numbered sentence list for the prompt
    # Cap at 12000 chars total to stay within model context while covering ~2400 words
    numbered_lines = []
    total_chars = 0
    included_sentences = []
    for i, s in enumerate(sentences):
        line = f"[{i}] {s}"
        total_chars += len(line)
        if total_chars > 12000:
            logger.info(f"Article truncated at sentence {i} ({total_chars} chars)")
            break
        numbered_lines.append(line)
        included_sentences.append(s)

    numbered_sentences = "\n".join(numbered_lines)

    # Step 3: call model
    try:
        raw = await _call_groq_extraction(numbered_sentences)
    except Exception as e:
        logger.error(f"Claim extraction API call failed: {e}")
        return []

    # Step 4: parse and validate
    parsed = parse_llm_json(raw, default=[])
    if not isinstance(parsed, list):
        logger.warning(f"Extraction returned non-list: {type(parsed)}")
        return []

    valid_claims = []
    valid_types  = {"Temporal", "Statistical", "Entity-State", "Historical-Fact"}

    for item in parsed:
        if not isinstance(item, dict):
            continue

        claim_text = str(item.get("claim_text", "")).strip()
        claim_type = str(item.get("claim_type", "Historical-Fact")).strip()

        # Validate claim text
        if not claim_text or len(claim_text) < 10:
            continue

        # Validate/normalise claim type
        if claim_type not in valid_types:
            claim_type = "Historical-Fact"

        # Resolve source_sentence from sentence_index — deterministic, no hallucination
        sentence_index = item.get("sentence_index")
        if isinstance(sentence_index, (int, float)):
            idx = int(sentence_index)
            if 0 <= idx < len(included_sentences):
                source_sentence = included_sentences[idx]
            else:
                # Index out of range — fall back to nearest sentence via claim_text search
                source_sentence = _find_nearest_sentence(claim_text, included_sentences)
        else:
            # Model didn't return an index — find best matching sentence
            source_sentence = _find_nearest_sentence(claim_text, included_sentences)

        valid_claims.append({
            "claim_id":        len(valid_claims) + 1,
            "claim_text":      claim_text,
            "claim_type":      claim_type,
            "source_sentence": source_sentence,
        })

    logger.info(f"Extracted {len(valid_claims)} valid claims from {len(sentences)} sentences")
    return valid_claims


def _find_nearest_sentence(claim_text: str, sentences: list) -> str:
    """
    Fallback: find the sentence that shares the most words with the claim.
    Used when model returns no/invalid sentence_index.
    Returns the best matching sentence, or claim_text if nothing matches.
    """
    if not sentences:
        return claim_text

    claim_words = set(claim_text.lower().split())
    best_score  = 0
    best_sent   = sentences[0]

    for s in sentences:
        sent_words = set(s.lower().split())
        # Jaccard-like overlap: shared words / claim words
        overlap = len(claim_words & sent_words) / max(len(claim_words), 1)
        if overlap > best_score:
            best_score = overlap
            best_sent  = s

    # If overlap is too low (< 20%), the claim may be invented — return claim_text
    # so TextAnnotator falls back gracefully rather than highlighting the wrong sentence
    return best_sent if best_score >= 0.2 else claim_text