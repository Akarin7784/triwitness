import pytest

from minicache import LRUCache


def test_put_get():
    c = LRUCache(2)
    c.put("a", 1)
    assert c.get("a") == 1
    assert c.get("zz", 0) == 0


def test_capacity():
    c = LRUCache(2)
    for k in "abc":
        c.put(k, k)
    assert len(c) == 2
    assert c.get("a") is None


def test_bad_capacity():
    with pytest.raises(ValueError):
        LRUCache(0)


def test_get_refreshes():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    c.put("c", 3)
    assert c.get("a") == 1
    assert c.get("b") is None


def test_missing_get_does_not_insert():
    c = LRUCache(1)
    c.put("a", 1)
    assert c.get("x") is None
    assert len(c) == 1
