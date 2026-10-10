"""宿主进程树管控（spec 002 §5.3-5，硬底线：超时杀整棵进程树）。

- POSIX：`start_new_session=True`，超时 / 结束后 `killpg(SIGKILL)` 整个进程组（顺带清掉后台残留）；
- Windows：每次 exec 建一个 Job Object（`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`），进程启动后立刻加入；
  超时 `TerminateJobObject`，结束时关闭句柄 → 作业内所有进程被系统杀掉。
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from triwitness.sandbox.base import OutputCollector


@dataclass
class ProcResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    truncated: bool


class _Job:
    """Windows Job Object 的最小封装；非 Windows 上为空操作。"""

    def __init__(self) -> None:
        self.handle: int | None = None
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            k32 = ctypes.WinDLL("kernel32", use_last_error=True)

            class IoCounters(ctypes.Structure):
                _fields_ = [(n, ctypes.c_ulonglong) for n in (
                    "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                    "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]  # fmt: skip

            class BasicLimit(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class ExtLimit(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", BasicLimit),
                    ("IoInfo", IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            job = k32.CreateJobObjectW(None, None)
            if not job:
                raise OSError(ctypes.get_last_error(), "CreateJobObjectW 失败")
            info = ExtLimit()
            info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
                k32.CloseHandle(job)
                raise OSError(ctypes.get_last_error(), "SetInformationJobObject 失败")
            self.handle = job
            self._k32 = k32

    def assign(self, pid: int) -> None:
        if sys.platform == "win32" and self.handle is not None:
            k32 = self._k32
            ph = k32.OpenProcess(0x0001 | 0x0100, False, pid)  # PROCESS_TERMINATE | PROCESS_SET_QUOTA
            if ph:
                try:
                    k32.AssignProcessToJobObject(self.handle, ph)
                finally:
                    k32.CloseHandle(ph)

    def kill(self) -> None:
        if sys.platform == "win32" and self.handle is not None:
            self._k32.TerminateJobObject(self.handle, 1)

    def close(self) -> None:
        if sys.platform == "win32" and self.handle is not None:
            self._k32.CloseHandle(self.handle)  # KILL_ON_JOB_CLOSE：剩余进程一并结束
            self.handle = None


def _kill_tree(proc: asyncio.subprocess.Process, job: _Job) -> None:
    if sys.platform == "win32":
        job.kill()
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)


async def run_tree(
    argv: Sequence[str],
    *,
    cwd: str,
    env: Mapping[str, str],
    timeout_s: float,
    max_output_bytes: int,
) -> ProcResult:
    """运行命令并管控整棵进程树。stdin 为空；输出流式头尾截断。"""
    started = time.monotonic()
    job = _Job()
    kwargs: dict[str, object] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000200  # CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        env=dict(env),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **kwargs,  # type: ignore[arg-type]
    )
    job.assign(proc.pid)
    out, err = OutputCollector(max_output_bytes), OutputCollector(max_output_bytes)

    async def pump(stream: asyncio.StreamReader | None, col: OutputCollector) -> None:
        if stream is None:
            return
        while chunk := await stream.read(65536):
            col.add(chunk)

    timed_out = False
    pumps = asyncio.gather(pump(proc.stdout, out), pump(proc.stderr, err))
    try:
        await asyncio.wait_for(proc.wait(), timeout_s)
    except TimeoutError:
        timed_out = True
    finally:
        # 无论正常结束还是超时，都清掉整棵树（后台残留进程会占着管道）
        _kill_tree(proc, job)
        with contextlib.suppress(ProcessLookupError):
            await proc.wait()
        try:
            await asyncio.wait_for(pumps, 5)
        except TimeoutError:
            pumps.cancel()
        job.close()
    so, t1 = out.result()
    se, t2 = err.result()
    code = 124 if timed_out else (proc.returncode if proc.returncode is not None else -1)
    if timed_out:
        se = (se + f"\n[超时 {timeout_s:g}s，已杀掉整个进程树]").strip()
    return ProcResult(
        exit_code=code,
        stdout=so,
        stderr=se,
        duration_ms=int((time.monotonic() - started) * 1000),
        timed_out=timed_out,
        truncated=t1 or t2,
    )
