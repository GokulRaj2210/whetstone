from render import render


def test_escapes_angle_brackets():
    assert render("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"


def test_plain_text_is_unchanged():
    assert render("hello world") == "hello world"


def test_empty_string():
    assert render("") == ""
