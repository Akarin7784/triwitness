Cache.REDIS: issubclass() arg 1 must be a class
In trying https://stackoverflow.com/questions/65686318/sharing-python-objects-across-multiple-workers I've encountered this exception.

Seems hit same issue here: https://github.com/samuelcolvin/pydantic/issues/545#issuecomment-595983173

From docker stderr:
```
app_1    |   File "/app/./main.py", line 8, in <module>
app_1    |     cache = Cache(Cache.REDIS, endpoint="localhost", port=6379, namespace="main")
app_1    |   File "/usr/local/lib/python3.8/site-packages/aiocache/factory.py", line 65, in __new__
app_1    |     assert issubclass(cache_class, BaseCache)
app_1    | TypeError: issubclass() arg 1 must be a class
```

REPL:

```
>>> from aiocache import Cache
ujson module not found, using json
msgpack not installed, MsgPackSerializer unavailable
>>> Cache()
<aiocache.backends.memory.SimpleMemoryCache object at 0x1085fd820>
>>> Cache(Cache.REDIS)
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/Users/variant23/repos/mintad-validator/venv/lib/python3.8/site-packages/aiocache/factory.py", line 65, in __new__
    assert issubclass(cache_class, BaseCache)
TypeError: issubclass() arg 1 must be a class
>>> type(Cache.REDIS)
<class 'NoneType'>
>>> print(Cache.REDIS)
None
>>> print(Cache.MEMORY)
<class 'aiocache.backends.memory.SimpleMemoryCache'>
```

Packages:

```
aiocache==0.11.1
fastapi==0.65.1
pydantic==1.8.2
```
