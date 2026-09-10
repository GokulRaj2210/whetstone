from board import leaderboard


def test_ties_are_broken_by_name_ascending():
    ranked = leaderboard(
        [
            {"name": "zoe", "score": 10},
            {"name": "amy", "score": 10},
        ]
    )
    assert [e["name"] for e in ranked] == ["amy", "zoe"]


def test_an_empty_board_is_empty():
    assert leaderboard([]) == []
