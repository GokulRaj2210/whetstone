MAX_ATTEMPTS = 3


def should_retry(job):
    """True when the job has attempts left and may be retried again."""
    return job["attempts"] >= MAX_ATTEMPTS
