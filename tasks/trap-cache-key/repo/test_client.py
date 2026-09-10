import client
from client import fetch


def setup_function():
    client.CALLS.clear()
    client._CACHE.clear()


def test_repeated_identical_request_is_cached():
    fetch("/a", {"x": 1})
    fetch("/a", {"x": 1})
    assert len(client.CALLS) == 1


def test_different_paths_are_separate():
    fetch("/a")
    fetch("/b")
    assert len(client.CALLS) == 2


def test_param_order_does_not_create_a_second_entry():
    # Passes on the current code because params are ignored entirely. It is
    # here so that a fix which keys on the params' *repr* is caught by running
    # the suite: {"x": 1, "y": 2} and {"y": 2, "x": 1} stringify differently.
    fetch("/a", {"x": 1, "y": 2})
    fetch("/a", {"y": 2, "x": 1})
    assert len(client.CALLS) == 1
