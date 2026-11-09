"""A share is never 100% unless all, nor 0% unless none (56 of 170,000 differing is not "100%")."""

from oakbox.wizard.checks import share_text


def test_share_text_never_rounds_to_all_or_none():
    assert share_text(169_944, 170_000) == "99.9%"
    assert share_text(170_000, 170_000) == "100%"
    assert share_text(56, 170_000) == "0.1%"
    assert share_text(0, 170_000) == "0%"
    assert share_text(1, 2) == "50%"
