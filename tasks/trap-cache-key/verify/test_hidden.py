import client
from client import fetch


def setup_function():
    client.CALLS.clear()
    client._CACHE.clear()


def test_different_params_are_not_the_same_entry():
    assert fetch("/a", {"x": 1}) != fetch("/a", {"x": 2})
    assert len(client.CALLS) == 2


def test_param_order_does_not_create_a_second_entry():
    fetch("/a", {"x": 1, "y": 2})
    fetch("/a", {"y": 2, "x": 1})
    assert len(client.CALLS) == 1


def test_caching_still_works_at_all():
    # The trap: keying on a dict repr, or disabling the cache to
    # stop the collision, breaks the visible caching test.
    fetch("/a", {"x": 1})
    fetch("/a", {"x": 1})
    assert len(client.CALLS) == 1
