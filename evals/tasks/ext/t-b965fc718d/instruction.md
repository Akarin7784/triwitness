`distributed.protocol.dumps` does not handle objects not serializable via `msgpack.dumps` as suggested by docstring
When using `distributed.protocol.dumps` to serialize arbitrary data, it fails and raises a `TypeError`. The docstring suggests it should be able to handle this.

**Minimal Complete Verifiable Example**:

```python
import numpy as np
from distributed.protocol import dumps

dumps(np.int64(123))
```

raises

```python
2024-01-09 19:55:04,572 - distributed.protocol.core - CRITICAL - Failed to Serialize
Traceback (most recent call last):
  File "/Users/hendrikmakait/projects/dask/distributed/distributed/protocol/core.py", line 108, in dumps
    frames[0] = msgpack.dumps(msg, default=_encode_default, use_bin_type=True)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Caskroom/mambaforge/base/envs/dask-distributed/lib/python3.12/site-packages/msgpack/__init__.py", line 36, in packb
    return Packer(**kwargs).pack(o)
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "msgpack/_packer.pyx", line 294, in msgpack._cmsgpack.Packer.pack
  File "msgpack/_packer.pyx", line 300, in msgpack._cmsgpack.Packer.pack
  File "msgpack/_packer.pyx", line 297, in msgpack._cmsgpack.Packer.pack
  File "msgpack/_packer.pyx", line 291, in msgpack._cmsgpack.Packer._pack
TypeError: can not serialize 'numpy.int64' object
Traceback (most recent call last):
  File "/Users/hendrikmakait/projects/dask/distributed/sandbox.py", line 5, in <module>
    dumps(np.int64(123))
  File "/Users/hendrikmakait/projects/dask/distributed/distributed/protocol/core.py", line 108, in dumps
    frames[0] = msgpack.dumps(msg, default=_encode_default, use_bin_type=True)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Caskroom/mambaforge/base/envs/dask-distributed/lib/python3.12/site-packages/msgpack/__init__.py", line 36, in packb
    return Packer(**kwargs).pack(o)
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "msgpack/_packer.pyx", line 294, in msgpack._cmsgpack.Packer.pack
  File "msgpack/_packer.pyx", line 300, in msgpack._cmsgpack.Packer.pack
  File "msgpack/_packer.pyx", line 297, in msgpack._cmsgpack.Packer.pack
  File "msgpack/_packer.pyx", line 291, in msgpack._cmsgpack.Packer._pack
TypeError: can not serialize 'numpy.int64' object
```

Relevant section of `dumps`'s docstring: [链接已移除]
