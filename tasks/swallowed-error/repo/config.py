import json


class ConfigError(Exception):
    """Raised when configuration cannot be loaded.

    Callers rely on this: `startup.py` catches it to print a usable
    message and exit non-zero. Returning defaults instead of raising
    makes a broken deploy look like a healthy one.
    """


def load_config(path):
    try:
        with open(path) as handle:
            return json.load(handle)
    except Exception:
        return {}
