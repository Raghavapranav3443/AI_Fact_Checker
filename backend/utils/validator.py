def validate_input(text: str) -> dict:
    """
    Validates and measures input text.
    Returns metadata or raises ValueError.
    """
    words = text.split()
    word_count = len(words)
    char_count = len(text)

    if word_count < 5:
        raise ValueError(f"Input too short: {word_count} words. Minimum is 5 words.")
    if word_count > 10000:
        raise ValueError(f"Input too long: {word_count} words. Maximum is 10,000 words.")

    # Estimate: 10s base + 3s per estimated claim (1 claim per ~100 words, max 15)
    estimated_claims = min(15, max(3, word_count // 100))
    estimated_time = 10 + (estimated_claims * 4)

    return {
        "word_count": word_count,
        "char_count": char_count,
        "estimated_claims": estimated_claims,
        "estimated_time_seconds": estimated_time,
    }
