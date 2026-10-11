Trivial function with docstring reports complexity of 2
```python
def f():
    """hi"""
    x = 1


def g():
    """hi"""
```

```
$ python3.5 mccabe.py test.py
1:0: 'f' 1
6:0: 'g' 2
```

```
$ git rev-parse HEAD
[提交号已移除]
```
