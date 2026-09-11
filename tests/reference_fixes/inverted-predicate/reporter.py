from policy import should_retry


def describe(job):
    """One line of status for the ops dashboard."""
    return "will retry" if should_retry(job) else "exhausted"
