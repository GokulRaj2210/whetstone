from invoice import invoice_total
from receipt import receipt_total


def test_receipt_rounds_up():
    assert receipt_total([0.145, 0.145]) == 0.29


def test_invoice_rounds_up_too():
    # The other caller of the same helper. A fix applied only where
    # the symptom was reported leaves this one broken.
    assert invoice_total([(0.145, 2)]) == 0.29


def test_rounding_is_not_just_truncation():
    # Binary floats cannot represent 1.005 exactly, so no correct
    # implementation can be asked to round it "up"; these are values where
    # truncation and rounding genuinely differ.
    assert receipt_total([0.129]) == 0.13
    assert receipt_total([1.0, 0.567]) == 1.57
