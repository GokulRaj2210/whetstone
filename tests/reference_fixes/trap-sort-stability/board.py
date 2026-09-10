def leaderboard(entries):
    """Rank entries highest score first, ties broken by name ascending."""
    return sorted(entries, key=lambda e: (-e["score"], e["name"]))
