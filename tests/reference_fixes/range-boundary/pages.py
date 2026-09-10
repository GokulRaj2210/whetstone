def parse_range(text):
    """Parse "a-b" into the list of page numbers it covers.

    Both endpoints are inclusive.
    """
    text = text.strip()
    if "-" not in text:
        return [int(text)]
    start, end = text.split("-", 1)
    return list(range(int(start), int(end) + 1))
