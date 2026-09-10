from summary import summarise


def test_empty_text_returns_empty():
    assert summarise("") == ""


def test_whitespace_only_returns_empty():
    assert summarise("   ") == ""


def test_the_existing_behaviour_still_holds():
    # The trap: returning early on falsy input, or dropping the
    # truncation branch, silences the crash and breaks these.
    assert summarise("hello world") == "hello world"
    assert summarise("the quick brown fox jumps over") == "the quick brown fox\u2026"
    assert len(summarise("a" * 50)) == 20
