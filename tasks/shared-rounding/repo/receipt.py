from money import round_money


def receipt_total(prices):
    return round_money(sum(prices))
