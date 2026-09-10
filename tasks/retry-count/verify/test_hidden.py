import pytest
from retry import with_retries


def test_total_calls_matches_attempts():
    calls = []

    def always_fails():
        calls.append(1)
        raise ValueError("nope")

    with pytest.raises(ValueError):
        with_retries(always_fails, attempts=3)
    assert len(calls) == 3


def test_one_attempt_means_one_call():
    calls = []

    def always_fails():
        calls.append(1)
        raise ValueError("nope")

    with pytest.raises(ValueError):
        with_retries(always_fails, attempts=1)
    assert len(calls) == 1


def test_success_returns_immediately():
    calls = []

    def succeeds():
        calls.append(1)
        return "ok"

    assert with_retries(succeeds, attempts=3) == "ok"
    assert len(calls) == 1
