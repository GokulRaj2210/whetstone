def slug(title):
    """Make a URL slug from a title."""
    hyphenated = title.lower().replace(" ", "-")
    return "".join(c for c in hyphenated if c.isalnum())
