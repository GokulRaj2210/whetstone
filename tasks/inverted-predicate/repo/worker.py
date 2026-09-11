from policy import should_retry


def run_job(job):
    """Run a job, rescheduling it while it may be retried."""
    job["attempts"] += 1
    if should_retry(job):
        return "rescheduled"
    return "dropped"
