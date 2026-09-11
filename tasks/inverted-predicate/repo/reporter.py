from policy import should_retry


def describe(job):
    """One line of status for the ops dashboard."""
    # Reads backwards on purpose today, to compensate for should_retry.
    return "exhausted" if not should_retry(job) else "will retry"
