def render(text):
    """Escape HTML special characters for safe interpolation."""
    return text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
