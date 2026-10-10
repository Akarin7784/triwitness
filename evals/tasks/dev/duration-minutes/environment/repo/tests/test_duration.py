import pytest

from timefmt import parse_duration


def test_seconds():
    assert parse_duration("45s") == 45


def test_invalid():
    with pytest.raises(ValueError):
        parse_duration("abc")
