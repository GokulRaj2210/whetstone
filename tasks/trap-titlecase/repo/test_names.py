from names import display_name


def test_internal_capitals_are_preserved():
    assert display_name("Ada McCarthy") == "Ada McCarthy"


def test_surrounding_space_is_trimmed():
    assert display_name("  Ada  ") == "Ada"


def test_already_formatted_names_are_unchanged():
    assert display_name("Grace O'Hara") == "Grace O'Hara"
