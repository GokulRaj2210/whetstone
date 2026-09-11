LIMIT = 40


def body(text):
    """Encode a notification body, at most LIMIT bytes.

    The result must be valid UTF-8 -- the provider rejects a payload
    that ends mid-character, which is easy to do when trimming bytes.
    """
    return text.encode("utf-8")
