CALLS = []
_CACHE = {}


def _key(path, params):
    return f"{path}:{params}"


def fetch(path, params=None):
    """Fetch `path`, caching by path *and* params."""
    params = params or {}
    key = _key(path, params)
    if key in _CACHE:
        return _CACHE[key]
    CALLS.append((path, dict(params)))
    body = f"{path}?{sorted(params.items())}"
    _CACHE[key] = body
    return body
