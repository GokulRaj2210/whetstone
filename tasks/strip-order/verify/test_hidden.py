from csv_import import tags_from_csv
from form_import import tags_from_form
from normalise import clean_token


def test_csv_tags_have_no_punctuation():
    assert tags_from_csv("urgent, Bug ,") == ["urgent", "bug"]


def test_form_tags_are_cleaned_too():
    # The other caller of the same normaliser.
    assert tags_from_form("Urgent! bug.") == ["urgent", "bug"]


def test_clean_token_lowercases_and_trims():
    assert clean_token("  Hello!  ") == "hello"
