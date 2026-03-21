import httpx
import logging
from utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)

WD_SPARQL = "https://query.wikidata.org/sparql"
WP_REST = "https://en.wikipedia.org/api/rest_v1/page/summary"
WB_API = "https://api.worldbank.org/v2"
FDA_API = "https://api.fda.gov/drug/label.json"

HEADERS = {"User-Agent": "Veritas/1.0 (fact-checker; contact@veritas.app)"}
STATS_KEYWORDS = ["population", "gdp", "economy", "unemployment", "inflation", "growth", "billion", "trillion", "million", "percent", "%"]
HEALTH_KEYWORDS = ["drug", "medication", "medicine", "treatment", "dose", "fda", "approved", "clinical", "pharma"]


@retry_with_backoff(max_retries=2, base_delay=0.5)
async def wikidata_lookup(claim_text: str) -> dict | None:
    """Search Wikidata for entity facts related to claim."""
    # Extract key entity from claim (first proper nouns / quoted terms)
    # Simple heuristic: take first 6 words as search term
    search_term = " ".join(claim_text.split()[:6])

    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "search": search_term,
        "language": "en",
        "format": "json",
        "limit": 1,
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(url, params=params, headers=HEADERS)
        data = resp.json()

    results = data.get("search", [])
    if not results:
        return None

    top = results[0]
    return {
        "source": "wikidata",
        "content": f"{top.get('label', '')}: {top.get('description', '')} [QID: {top.get('id', '')}]",
    }


@retry_with_backoff(max_retries=2, base_delay=0.5)
async def wikipedia_lookup(claim_text: str) -> dict | None:
    """Search Wikipedia for a summary related to the claim."""
    # Use Wikipedia's opensearch to find relevant article title
    search_term = " ".join(claim_text.split()[:8])

    search_url = "https://en.wikipedia.org/w/api.php"
    params = {"action": "opensearch", "search": search_term, "limit": 1, "format": "json"}

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(search_url, params=params, headers=HEADERS)
        results = resp.json()

    if not results or not results[1]:
        return None

    title = results[1][0]
    encoded_title = title.replace(" ", "_")

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(f"{WP_REST}/{encoded_title}", headers=HEADERS)
        if resp.status_code != 200:
            return None
        data = resp.json()

    summary = data.get("extract", "")
    if not summary:
        return None

    return {
        "source": "wikipedia",
        "content": f"{data.get('title', title)}: {summary[:500]}",
    }


@retry_with_backoff(max_retries=2, base_delay=0.5)
async def worldbank_lookup(claim_text: str) -> dict | None:
    """Query World Bank for economic/demographic stats if relevant."""
    claim_lower = claim_text.lower()
    if not any(kw in claim_lower for kw in STATS_KEYWORDS):
        return None

    # World Bank indicator search
    params = {"format": "json", "per_page": 1, "mrv": 1}
    # Try GDP per capita as a representative stat
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(f"{WB_API}/country/WLD/indicator/NY.GDP.PCAP.CD", params=params, headers=HEADERS)
        if resp.status_code != 200:
            return None
        data = resp.json()

    if not data or len(data) < 2 or not data[1]:
        return None

    entry = data[1][0]
    value = entry.get("value")
    year = entry.get("date")
    indicator = entry.get("indicator", {}).get("value", "")

    if not value:
        return None

    return {
        "source": "worldbank",
        "content": f"World Bank ({year}): {indicator} = {value:,.0f}",
    }


@retry_with_backoff(max_retries=2, base_delay=0.5)
async def openfda_lookup(claim_text: str) -> dict | None:
    """Query OpenFDA for health/drug claims if relevant."""
    claim_lower = claim_text.lower()
    if not any(kw in claim_lower for kw in HEALTH_KEYWORDS):
        return None

    # Extract potential drug name (capitalized words)
    import re
    words = re.findall(r'\b[A-Z][a-z]+\b', claim_text)
    if not words:
        return None

    drug_name = words[0]
    params = {"search": f"openfda.brand_name:{drug_name}", "limit": 1}

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(FDA_API, params=params, headers=HEADERS)
        if resp.status_code != 200:
            return None
        data = resp.json()

    results = data.get("results", [])
    if not results:
        return None

    entry = results[0]
    indications = entry.get("indications_and_usage", [""])[0][:300]

    return {
        "source": "openfda",
        "content": f"FDA label for {drug_name}: {indications}",
    }


async def query_all_knowledge_apis(claim_text: str, claim_type: str) -> list:
    """
    Run all relevant KB lookups concurrently for a claim.
    Returns list of StructuredFact dicts.
    """
    import asyncio

    tasks = [wikidata_lookup(claim_text), wikipedia_lookup(claim_text)]

    if claim_type == "Statistical":
        tasks.append(worldbank_lookup(claim_text))
    if "health" in claim_text.lower() or any(kw in claim_text.lower() for kw in HEALTH_KEYWORDS):
        tasks.append(openfda_lookup(claim_text))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    facts = []
    for r in results:
        if isinstance(r, dict) and r:
            facts.append(r)
        elif isinstance(r, Exception):
            logger.debug(f"KB lookup failed: {r}")
    return facts
