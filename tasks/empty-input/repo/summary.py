def summarise(text, limit=20):
    """Return a one-line summary, truncated to `limit` characters.

    A summary longer than `limit` is cut and gets an ellipsis; one
    that fits is returned unchanged.
    """
    words = text.split()
    first = words[0]
    joined = " ".join(words)
    if len(joined) > limit:
        return joined[: limit - 1] + "\u2026"
    return joined
