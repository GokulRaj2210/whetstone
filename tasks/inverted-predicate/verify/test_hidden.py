from policy import should_retry
from reporter import describe
from worker import run_job


def test_a_job_with_attempts_left_may_retry():
    assert should_retry({"attempts": 1}) is True


def test_an_exhausted_job_may_not():
    assert should_retry({"attempts": 3}) is False


def test_the_worker_drops_exhausted_jobs():
    assert run_job({"attempts": 2}) == "dropped"


def test_the_worker_still_reschedules_young_jobs():
    assert run_job({"attempts": 0}) == "rescheduled"


def test_the_dashboard_still_reads_correctly():
    # The other caller. It compensates for the inverted predicate today,
    # so fixing the predicate without fixing this reverses the dashboard.
    assert describe({"attempts": 3}) == "exhausted"
    assert describe({"attempts": 0}) == "will retry"
