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
    Split text into sentences robustly while tracking character offsets.
    Returns list of dicts: {"text": str, "start": int, "end": int}
    """
    if not text:
        return []

    p = text
    # 1-to-1 protections (preserves length so offsets match original text)
    # Protect X.Y. abbreviations
    p = re.sub(
        r'\b([A-Z])\.([A-Z])\.',
        lambda m: m.group(1) + "\x00" + m.group(2) + ".",
        p
    )
    # Protect word abbreviations (Dr. Mr. Inc. etc.)
    p = re.sub(
        _ABBREVS + r'\.',
        lambda m: m.group(0).replace('.', "\x00"),
        p
    )
    # Protect decimal numbers: 3.14 → 3\x0114
    p = re.sub(r'(\d)\.(\d)', lambda m: m.group(1) + "\x01" + m.group(2), p)
    # Protect ellipsis
    p = p.replace('...', "\x02\x02\x02")

    # Split pattern using finditer to avoid fragile lookbehinds.
    # Group 1 = sentence end + optional quote.
    pattern = r'([.!?][)\"\u2019\u201d]?)\s+(?=[A-Z\"\u2018\u201c])'
    
    sentences = []
    cursor = 0
    for match in re.finditer(pattern, p):
        # End of the content (at the space start)
        content_end = match.end(1)
        s_text = text[cursor:content_end].strip()
        if len(s_text) > 5:
            sentences.append({
                "text":  s_text,
                "start": cursor,
                "end":   content_end
            })
        # Next sentence starts after the match
        cursor = match.end()

    # Final sentence
    s_text = text[cursor:].strip()
    if len(s_text) > 5:
        sentences.append({
            "text":  s_text,
            "start": cursor,
            "end":   len(text)
        })
    return sentences


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
   - Temporal: Current status or events that may change (e.g., current leaders, stock prices, active status).
   - Statistical: Numerical data, specific counts, percentages, or quantitative measurements.
   - Entity Status: Organizational or structural state (e.g., "is a non-profit", "is headquartered in X", "uses technology Y").
   - Historical Fact: Fixed past events, founding dates, past records, or biographical history.
4. Extract a MAXIMUM of 12 claims. Prioritise claims with specific numbers, names, or dates — these are the most independently verifiable.
5. Return ONLY a valid JSON array. No preamble. No markdown fences.

EXAMPLES OF GOOD vs BAD CLAIMS:
Good: "The WHO was established on April 7, 1948." (Historical Fact — specific date, verifiable)
Good: "The WHO has 194 member states." (Statistical — specific number, verifiable)
Bad:  "The WHO plays an important role in global health." (opinion, not verifiable)
Bad:  "Experts believe AI may transform healthcare." (speculation)
Bad:  "The organization was founded and is headquartered in Geneva." (two facts — split into two claims)

CLAIM TYPES — ONE EXAMPLE EACH:
Temporal:        "Dr. Tedros Adhanom Ghebreyesus is the current WHO Director-General."
Statistical:     "Microsoft invested $13 billion in OpenAI in 2023."
Entity Status:    "OpenAI is structured as a capped-profit company."
Historical Fact: "Apple was founded by Steve Jobs and Steve Wozniak in 1976."

JSON SCHEMA — output exactly this structure:
[
  {{
    "claim_id": 1,
    "claim_text": "Single atomic verifiable fact as a clean sentence.",
    "claim_type": "Temporal|Statistical|Entity Status|Historical Fact",
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
    # sentences is now a list of dicts: {text, start, end}
    for i, s_dict in enumerate(sentences):
        line = f"[{i}] {s_dict['text']}"
        total_chars += len(line)
        if total_chars > 12000:
            logger.info(f"Article truncated at sentence {i} ({total_chars} chars)")
            break
        numbered_lines.append(line)

    included_count = len(numbered_lines)
    included_sentences = sentences[:included_count]
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
    valid_types  = {"Temporal", "Statistical", "Entity Status", "Historical Fact"}

    for item in parsed:
        if not isinstance(item, dict):
            continue

        claim_text = str(item.get("claim_text", "")).strip()
        raw_type   = str(item.get("claim_type", "Historical Fact")).strip()

        # Normalization: handle hyphens and case for robustness
        # e.g., "Historical-Fact" -> "Historical Fact"
        norm_type = raw_type.replace("-", " ").title()
        if norm_type in valid_types:
            claim_type = norm_type
        else:
            claim_type = "Historical Fact"

        # Validate claim text
        if not claim_text or len(claim_text) < 10:
            continue

        # Resolve source_sentence from sentence_index — deterministic, no hallucination
        sentence_index = item.get("sentence_index")
        source_sentence = claim_text # fallback
        start_char = 0
        end_char = 0

        if isinstance(sentence_index, (int, float)):
            idx = int(sentence_index)
            if 0 <= idx < included_count:
                source_sentence = included_sentences[idx]["text"]
                start_char = included_sentences[idx]["start"]
                end_char = included_sentences[idx]["end"]
            else:
                # Index out of range — fall back via search
                matched = _find_nearest_sentence(claim_text, included_sentences)
                source_sentence = matched["text"]
                start_char = matched["start"]
                end_char = matched["end"]
        else:
            # Model didn't return an index — find best matching sentence
            matched = _find_nearest_sentence(claim_text, included_sentences)
            source_sentence = matched["text"]
            start_char = matched["start"]
            end_char = matched["end"]

        valid_claims.append({
            "claim_id":        len(valid_claims) + 1,
            "claim_text":      claim_text,
            "claim_type":      claim_type,
            "source_sentence": source_sentence,
            "start_char":      start_char,
            "end_char":        end_char,
        })

    # Step 5: Final sort by document order for intuitive labeling
    valid_claims.sort(key=lambda x: (x.get("start_char", 0), x.get("end_char", 0)))
    for i, c in enumerate(valid_claims):
        c["claim_id"] = i + 1

    logger.info(f"Extracted {len(valid_claims)} valid claims from {len(sentences)} sentences")
    return valid_claims


def _find_nearest_sentence(claim_text: str, sentences: list) -> dict:
    """
    Fallback: find the sentence that shares the most words with the claim.
    Returns the full sentence dict {text, start, end}.
    """
    if not sentences:
        return {"text": claim_text, "start": 0, "end": 0}

    claim_words = set(claim_text.lower().split())
    best_score  = 0
    best_sent   = sentences[0]

    for s_dict in sentences:
        sent_words = set(s_dict["text"].lower().split())
        overlap = len(claim_words & sent_words) / max(len(claim_words), 1)
        if overlap > best_score:
            best_score = overlap
            best_sent  = s_dict

    # Return the best sentence dict if score is high enough, else dummy
    if best_score >= 0.2:
        return best_sent
    else:
        return {"text": claim_text, "start": 0, "end": 0}