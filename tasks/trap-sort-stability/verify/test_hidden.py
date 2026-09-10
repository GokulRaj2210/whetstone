from board import leaderboard


def test_highest_score_comes_first():
    ranked = leaderboard(
        [{"name": "amy", "score": 3}, {"name": "bob", "score": 9}]
    )
    assert [e["name"] for e in ranked] == ["bob", "amy"]


def test_ties_are_still_broken_by_name_ascending():
    # The trap: `reverse=True` fixes the score order and silently
    # reverses the name tie-break, breaking the visible test.
    ranked = leaderboard(
        [{"name": "zoe", "score": 10}, {"name": "amy", "score": 10}]
    )
    assert [e["name"] for e in ranked] == ["amy", "zoe"]


def test_empty_board_still_empty():
    assert leaderboard([]) == []
