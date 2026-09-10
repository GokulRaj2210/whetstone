def leaderboard(entries):
    """Rank entries highest score first."""
    return sorted(entries, key=lambda e: (e["score"], e["name"]), reverse=True)
