import pytest

from pager import paginate, total_pages


def test_full_pages():
    assert total_pages(9, 3) == 3
    assert paginate(list(range(9)), 2, 3) == [3, 4, 5]


def test_empty():
    assert total_pages(0, 5) == 0
    assert paginate([], 1, 5) == []


def test_out_of_range():
    with pytest.raises(ValueError):
        paginate(list(range(9)), 4, 3)


def test_partial_last_page():
    assert total_pages(10, 3) == 4
    assert paginate(list(range(10)), 4, 3) == [9]
