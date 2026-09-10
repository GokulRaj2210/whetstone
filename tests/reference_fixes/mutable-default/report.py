def add_section(title, sections=None):
    """Append a section and return the accumulated list."""
    if sections is None:
        sections = []
    sections.append(title)
    return sections


def build_report(titles):
    result = []
    for title in titles:
        result = add_section(title, result)
    return result
