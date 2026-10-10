from csvkit_lite.parse import parse_rows


def test_basic():
    assert parse_rows("a,1\nb,2") == [("a", 1), ("b", 2)]
