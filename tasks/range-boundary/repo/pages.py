def parse_range(text):
    """Parse "a-b" into the list of page numbers it covers.

    Both endpoints are inclusive: "1-5" covers pages 1, 2, 3, 4 and 5.
    A bare number is a single page. Whitespace is ignored.
    """
    text = text.strip()
    if "-" not in text:
        return [int(text)]
    start, end = text.split("-", 1)
    return list(range(int(start), int(end)))
