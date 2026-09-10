from summary import summarise


def test_short_text_is_unchanged():
    assert summarise("hello world") == "hello world"


def test_long_text_is_truncated_with_an_ellipsis():
    assert summarise("the quick brown fox jumps over") == "the quick brown fox\u2026"


def test_limit_is_respected():
    assert len(summarise("a" * 50)) == 20
