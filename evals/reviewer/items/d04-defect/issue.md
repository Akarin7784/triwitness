`pager.total_pages(10, per_page=3)` returns 3 but there are 4 pages, and `pager.paginate(items, page=4, per_page=3)`
raises `ValueError: page out of range` for a 10-item list instead of returning the last item.
