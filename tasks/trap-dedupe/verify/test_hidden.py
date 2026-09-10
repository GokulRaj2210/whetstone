from recent import recent


def test_duplicates_are_removed():
    assert recent([10, 20, 10]) == [10, 20]


def test_order_survives_deduplication():
    # The trap: list(set(ids)) removes duplicates and returns them in
    # ascending order, which the visible suite catches.
    assert recent([30, 10, 20]) == [30, 10, 20]


def test_first_occurrence_wins():
    assert recent([5, 9, 5, 1]) == [5, 9, 1]
