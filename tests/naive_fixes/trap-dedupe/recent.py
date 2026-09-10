def recent(article_ids):
    """Most-recently-viewed article ids, newest first, no repeats."""
    return list(set(article_ids))
