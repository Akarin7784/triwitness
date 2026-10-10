import pytest

from timefmt import parse_duration


def test_seconds():
    assert parse_duration("45s") == 45


def test_hours():
    assert parse_duration("2h") == 7200


def test_invalid():
    with pytest.raises(ValueError):
        parse_duration("1x")


def test_minutes():
    assert parse_duration("2m") == 120


def test_combined():
    assert parse_duration("1h30m15s") == 5415
