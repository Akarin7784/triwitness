Statement.get_type() does not skip comments between subqueries.
SQL query can contain comment in between WITH multiple query but the `get_type()` implementation doesn't skip them

```python
>>> query, = sqlparse.parse("""
WITH A AS (),
          -- A comment about the B subquery...
          B AS ()
SELECT * FROM B
""")
>>> query.get_type()
'UNKNOWN'
```

Without the comment:

```python
>>> query, = sqlparse.parse("""
WITH A AS (),
          B AS ()
SELECT * FROM B
""")
>>> query.get_type()
'SELECT'
```
