`minicache.LRUCache` evicts the wrong entry. With capacity 2: `put("a")`, `put("b")`, `get("a")`, `put("c")` —
`"a"` was just read, so `"b"` should be evicted, but `"a"` disappears instead.
