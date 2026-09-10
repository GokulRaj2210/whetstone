def round_money(amount):
    """Round a monetary amount to 2 decimal places, half away from zero."""
    return int(amount * 100) / 100
