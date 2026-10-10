B017: False negative when "from" imports used
## Summary
B017 fails when raises is imported directly

## Version
Replicated on version `23.9.16`

## Sample code
```
import pytest
from pytest import raises


def foo():
    raise


def test_pytest_raises():
    with raises(Exception):
        foo()
    with pytest.raises(Exception):
        foo()
```
