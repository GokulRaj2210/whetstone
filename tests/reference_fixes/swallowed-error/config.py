import json


class ConfigError(Exception):
    """Raised when configuration cannot be loaded."""


def load_config(path):
    try:
        with open(path) as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"could not load {path}: {exc}") from exc
