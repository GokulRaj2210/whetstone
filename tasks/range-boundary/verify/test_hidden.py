from pages import parse_range


def test_both_endpoints_are_inclusive():
    assert parse_range("1-5") == [1, 2, 3, 4, 5]


def test_a_single_page_still_works():
    assert parse_range("7") == [7]


def test_whitespace_is_ignored():
    assert parse_range("  2-4 ") == [2, 3, 4]


def test_a_degenerate_range_is_one_page():
    assert parse_range("3-3") == [3]
