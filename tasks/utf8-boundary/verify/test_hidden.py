from notify import LIMIT, body


def test_short_text_is_unchanged():
    assert body("hello") == b"hello"


def test_long_ascii_is_trimmed_to_the_limit():
    assert len(body("a" * 100)) <= LIMIT


def test_the_result_is_always_decodable():
    # A multi-byte character straddling the limit is the whole point:
    # naive byte slicing produces an undecodable payload.
    for size in range(1, 60):
        assert body("é" * size).decode("utf-8")


def test_multibyte_text_still_fits():
    assert len(body("é" * 100)) <= LIMIT
