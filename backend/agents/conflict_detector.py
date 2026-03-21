import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Keywords that signal direct contradiction between sources
CONTRADICTION_SIGNALS = [
    ("increased", "decreased"), ("grew", "shrank"), ("rose", "fell"),
    ("confirmed", "denied"), ("approved", "rejected"), ("true", "false"),
    ("founded", "not founded"), ("is", "is not"), ("was", "was not"),
    ("supports", "opposes"), ("passed", "failed"), ("won", "lost"),
]


def _sources_conflict(snippet_a: str, snippet_b: str) -> bool:
    """
    Simple heuristic: check if two snippets contain opposing signal words.
    """
    a = snippet_a.lower()
    b = snippet_b.lower()
    for (word1, word2) in CONTRADICTION_SIGNALS:
        if (word1 in a and word2 in b) or (word2 in a and word1 in b):
            return True
    return False


def _better_supported(source_a: dict, source_b: dict) -> str:
    """Compare two sources by authority + recency. Returns 'A', 'B', or 'equal'."""
    score_a = source_a.get("authority_score", 0.4)
    score_b = source_b.get("authority_score", 0.4)

    # Recency tiebreaker
    pub_a = source_a.get("publish_date", "") or ""
    pub_b = source_b.get("publish_date", "") or ""
    recent_years = {"2025", "2026", "2024"}
    a_recent = any(y in pub_a for y in recent_years)
    b_recent = any(y in pub_b for y in recent_years)

    if score_a > score_b + 0.1:
        return "A"
    if score_b > score_a + 0.1:
        return "B"
    if a_recent and not b_recent:
        return "A"
    if b_recent and not a_recent:
        return "B"
    return "equal"


def detect_conflicts(verdicts: Dict[int, dict], evidence_bundles: Dict[int, dict]) -> List[dict]:
    """
    Scan all verified claims for cross-source contradictions.
    A conflict is when two sources from the same or different claims
    have directly opposing content about the same subject.

    Returns list of ConflictPair dicts.
    """
    conflicts = []

    # First: detect within a single claim (sources that contradict each other)
    for claim_id, bundle in evidence_bundles.items():
        sources = bundle.get("sources", [])
        verdict = verdicts.get(claim_id, {})
        claim_text = verdict.get("claim_text", f"Claim {claim_id}")

        for i, src_a in enumerate(sources):
            for src_b in sources[i + 1:]:
                snippet_a = src_a.get("content_snippet", "")
                snippet_b = src_b.get("content_snippet", "")

                if not snippet_a or not snippet_b:
                    continue

                if _sources_conflict(snippet_a, snippet_b):
                    conflict = {
                        "claim_id": claim_id,
                        "claim_text": claim_text,
                        "source_a": src_a,
                        "source_b": src_b,
                        "source_a_summary": snippet_a[:300],
                        "source_b_summary": snippet_b[:300],
                        "better_supported": _better_supported(src_a, src_b),
                    }
                    conflicts.append(conflict)

                    # Flag the verdict
                    if claim_id in verdicts:
                        verdicts[claim_id]["conflict_flag"] = True

                    logger.info(
                        f"Conflict detected in claim {claim_id}: "
                        f"{src_a.get('domain')} vs {src_b.get('domain')}"
                    )

    # Deduplicate conflicts (same claim_id + same domain pair)
    seen = set()
    unique_conflicts = []
    for c in conflicts:
        key = (c["claim_id"], c["source_a"].get("domain", ""), c["source_b"].get("domain", ""))
        if key not in seen:
            seen.add(key)
            unique_conflicts.append(c)

    logger.info(f"Conflict detection complete: {len(unique_conflicts)} conflicts found")
    return unique_conflicts
