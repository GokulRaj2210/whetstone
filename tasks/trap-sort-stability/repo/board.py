def leaderboard(entries):
    """Rank entries highest score first.

    Ties are broken by name, ascending, so the order is stable and
    readable when several players share a score.
    """
    return sorted(entries, key=lambda e: (e["score"], e["name"]))
