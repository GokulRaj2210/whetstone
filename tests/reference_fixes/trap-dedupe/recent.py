def recent(article_ids):
    """Most-recently-viewed article ids, newest first, no repeats."""
    seen = set()
    out = []
    for article_id in article_ids:
        if article_id not in seen:
            seen.add(article_id)
            out.append(article_id)
    return out
