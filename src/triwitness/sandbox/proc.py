"""宿主进程树管控（spec 002 §5.3-5，硬底线：超时杀整棵进程树）。

- POSIX：`start_new_session=True`，超时 / 结束后 `killpg(SIGKILL)` 整个进程组（顺带清掉后台残留）；
- Windows：每次 exec 建一个 Job Object（`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`）；进程以 CREATE_SUSPENDED 启动，
  加入作业后才恢复运行（没有“先派生子进程再入作业”的竞态）；超时 / 结束时 `TerminateJobObject`，
  关闭句柄 → 作业内所有进程被系统杀掉。
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


def _kernel32():  # type: ignore[no-untyped-def]  # pragma: no cover - 仅 Windows
    """带正确 restype / argtypes 的 kernel32（HANDLE 是指针宽度，默认 c_int 会截断）。"""
    if sys.platform != "win32":
        raise OSError("kernel32 只在 Windows 上可用")
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    H, D, B = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL
    sigs = {
        "CreateJobObjectW": (H, [ctypes.c_void_p, wintypes.LPCWSTR]),
        "SetInformationJobObject": (B, [H, ctypes.c_int, ctypes.c_void_p, D]),
        "AssignProcessToJobObject": (B, [H, H]),
        "TerminateJobObject": (B, [H, ctypes.c_uint]),
        "OpenProcess": (H, [D, B, D]),
        "TerminateProcess": (B, [H, ctypes.c_uint]),
        "GetExitCodeProcess": (B, [H, ctypes.POINTER(D)]),
        "CloseHandle": (B, [H]),
    }
    for name, (res, args) in sigs.items():
        fn = getattr(k32, name)
        fn.restype, fn.argtypes = res, args
    return k32


class _Job:
    """Windows Job Object 的最小封装；非 Windows 上为空操作。"""

    def __init__(self) -> None:
        self.handle: int | None = None
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            k32 = _kernel32()

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

    def assign_and_resume(self, pid: int) -> None:
        """把（挂起中的）进程加入作业，然后恢复运行。加入失败时直接杀掉进程，不放任它在作业外跑。"""
        if sys.platform != "win32" or self.handle is None:
            return
        import ctypes

        k32 = self._k32
        # PROCESS_TERMINATE | PROCESS_SET_QUOTA | PROCESS_SUSPEND_RESUME
        ph = k32.OpenProcess(0x0001 | 0x0100 | 0x0800, False, pid)
        if not ph:
            raise OSError(ctypes.get_last_error(), "OpenProcess 失败")
        try:
            if not k32.AssignProcessToJobObject(self.handle, ph):
                err = ctypes.get_last_error()
                k32.TerminateProcess(ph, 1)
                raise OSError(err, "AssignProcessToJobObject 失败")
            ntdll = ctypes.WinDLL("ntdll")
            ntdll.NtResumeProcess.restype = ctypes.c_long
            ntdll.NtResumeProcess.argtypes = [ctypes.c_void_p]
            if ntdll.NtResumeProcess(ph) != 0:
                k32.TerminateProcess(ph, 1)
                raise OSError(0, "NtResumeProcess 失败")
        finally:
            k32.CloseHandle(ph)

    def kill(self) -> None:
        if sys.platform == "win32" and self.handle is not None:
            self._k32.TerminateJobObject(self.handle, 1)

    def close(self) -> None:
        if sys.platform == "win32" and self.handle is not None:
            self._k32.CloseHandle(self.handle)  # KILL_ON_JOB_CLOSE：剩余进程一并结束
            self.handle = None


def pid_alive(pid: int) -> bool:
    """进程是否还活着（POSIX：信号 0 + 排除僵尸；Windows：OpenProcess + GetExitCodeProcess）。"""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        k32 = _kernel32()
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.get_last_error() == 5  # 拒绝访问 = 存在但属于别人
        try:
            code = wintypes.DWORD()
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        with open(f"/proc/{pid}/stat", encoding="ascii") as f:
            return f.read().rsplit(")", 1)[-1].split()[0] != "Z"
    except OSError:
        return True  # 没有 /proc（macOS）：信号 0 成功即视为活着


def _kill_tree(proc: asyncio.subprocess.Process, job: _Job) -> None:
    if sys.platform == "win32":
        job.kill()
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)


async def _exited(proc: asyncio.subprocess.Process) -> None:
    delay = 0.005
    while proc.returncode is None:
        await asyncio.sleep(delay)
        delay = min(delay * 2, 0.05)


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
        kwargs["creationflags"] = 0x00000200 | 0x00000004  # CREATE_NEW_PROCESS_GROUP | CREATE_SUSPENDED
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
    try:
        job.assign_and_resume(proc.pid)
    except OSError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        job.close()
        raise
    out, err = OutputCollector(max_output_bytes), OutputCollector(max_output_bytes)

    async def pump(stream: asyncio.StreamReader | None, col: OutputCollector) -> None:
        if stream is None:
            return
        while chunk := await stream.read(65536):
            col.add(chunk)

    timed_out = False
    pumps = asyncio.gather(pump(proc.stdout, out), pump(proc.stderr, err))
    try:
        # 不用 proc.wait()：它要等所有管道关闭，后台残留进程（`npm start &`）继承了 stdout 时会一直等到超时。
        # 只看主进程是否已退出（returncode 由子进程监视器设置，与管道无关），退出后再清掉整棵树。
        await asyncio.wait_for(_exited(proc), timeout_s)
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
