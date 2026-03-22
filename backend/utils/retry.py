import asyncio
import json
import re
import logging
from functools import wraps
from typing import Any, Optional

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Async retry decorator with exponential backoff.
    Applies to all external API calls. Rule B-1.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {e}")
            if last_exception:
                raise last_exception
            raise Exception(f"{func.__name__} failed without an exception recorded")
        return wrapper
    return decorator


def parse_llm_json(raw: str, default: Any = None) -> Any:
    """
    Tolerant JSON parser for LLM responses. Rule B-2.
    Handles: markdown fences, leading text, trailing text,
    extra fields, minor schema issues.
    Never raises — returns default on failure.
    """
    if not raw:
        return default

    # Strip markdown fences
    cleaned = re.sub(r'```(?:json)?\s*', '', raw)
    cleaned = re.sub(r'```\s*$', '', cleaned)
    cleaned = cleaned.strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to extract first JSON object
    obj_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if obj_match:
        try:
            return json.loads(obj_match.group())
        except json.JSONDecodeError:
            pass

    # Try to extract first JSON array
    arr_match = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if arr_match:
        try:
            return json.loads(arr_match.group())
        except json.JSONDecodeError:
            pass

    # Fix trailing commas before closing braces/brackets
    fixed = re.sub(r',\s*([}\]])', r'\1', cleaned)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # New: Aggressive repair for truncated JSON objects
    if cleaned.startswith('{') and not cleaned.endswith('}'):
        # Try to backtrack to the last meaningful closing point
        # This regex looks for a value followed by a comma or a key:value pair
        # and tries to close the object there.
        try:
            # 1. Strip trailing dangling characters following a comma or colon
            repaired = re.sub(r',[^,]*$', '', cleaned)
            repaired = repaired.rstrip() # Remove trailing spaces
            if not repaired.endswith('}'): 
                repaired += '}'
            return json.loads(repaired)
        except Exception:
            try:
                # 2. Even more aggressive: find last quote followed by anything and strip it
                repaired = re.sub(r'"[^"]*$', '', cleaned)
                repaired = repaired.rstrip().rstrip(',') # Remove trailing comma if it exists after strip
                if not repaired.endswith('}'):
                    repaired += '}'
                return json.loads(repaired)
            except Exception:
                pass

    logger.debug(f"parse_llm_json: all attempts failed. Raw (first 300 chars): {raw[:300]}")
    return default


def safe_get(d: dict, key: str, default: Any = None) -> Any:
    """Safe dict access with default."""
    return d.get(key, default) if isinstance(d, dict) else default
