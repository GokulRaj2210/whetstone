def display_name(name):
    """Format an author name for display."""
    return " ".join(word[:1].upper() + word[1:] for word in name.strip().split())
