from pager import paginate, total_pages


def test_full_pages():
    assert total_pages(9, 3) == 3
    assert paginate(list(range(9)), 2, 3) == [3, 4, 5]
