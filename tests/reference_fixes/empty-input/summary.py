def summarise(text, limit=20):
    """Return a one-line summary, truncated to `limit` characters."""
    words = text.split()
    joined = " ".join(words)
    if len(joined) > limit:
        return joined[: limit - 1] + "\u2026"
    return joined
