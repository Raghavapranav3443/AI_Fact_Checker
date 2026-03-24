import httpx
import re
import ipaddress
import socket
import asyncio
import logging
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import trafilatura
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError
from utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)

# Global semaphore to limit concurrent browser instances (prevent CPU/RAM spikes)
# We use a lazy loader to ensure it's attached to the running event loop.
_BROWSER_SEMAPHORE = None

def get_browser_semaphore():
    global _BROWSER_SEMAPHORE
    if _BROWSER_SEMAPHORE is None:
        _BROWSER_SEMAPHORE = asyncio.Semaphore(2)
    return _BROWSER_SEMAPHORE

# Modern browser headers to reduce bot detection
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

SKIP_TAGS = ["script", "style", "nav", "footer", "header", "aside",
             "noscript", "iframe", "form", "button", "meta", "link"]

_PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]
_BLOCKED_HOSTNAMES = {
    "localhost", "metadata.google.internal",
    "169.254.169.254", "instance-data",
}


def _validate_url(url: str) -> str:
    if len(url) > 2048:
        raise ValueError("URL too long (max 2048 characters)")
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError("Invalid URL format")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are allowed")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise ValueError(f"Requests to '{hostname}' are not allowed")
    try:
        # Initial SSRF check (DNS resolution)
        resolved_ip = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)[0][4][0]
        ip_obj = ipaddress.ip_address(resolved_ip)
        for private_range in _PRIVATE_RANGES:
            if ip_obj in private_range:
                raise ValueError("Requests to private/internal IP ranges are not allowed")
    except ValueError:
        raise
    except Exception:
        pass
    return url

async def _is_private_ip(hostname: str | None) -> bool:
    """Helper to check if a hostname resolves to a private IP (async)."""
    if not hostname:
        return False
    try:
        loop = asyncio.get_running_loop()
        # Use the async address info resolution
        addr_info = await loop.getaddrinfo(hostname, None)
        for item in addr_info:
            ip_str = item[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            for private_range in _PRIVATE_RANGES:
                if ip_obj in private_range:
                    return True
    except Exception:
        pass
    return False

async def _browser_scrape(url: str) -> dict:
    """Tier 2: Headless browser fallback for JS-rendered content."""
    logger.info(f"Launching browser fallback for: {url}")
    sem = get_browser_semaphore()
    async with sem:
        async with async_playwright() as p:
            # On some Windows environments, 'chromium' might not be installed.
            # We catch specific playwright errors in the outer block.
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                logger.error(f"Playwright chromium launch failed: {e}")
                raise
            try:
                context = await browser.new_context(
                    user_agent=HEADERS["User-Agent"],
                    viewport={"width": 1280, "height": 800}
                )
                page = await context.new_page()

                # Deep SSRF Protection via Request Interception
                async def intercept(route, request):
                    parsed = urlparse(request.url)
                    # Use the async check
                    if parsed.hostname and await _is_private_ip(parsed.hostname):
                        logger.warning(f"Aborting SSRF-risk request: {request.url}")
                        await route.abort()
                    else:
                        await route.continue_()

                await page.route("**/*", intercept)

                try:
                    # Wait for networkidle (or timeout)
                    await page.goto(url, wait_until="networkidle", timeout=20000)
                except PWTimeoutError:
                    logger.warning(f"Browser timeout on {url}, proceeding with partially loaded DOM")
                
                # Small cushion for SPA rendering
                await asyncio.sleep(1.5)

                html = await page.content()
                title = await page.title()
                return {"html": html, "title": title}
            finally:
                await browser.close()

@retry_with_backoff(max_retries=2, base_delay=1.0)
async def scrape_url(url: str) -> dict:
    """
    Robust URL scraper with Three-Tier fallback chain:
    1. Fast: httpx + Trafilatura
    2. Dynamic: Playwright + Trafilatura
    3. Heuristic: BeautifulSoup (last resort)
    """
    url = _validate_url(url)
    html = ""
    title = ""
    
    # --- Tier 1: Fast Scrape ---
    try:
        async with httpx.AsyncClient(
            timeout=12.0, 
            follow_redirects=True, 
            headers=HEADERS,
            max_redirects=3,
            verify=False  # Ignore SSL errors in fast scrape to allow fallback/trafilatura a chance
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
            # Basic title from fast scrape
            soup_fast = BeautifulSoup(html, "lxml")
            if soup_fast.title:
                title = soup_fast.title.get_text(strip=True)
    except Exception as e:
        logger.warning(f"Fast scrape failed for {url}: {e}")

    # Initial extraction attempt
    text = ""
    if html:
        text = await asyncio.to_thread(trafilatura.extract, html) or ""
    
    # --- Tier 2: Browser Fallback (if Tier 1 returned too little or failed) ---
    word_count = len((text or "").split())
    if word_count < 80:
        logger.info(f"Tier 1 insufficient ({word_count} words). Falling back to browser for {url}")
        try:
            b_data = await _browser_scrape(url)
            html = b_data["html"]
            title = b_data.get("title") or title
            # Re-extract from rendered DOM
            text = await asyncio.to_thread(trafilatura.extract, html) or ""
        except Exception as e:
            import traceback
            logger.error(f"Browser fallback fatal for {url}: {e}\n{traceback.format_exc()}")

    # --- Tier 3: Heuristic Fallback (BeautifulSoup) ---
    soup = None
    if not text or len(text.split()) < 35:
        logger.info(f"Tier 1+2 failed to extract quality content. Falling back to BS4 heuristics.")
        if html:
            try:
                soup = await asyncio.to_thread(BeautifulSoup, html, "lxml")
                # Decompose noise
                for t in soup(SKIP_TAGS): 
                    t.decompose()
                
                # Try to find a meaningful container
                body_el = (
                    soup.find("article") or 
                    soup.find("main") or
                    soup.find(attrs={"class": re.compile(r"article|content|story|post|body|article-body", re.I)}) or
                    soup.find(attrs={"id": re.compile(r"article|content|story|post|body|article-body", re.I)})
                )
                
                if body_el:
                    raw_text = body_el.get_text(separator=" ", strip=True)
                else:
                    # Last-last resort: grab all remaining text from the whole body
                    raw_text = soup.get_text(separator=" ", strip=True)
                
                # Cleanup whitespace
                raw_text = re.sub(r"\s{2,}", " ", raw_text).strip()
                text = re.sub(r"\n{3,}", "\n\n", raw_text)
            except Exception as e:
                logger.warning(f"Heuristic fallback failed: {e}")

    # --- Image Extraction (BS4 on final HTML) ---
    images = []
    if html:
        if soup is None:
            soup = await asyncio.to_thread(BeautifulSoup, html, "lxml")
        
        for img in soup.find_all("img", src=True):
            src = img.get("src", "")
            if src.startswith("//"): src = "https:" + src
            if not src.startswith("http"): continue
            
            if any(src.lower().split("?")[0].endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                # Lightweight check: most images are on the same domain as the article or a CDN
                # For images, we just check the hostname string against blocked list to save on DNS calls
                img_hostname = urlparse(src).hostname
                if img_hostname and img_hostname.lower() not in _BLOCKED_HOSTNAMES:
                    images.append(src)

    final_word_count = len((text or "").split())
    if final_word_count < 5:
        raise ValueError(
            f"Extracted text too short ({final_word_count} words) — "
            "page may require login, be behind a paywall, or have anti-bot protections."
        )

    logger.info(f"Successfully scraped {url}: {final_word_count} words, {len(images)} images")
    return {
        "text": text,
        "title": title,
        "images": list(dict.fromkeys(images))[:20]
    }
