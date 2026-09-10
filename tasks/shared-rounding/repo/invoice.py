from money import round_money


def invoice_total(lines):
    """lines: [(unit_price, quantity)]"""
    return round_money(sum(price * qty for price, qty in lines))
