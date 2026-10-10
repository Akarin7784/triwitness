"""W2-33：只在真实 Windows 上跑（windows-latest CI）——Job Object 杀进程树、Git Bash 探测 / PowerShell 兜底、
8.3 短名与路径规范化。其他平台整体跳过（对应逻辑在 Linux 上由模拟用例覆盖）。"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="真实 Windows 用例（W2-33）")

SPAWN = """import os, subprocess, sys, time
open(sys.argv[1], "w").write(str(os.getpid()))
if len(sys.argv) > 2:
    subprocess.Popen([sys.executable, __file__, sys.argv[2]])
time.sleep(300)
"""


async def _pid(path: Path, timeout: float = 15) -> int:
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        try:
            return int(path.read_text())
        except (OSError, ValueError):
            await asyncio.sleep(0.05)
    raise AssertionError(f"{path.name} 没写出来")


# ------------------------------------------------------------------ Job Object
async def test_job_object_kills_tree_on_timeout(tmp_path: Path) -> None:
    from triwitness.sandbox.proc import pid_alive, run_tree

    (tmp_path / "spawn.py").write_text(SPAWN)
    task = asyncio.create_task(run_tree([sys.executable, "spawn.py", "child.pid", "grand.pid"], cwd=str(tmp_path),
                                        env=dict(os.environ), timeout_s=5, max_output_bytes=10_000))  # fmt: skip
    pids = [await _pid(tmp_path / "child.pid"), await _pid(tmp_path / "grand.pid")]
    assert all(pid_alive(p) for p in pids)
    r = await task
    assert r.timed_out and r.exit_code == 124 and "进程树" in r.stderr
    await asyncio.sleep(0.5)
    assert not any(pid_alive(p) for p in pids)


async def test_job_object_kills_leftovers_after_exit(tmp_path: Path) -> None:
    from triwitness.sandbox.proc import pid_alive, run_tree

    (tmp_path / "spawn.py").write_text(SPAWN)
    code = ("import subprocess, sys, time, os\n"
            "subprocess.Popen([sys.executable, 'spawn.py', 'bg.pid'])\n"
            "while not os.path.exists('bg.pid') or not open('bg.pid').read(): time.sleep(0.05)\n"
            "print('parent done')")  # fmt: skip
    r = await run_tree([sys.executable, "-c", code], cwd=str(tmp_path), env=dict(os.environ), timeout_s=30,
                       max_output_bytes=10_000)  # fmt: skip
    assert r.exit_code == 0 and not r.timed_out and "parent done" in r.stdout
    pid = int((tmp_path / "bg.pid").read_text())
    await asyncio.sleep(0.5)
    assert not pid_alive(pid)


async def test_suspended_start_still_runs_and_streams(tmp_path: Path) -> None:
    from triwitness.sandbox.proc import run_tree

    r = await run_tree([sys.executable, "-c", "print('hi'); import sys; sys.exit(3)"], cwd=str(tmp_path),
                       env=dict(os.environ), timeout_s=30, max_output_bytes=10_000)  # fmt: skip
    assert r.stdout.strip() == "hi" and r.exit_code == 3


def test_pid_alive() -> None:
    from triwitness.sandbox.proc import pid_alive

    assert pid_alive(os.getpid())
    assert not pid_alive(999_999_999)


# ------------------------------------------------------------------ Git Bash / PowerShell
async def test_git_bash_detected_and_runs(tmp_path: Path) -> None:
    from triwitness.sandbox.local import find_shell
    from triwitness.sandbox.proc import run_tree

    sh = find_shell()
    low = sh.exe.lower().replace("/", "\\")
    assert sh.kind == "bash" and low.endswith("bash.exe"), sh
    assert "\\system32\\" not in low and "\\windowsapps\\" not in low
    assert Path(sh.exe).is_file()
    r = await run_tree(sh.argv("echo $BASH_VERSION; uname -s"), cwd=str(tmp_path), env=dict(os.environ),
                       timeout_s=30, max_output_bytes=10_000)  # fmt: skip
    assert r.exit_code == 0 and r.stdout.split()[0][0].isdigit() and "MINGW" in r.stdout.upper()


async def test_powershell_fallback_runs(tmp_path: Path) -> None:
    from triwitness.sandbox.local import find_shell
    from triwitness.sandbox.proc import run_tree

    sh = find_shell(windows=True, exists=lambda p: False, git_exec_path=lambda: None)
    assert sh.kind == "powershell" and Path(sh.exe).name.lower() in ("pwsh.exe", "powershell.exe")
    r = await run_tree(sh.argv("Write-Output ('a' + 'b'); exit 4"), cwd=str(tmp_path), env=dict(os.environ),
                       timeout_s=60, max_output_bytes=10_000)  # fmt: skip
    assert r.stdout.strip() == "ab" and r.exit_code == 4


# ------------------------------------------------------------------ 8.3 短名与路径规范化
def _short(p: Path) -> str:
    if sys.platform != "win32":
        return str(p)
    import ctypes

    buf = ctypes.create_unicode_buffer(32768)
    n = ctypes.windll.kernel32.GetShortPathNameW(str(p), buf, 32768)
    return buf.value if n else str(p)


def test_windows_long_name_expands_real_short_path(tmp_path: Path) -> None:
    from triwitness.permissions.paths import normalize_path, windows_long_name

    long_dir = tmp_path / "Program Files Like Dir"
    long_dir.mkdir()
    short = _short(long_dir)
    if "~" not in short:
        pytest.skip("该卷未启用 8.3 短名")
    np = normalize_path(short + "\\new.txt", cwd="/", home="/", windows=True, long_name=windows_long_name)
    expect = normalize_path(str(long_dir) + "\\new.txt", cwd="/", home="/", windows=True,
                            long_name=windows_long_name)  # fmt: skip
    assert "short_name" not in np.flags and np.path == expect.path
    assert np.path.lower().endswith("/program files like dir/new.txt")


def test_engine_on_real_windows_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from triwitness.permissions.config import SessionOverrides, load_policy
    from triwitness.permissions.engine import Action, PermissionEngine

    monkeypatch.delenv("CI", raising=False)
    repo = tmp_path / "Repo Dir"
    (repo / ".git").mkdir(parents=True)
    (repo / "src").mkdir()
    pol = load_policy(repo, backend="none", interactive=True, session=SessionOverrides(mode="auto_edit"),
                      home=tmp_path / "twhome", managed_path=tmp_path / "managed.yaml")  # fmt: skip
    # 用短名形式给工作区（TEMP 在 GitHub runner 上就是 RUNNER~1 形式），引擎应展开后照常判断
    e = PermissionEngine(pol, workspace=_short(repo))
    assert e.windows and "~" not in e.workspace

    def edit(p: str) -> str:
        return e.check(Action("Edit", p, tool="edit_file")).decision

    assert edit(str(repo / "src" / "a.py")) == "allow"
    assert edit(str(repo / "SRC" / "B.PY").upper()) == "allow"  # 大小写不敏感
    assert edit("src\\c.py") == "allow"
    assert edit(str(repo / ".git" / "config")) == "deny"
    assert edit(str(repo / ".GIT" / "CONFIG")) == "deny"
    assert edit(str(repo / "src" / "a.py") + "::$DATA") != "allow"  # NTFS 备用数据流
    assert edit(str(tmp_path / "outside.txt")) == "ask"
    assert edit("\\\\server\\share\\x.txt") != "allow"  # UNC
