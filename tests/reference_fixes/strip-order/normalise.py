import string


def clean_token(token):
    """Normalise one user-supplied token: trim, lowercase, drop punctuation."""
    return token.strip().strip(string.punctuation).strip().lower()
