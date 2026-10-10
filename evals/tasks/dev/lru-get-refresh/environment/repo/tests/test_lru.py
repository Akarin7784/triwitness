from minicache import LRUCache


def test_put_get():
    c = LRUCache(2)
    c.put("a", 1)
    assert c.get("a") == 1
    assert c.get("zz", 0) == 0
