def slug(title):
    """Make a URL slug from a title.

    Spaces become hyphens. Punctuation must be removed *before*
    hyphenation, or a filter applied afterwards will take out the
    hyphens along with everything else.
    """
    return title.lower().replace(" ", "-")
