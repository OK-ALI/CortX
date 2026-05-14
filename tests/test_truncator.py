from __future__ import annotations

from backend.processor.truncator import truncate_words


def test_truncate_words_limits_length() -> None:
    text = "one two three four five"
    assert truncate_words(text, 3) == "one two three"


def test_truncate_words_keeps_short_text() -> None:
    text = "alpha beta"
    assert truncate_words(text, 5) == "alpha beta"
