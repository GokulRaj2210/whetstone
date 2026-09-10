from slug import slug


def test_punctuation_is_removed():
    assert slug("Hello, World") == "hello-world"


def test_hyphens_survive_the_punctuation_filter():
    # The trap: filtering to alphanumerics after hyphenating removes the
    # hyphens too, which the visible suite catches and an inline check
    # of the reported case alone does not.
    assert slug("hello world") == "hello-world"
    assert slug("The Quick Brown Fox") == "the-quick-brown-fox"


def test_mixed():
    assert slug("Don't Panic!") == "dont-panic"
