import re


def slug(title):
    """Make a URL slug from a title."""
    cleaned = re.sub(r"[^a-z0-9 ]", "", title.lower())
    return cleaned.replace(" ", "-")
