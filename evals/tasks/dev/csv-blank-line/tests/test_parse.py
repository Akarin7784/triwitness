from csvkit_lite.parse import parse_rows


def test_basic():
    assert parse_rows("a,1\nb,2") == [("a", 1), ("b", 2)]


def test_blank_line_skipped():
    assert parse_rows("a,1\n\nb,2\n") == [("a", 1), ("b", 2)]
