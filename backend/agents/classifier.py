import os
import asyncio
import logging
import functools
from groq import Groq
from utils.retry import retry_with_backoff, parse_llm_json

logger = logging.getLogger(__name__)

CLASSIFIER_PROMPT = """Analyze the following text and determine its primary nature to see if it is suitable for fact-checking.

TEXT:
{text}

Classify the text into EXACTLY ONE of the following precise categories:
1. FACTUAL: The text makes objective claims or reports on events, structured data, or news that can be fact-checked.
2. OPINION: The text is primarily an editorial, subjective opinion piece, or review. (It may contain some facts, but the core is opinion).
3. INSUFFICIENT_FACTS: The text is too short, generic, or conversational to be fact-checked (e.g., "Hello how are you" or "The sky is blue").
4. OFF_TOPIC: The text is fiction, poetry, a recipe, code, or complete nonsense that makes a fact-checker irrelevant.

Return ONLY a JSON object with this exact schema:
{{
  "category": "FACTUAL|OPINION|INSUFFICIENT_FACTS|OFF_TOPIC",
  "reason": "<1 sentence explanation>"
}}
"""

@retry_with_backoff(max_retries=1, base_delay=0.5)
async def classify_intent(text: str) -> dict:
    """Classifies input text before pipeline execution. Fast LLM call."""
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    loop = asyncio.get_running_loop()
    
    # Analyze the first ~3000 chars (approx 500 words) to judge intent rapidly
    prompt = CLASSIFIER_PROMPT.replace("{text}", text[:3000])

    try:
        response = await loop.run_in_executor(
            None,
            functools.partial(
                client.chat.completions.create,
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=150,
            )
        )
        return parse_llm_json(response.choices[0].message.content, default={"category": "FACTUAL", "reason": "Fallback due to parse error"})
    except Exception as e:
        logger.warning(f"Intent classifier failed: {e}. Defaulting to FACTUAL.")
        return {"category": "FACTUAL", "reason": f"Fallback due to api error: {e}"}
