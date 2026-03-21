from urllib.parse import urlparse

TIER_1_DOMAINS = {
    "reuters.com", "apnews.com", "who.int", "cdc.gov", "nih.gov",
    "nature.com", "science.org", "pubmed.ncbi.nlm.nih.gov", "scholar.google.com",
    "un.org", "worldbank.org", "imf.org", "europa.eu", "nasa.gov",
}

TIER_2_DOMAINS = {
    "bbc.com", "bbc.co.uk", "nytimes.com", "theguardian.com",
    "washingtonpost.com", "economist.com", "ft.com", "wsj.com",
    "bloomberg.com", "npr.org", "pbs.org", "theatlantic.com",
    "time.com", "newsweek.com", "forbes.com", "cnbc.com",
    "wired.com", "scientificamerican.com", "newscientist.com",
    "thetimes.co.uk", "telegraph.co.uk", "lemonde.fr", "dw.com",
    "aljazeera.com", "thehindu.com", "ndtv.com", "hindustantimes.com",
}


def score_domain(url: str) -> float:
    """
    Returns authority score: 1.0 (Tier 1), 0.7 (Tier 2), 0.4 (Tier 3).
    Tier 1 also includes all .gov and .edu TLDs.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().lstrip("www.")
    except Exception:
        return 0.3

    # .gov and .edu always Tier 1
    if domain.endswith(".gov") or domain.endswith(".edu"):
        return 1.0

    # Check exact domain match
    if domain in TIER_1_DOMAINS:
        return 1.0
    if domain in TIER_2_DOMAINS:
        return 0.7

    # Check if it's a subdomain of a known domain
    for known in TIER_1_DOMAINS:
        if domain.endswith(f".{known}"):
            return 1.0
    for known in TIER_2_DOMAINS:
        if domain.endswith(f".{known}"):
            return 0.7

    return 0.4


def get_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().lstrip("www.")
    except Exception:
        return url
