import limiter


def setup_function():
    limiter._COUNTS.clear()


def test_hits_accumulate():
    for _ in range(3):
        limiter.record("ada")
    assert limiter.hits("ada") == 3


def test_a_user_is_blocked_past_the_limit():
    for _ in range(3):
        limiter.record("ada")
    assert limiter.allowed("ada") is False


def test_users_are_counted_separately():
    limiter.record("ada")
    assert limiter.hits("grace") == 0


def test_a_fresh_user_is_allowed():
    assert limiter.allowed("new") is True
