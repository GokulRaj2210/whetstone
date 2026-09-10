import sys

from config import ConfigError, load_config


def main(path):
    try:
        settings = load_config(path)
    except ConfigError as exc:
        print(f"bad config: {exc}", file=sys.stderr)
        return 1
    print(f"started with {len(settings)} setting(s)")
    return 0
