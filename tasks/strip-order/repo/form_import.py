from normalise import clean_token


def tags_from_form(text):
    """Tags typed by a user, separated by spaces."""
    return [clean_token(part) for part in text.split() if part.strip()]
