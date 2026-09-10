from render import render


def test_ampersands_are_escaped():
    assert render("Tom & Jerry") == "Tom &amp; Jerry"


def test_angle_brackets_are_not_double_escaped():
    # The trap. Appending `.replace("&", "&amp;")` at the end of the chain
    # fixes the reported symptom and turns "&lt;" into "&amp;lt;", breaking
    # the visible suite. The docstring says which order is required.
    assert render("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"


def test_a_mixed_string_is_escaped_once_each():
    assert render("a & <b>") == "a &amp; &lt;b&gt;"


def test_plain_text_still_unchanged():
    assert render("hello world") == "hello world"
