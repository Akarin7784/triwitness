from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def total_pages(count: int, per_page: int) -> int:
    if per_page <= 0:
        raise ValueError("per_page must be positive")
    return count // per_page


def paginate(items: Sequence[T], page: int, per_page: int) -> list[T]:
    """page 从 1 开始。"""
    pages = total_pages(len(items), per_page)
    if page < 1 or page > max(pages, 1):
        raise ValueError("page out of range")
    start = (page - 1) * per_page
    return list(items[start : start + per_page])
