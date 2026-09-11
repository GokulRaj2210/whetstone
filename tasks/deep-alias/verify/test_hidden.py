from config import Config
from service import handle


def test_nested_edits_do_not_leak_to_the_original():
    base = Config()
    clone = base.clone()
    clone["db"]["host"] = "otherhost"
    assert base["db"]["host"] == "localhost"


def test_clones_are_independent_of_each_other():
    base = Config()
    a, b = base.clone(), base.clone()
    a["cache"]["ttl"] = 1
    assert b["cache"]["ttl"] == 60


def test_requests_do_not_leak_into_the_defaults():
    first = handle({"debug": True})
    second = handle({})
    assert first["debug"] is True
    assert second["debug"] is False


def test_top_level_edits_still_work():
    clone = Config().clone()
    clone["debug"] = True
    assert clone["debug"] is True
