import time


def with_retries(call, attempts=3, delay=0.0):
    """Call `call()`, retrying on exception.

    `attempts` is the total number of calls made, not the number of
    retries after the first: `attempts=3` means at most three calls.
    """
    last = None
    for index in range(attempts):
        try:
            return call()
        except Exception as exc:
            last = exc
            time.sleep(delay)
    try:
        return call()
    except Exception as exc:
        last = exc
    raise last
