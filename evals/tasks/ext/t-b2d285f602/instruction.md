`distributed.Client.register_worker_plugin` silently discards `**kwargs`
**What happened**:
An issue was [raised in slack](https://coiled-users.slack.com/archives/C0195GJKQ1G/p1643038235023300) regarding `UploadPlugin` failing to update the `sys.path` or restart workers. It was clear from the example code that `update_path=True` and `restart=True`, however these `kwargs` are actually ignored because a plugin instance was passed instead of a class.

**Minimal Complete Verifiable Example**:

```python
import asyncio
import pathlib
import tempfile

import distributed
from distributed import Nanny
from distributed.diagnostics.plugin import UploadDirectory


def run_demo_module():
    import demo_module

    return demo_module.demo_function()


async def amain():
    async with distributed.Client(
        processes=True, security=True, asynchronous=True
    ) as client:
        with tempfile.TemporaryDirectory() as tmpdir_fn:
            tmpdir = pathlib.Path(tmpdir_fn)
            (tmpdir / "demo_module.py").write_bytes(
                b'def demo_function(): return "hello"\n'
            )

            await client.register_worker_plugin(
                UploadDirectory(tmpdir),
                update_path=True,
                restart=True,
                nanny=True,
            )

        assert await client.submit(run_demo_module) == "hello"


if __name__ == "__main__":
    asyncio.run(amain())
```

results in:

```pytb
distributed.worker - WARNING - Compute Failed
Function:  run_demo_module
args:      ()
kwargs:    {}
Exception: 'ModuleNotFoundError("No module named \'demo_module\'")'

Traceback (most recent call last):
  File "demo.py", line 37, in <module>
    asyncio.run(amain())
  File "/home/graingert/miniconda3/envs/my_env/lib/python3.8/asyncio/runners.py", line 43, in run
    return loop.run_until_complete(main)
  File "/home/graingert/miniconda3/envs/my_env/lib/python3.8/asyncio/base_events.py", line 616, in run_until_complete
    return future.result()
  File "demo.py", line 32, in amain
    assert await client.submit(run_demo_module) == "hello"
  File "/home/graingert/miniconda3/envs/my_env/lib/python3.8/site-packages/distributed/client.py", line 245, in _result
    raise exc.with_traceback(tb)
  File "demo.py", line 10, in run_demo_module
    import demo_module
ModuleNotFoundError: No module named 'demo_module'
```

for this case the fix is to apply the kwargs directly to `UploadDirectory`:
```diff
@@ -24,9 +24,11 @@
             )
 
             await client.register_worker_plugin(
-                UploadDirectory(tmpdir),
-                update_path=True,
-                restart=True,
+                UploadDirectory(
+                    tmpdir,
+                    update_path=True,
+                    restart=True,
+                ),
                 nanny=True,
             )
```
