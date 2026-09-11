LIMIT = 40


def body(text):
    """Encode a notification body, at most LIMIT bytes, always valid UTF-8."""
    encoded = text.encode("utf-8")
    if len(encoded) <= LIMIT:
        return encoded
    trimmed = encoded[:LIMIT]
    while trimmed:
        try:
            trimmed.decode("utf-8")
        except UnicodeDecodeError:
            trimmed = trimmed[:-1]
            continue
        break
    return trimmed
