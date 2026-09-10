def render(text):
    """Escape HTML special characters for safe interpolation.

    Order matters: `&` has to be escaped *before* the others, or the
    ampersands introduced by `&lt;` and `&gt;` get escaped a second time
    and the output shows `&amp;lt;` to the user.
    """
    return text.replace("<", "&lt;").replace(">", "&gt;")
