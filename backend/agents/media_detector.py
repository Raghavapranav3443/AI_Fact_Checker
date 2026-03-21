import os
import asyncio
import logging
import httpx
from utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)

HIVE_API_URL = "https://api.thehive.ai/api/v2/task/sync"
MAX_IMAGES = 8  # cap per run to avoid rate limits


@retry_with_backoff(max_retries=2, base_delay=1.0)
async def _analyze_image(image_url: str, api_key: str) -> dict:
    """Send one image URL to Hive Moderation API."""
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"url": image_url}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(HIVE_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    # Parse Hive response structure
    ai_score = 0.0
    is_deepfake = False
    model_detected = None

    status_list = data.get("status", [])
    for status in status_list:
        for output in status.get("response", {}).get("output", []):
            for cls in output.get("classes", []):
                cls_name = cls.get("class", "").lower()
                score = float(cls.get("score", 0))
                if "ai_generated" in cls_name or "ai generated" in cls_name:
                    ai_score = max(ai_score, score)
                if "deepfake" in cls_name:
                    is_deepfake = score > 0.5
                    if is_deepfake:
                        model_detected = "deepfake"

    return {
        "url": image_url,
        "ai_generated_score": round(ai_score, 3),
        "is_deepfake": is_deepfake,
        "model_detected": model_detected,
        "error": None,
    }


async def detect_media(image_urls: list) -> list:
    """
    Analyze up to MAX_IMAGES from a page for AI generation / deepfakes.
    Runs all in parallel. Returns list of MediaResult dicts.
    Gracefully skips images that fail.
    """
    api_key = os.getenv("HIVE_API_KEY", "")
    if not api_key or api_key == "your_hive_api_key_here":
        logger.info("Hive API key not set — skipping media detection")
        return []

    urls_to_check = image_urls[:MAX_IMAGES]
    if not urls_to_check:
        return []

    async def _safe_analyze(url):
        try:
            return await _analyze_image(url, api_key)
        except Exception as e:
            logger.warning(f"Media detection failed for {url}: {e}")
            return {
                "url": url,
                "ai_generated_score": 0.0,
                "is_deepfake": False,
                "model_detected": None,
                "error": str(e),
            }

    results = await asyncio.gather(*[_safe_analyze(u) for u in urls_to_check])
    logger.info(f"Media detection complete: {len(results)} images analyzed")
    return list(results)
