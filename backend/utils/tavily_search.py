import asyncio
import logging
import os
from typing import List
from utils.retry import retry_with_backoff
from utils.authority import score_domain, get_domain

logger = logging.getLogger(__name__)


def _get_tavily_client():
    from tavily import TavilyClient
    return TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))


@retry_with_backoff(max_retries=3, base_delay=1.0)
async def _search_one(query: str) -> List[dict]:
    """Execute a single Tavily search query asynchronously."""
    client = _get_tavily_client()
    loop = asyncio.get_running_loop()
    # Tavily is sync — run in thread executor
    result = await loop.run_in_executor(
        None,
        lambda: client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_raw_content=False,
        )
    )
    sources = []
    for r in result.get("results", []):
        sources.append({
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "content_snippet": r.get("content", "")[:600],
            "domain": get_domain(r.get("url", "")),
            "authority_score": score_domain(r.get("url", "")),
            "publish_date": r.get("published_date"),
        })
    return sources


async def search_parallel(queries: List[str]) -> List[dict]:
    """
    Fire all queries concurrently. Merge, deduplicate by URL, sort by authority.
    Returns top 5 sources.
    """
    if not queries:
        return []

    results = await asyncio.gather(
        *[_search_one(q) for q in queries],
        return_exceptions=True
    )

    seen_urls = set()
    merged = []
    for batch in results:
        if isinstance(batch, Exception):
            logger.warning(f"Tavily query failed: {batch}")
            continue
        for source in batch:
            url = source.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                merged.append(source)

    # Sort by authority score descending, keep top 5
    merged.sort(key=lambda x: x.get("authority_score", 0), reverse=True)
    return merged[:5]
