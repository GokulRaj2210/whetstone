import time


def with_retries(call, attempts=3, delay=0.0):
    """Call `call()`, retrying on exception. `attempts` is the total calls."""
    last = None
    for index in range(attempts):
        try:
            return call()
        except Exception as exc:
            last = exc
            if index < attempts - 1:
                time.sleep(delay)
    raise last
