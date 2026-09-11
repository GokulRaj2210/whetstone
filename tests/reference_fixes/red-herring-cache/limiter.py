_COUNTS = {}


def _key(user_id):
    return str(user_id)


def hits(user_id):
    """Number of requests seen for this user."""
    return _COUNTS.get(_key(user_id), 0)


def record(user_id):
    key = _key(user_id)
    _COUNTS[key] = _COUNTS.get(key, 0) + 1


def allowed(user_id, limit=3):
    return hits(user_id) < limit
