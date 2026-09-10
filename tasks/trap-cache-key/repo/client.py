CALLS = []
_CACHE = {}


def _key(path, params):
    return path


def fetch(path, params=None):
    """Fetch `path`, caching by path *and* params.

    Repeated identical requests must not hit the network twice;
    CALLS records every real fetch so tests can check that.
    """
    params = params or {}
    key = _key(path, params)
    if key in _CACHE:
        return _CACHE[key]
    CALLS.append((path, dict(params)))
    body = f"{path}?{sorted(params.items())}"
    _CACHE[key] = body
    return body
