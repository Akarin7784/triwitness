`SELECT * REPLACE` isn't currently handled
Hi David,

https://cloud.google.com/bigquery/docs/reference/standard-sql/query-syntax#select_replace

sqlvalidator 0.0.18:

```diff
- SELECT * REPLACE('bar' AS foo)
+ SELECT * REPLACE
```

A quick unit test causes
```
self = <Alias: <Column: '*'> as=False 'REPLACE'>

    def __str__(self):
>       return str(self.value)
E       AttributeError: 'Alias' object has no attribute 'value'

../../sqlvalidator/grammar/sql.py:239: AttributeError
```
when trying to print the expression
