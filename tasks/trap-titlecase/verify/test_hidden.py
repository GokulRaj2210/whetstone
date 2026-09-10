from names import display_name


def test_lowercase_names_are_capitalised():
    assert display_name("ada lovelace") == "Ada Lovelace"


def test_internal_capitals_survive_the_casing_fix():
    # The trap: str.title() lowercases the rest of every word, turning
    # "McCarthy" into "Mccarthy". The visible suite catches it; an inline
    # check of the reported name alone does not.
    assert display_name("Ada McCarthy") == "Ada McCarthy"


def test_trimming_still_happens():
    assert display_name("  ada  ") == "Ada"
