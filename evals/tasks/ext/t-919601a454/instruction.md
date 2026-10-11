`check_expires=True` produces an error
`extract_params` uses `urllib.parse.parse_qs`, which will return a _list_ for every parameter:
```python
qs = urllib.parse.parse_qs('foo=bar')
# qs = { 'foo': ['bar'] }
```

`extract_params(payload).get('expires')` is then fed into `int()`, which obviously throws, because you cannot convert a list to an int.
