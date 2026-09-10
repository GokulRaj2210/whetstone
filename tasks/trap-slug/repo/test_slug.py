from slug import slug


def test_spaces_become_hyphens():
    assert slug("hello world") == "hello-world"


def test_already_lowercase_is_unchanged():
    assert slug("simple") == "simple"


def test_multiple_words():
    assert slug("The Quick Brown Fox") == "the-quick-brown-fox"
