Invariant of a subclass applies to its base
Invariants of subclasses affect their base classes, as well as sibling classes.

Here is a example to reproduce the problem:
```
from icontract import invariant

@invariant(lambda: True)
class Base:
    pass

@invariant(lambda: False)
class Derived(Base):
    pass

Base()  # ViolationError
```

By the way, thanks for the nice library!
