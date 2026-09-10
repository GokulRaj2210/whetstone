from billing import average_invoice
from dashboard import average_response_ms
from stats import mean


def test_dashboard_average_is_fractional():
    assert average_response_ms([0.4, 0.6]) == 0.5


def test_billing_average_is_fractional_too():
    assert average_invoice([1.0, 2.0]) == 1.5


def test_mean_of_ints_is_still_exact():
    assert mean([2, 4]) == 3
