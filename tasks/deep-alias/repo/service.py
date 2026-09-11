from config import Config


def handle(request_overrides):
    """Each request gets its own view of the settings."""
    settings = Config().clone()
    for key, value in request_overrides.items():
        settings[key] = value
    return settings
