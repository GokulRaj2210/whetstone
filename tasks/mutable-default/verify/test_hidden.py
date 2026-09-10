from report import add_section, build_report


def test_build_report_is_independent_between_calls():
    assert build_report(["a", "b"]) == ["a", "b"]
    assert build_report(["c"]) == ["c"]


def test_add_section_does_not_accumulate_across_calls():
    # The definition itself must be fixed, not just its caller.
    assert add_section("x") == ["x"]
    assert add_section("y") == ["y"]


def test_an_explicit_list_is_still_appended_to():
    existing = ["kept"]
    assert add_section("new", existing) == ["kept", "new"]
