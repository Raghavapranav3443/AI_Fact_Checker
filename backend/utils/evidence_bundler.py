import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def build_evidence_bundle(
    claim_id: int,
    tavily_sources: List[dict],
    structured_facts: List[dict],
    queries_used: List[str],
) -> dict:
    """
    Merges web search results and structured KB facts into a single
    evidence bundle for a claim. Deduplicates by URL. Sorts by authority.
    """
    # Deduplicate by URL
    seen_urls = set()
    clean_sources = []
    for s in tavily_sources:
        url = s.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            clean_sources.append(s)

    # Sort by authority score desc, keep top 5
    clean_sources.sort(key=lambda x: x.get("authority_score", 0), reverse=True)
    clean_sources = clean_sources[:5]

    # Clean structured facts
    clean_facts = [f for f in structured_facts if f and isinstance(f, dict) and f.get("content")]

    logger.debug(
        f"Claim {claim_id}: bundled {len(clean_sources)} web sources, "
        f"{len(clean_facts)} KB facts"
    )

    return {
        "claim_id": claim_id,
        "sources": clean_sources,
        "structured_facts": clean_facts,
        "queries_used": queries_used,
    }


def format_evidence_for_prompt(bundle: dict) -> str:
    """
    Formats an evidence bundle into a plain-text block for LLM prompts.
    Combines web sources and structured KB facts.
    """
    lines = []

    for i, src in enumerate(bundle.get("sources", []), 1):
        snippet = src.get("content_snippet", "").strip()
        domain = src.get("domain", "")
        title = src.get("title", "")
        url = src.get("url", "")
        pub = src.get("publish_date", "")
        date_str = f" ({pub})" if pub else ""
        lines.append(
            f"[WEB SOURCE {i}] {title} — {domain}{date_str}\n"
            f"URL: {url}\n"
            f"Content: {snippet}\n"
        )

    for i, fact in enumerate(bundle.get("structured_facts", []), 1):
        source_name = fact.get("source", "KB").upper()
        content = fact.get("content", "").strip()
        lines.append(f"[{source_name} STRUCTURED FACT {i}] {content}\n")

    if not lines:
        return "No evidence retrieved for this claim."

    return "\n".join(lines)
