import pytest
import store


def test_rename_is_visible():
    assert store.get_user(1)["name"] == "ada"
    store.rename_user(1, "ada l")
    assert store.get_user(1)["name"] == "ada l"


def test_delete_is_visible_too():
    # The other writer against the same cache. Invalidating only in
    # `rename_user` leaves this one serving a deleted row.
    assert store.get_user(2)["name"] == "grace"
    store.delete_user(2)
    with pytest.raises(KeyError):
        store.get_user(2)
