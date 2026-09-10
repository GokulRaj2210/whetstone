from recent import recent


def test_order_is_preserved():
    assert recent([30, 10, 20]) == [30, 10, 20]


def test_a_single_item():
    assert recent([7]) == [7]


def test_empty():
    assert recent([]) == []
