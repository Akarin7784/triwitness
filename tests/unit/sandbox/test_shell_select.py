"""AC15：Windows 上 Git Bash 查找与 PowerShell 兜底（注入假文件系统，在 Linux 上模拟）。"""

from __future__ import annotations

import pytest

from triwitness.core.errors import SandboxError
from triwitness.sandbox.local import find_shell

GIT = "C:/Program Files/Git"


def fs(*files: str):  # type: ignore[no-untyped-def]
    norm = {f.replace("\\", "/") for f in files}
    return lambda p: p.replace("\\", "/") in norm


def which(**m: str):  # type: ignore[no-untyped-def]
    return lambda name: m.get(name)


ENV = {"ProgramFiles": "C:/Program Files", "LOCALAPPDATA": "C:/Users/Eva/AppData/Local"}


def test_setting_wins() -> None:
    c = find_shell(windows=True, setting="D:/tools/bash.exe", exists=fs("D:/tools/bash.exe"), which=which(),
                   git_exec_path=lambda: None, environ=ENV)  # fmt: skip
    assert c.kind == "bash" and c.exe == "D:/tools/bash.exe"


def test_git_exec_path() -> None:
    c = find_shell(windows=True, exists=fs("E:/Git/bin/bash.exe"), which=which(),
                   git_exec_path=lambda: r"E:\Git\mingw64\libexec\git-core", environ=ENV)  # fmt: skip
    assert c.kind == "bash" and c.exe.replace("\\", "/") == "E:/Git/bin/bash.exe"
    assert c.argv("ls") == [c.exe, "-c", "ls"]


def test_program_files_and_user_install() -> None:
    c = find_shell(windows=True, exists=fs(f"{GIT}/bin/bash.exe"), which=which(), git_exec_path=lambda: None,
                   environ=ENV)  # fmt: skip
    assert c.exe.replace("\\", "/") == f"{GIT}/bin/bash.exe"
    c2 = find_shell(windows=True, exists=fs("C:/Users/Eva/AppData/Local/Programs/Git/bin/bash.exe"), which=which(),
                    git_exec_path=lambda: None, environ=ENV)  # fmt: skip
    assert c2.kind == "bash"


def test_never_wsl_launcher() -> None:
    c = find_shell(windows=True, setting=r"C:\Windows\System32\bash.exe", exists=lambda p: True,
                   which=which(pwsh="C:/pwsh.exe"), git_exec_path=lambda: None, environ={})  # fmt: skip
    assert c.kind == "powershell"


def test_powershell_fallback_order() -> None:
    c = find_shell(windows=True, exists=fs(), which=which(pwsh="C:/pwsh.exe", powershell="C:/ps51.exe"),
                   git_exec_path=lambda: None, environ=ENV)  # fmt: skip
    assert (c.kind, c.exe) == ("powershell", "C:/pwsh.exe")
    assert c.argv("Get-ChildItem")[1:4] == ["-NoProfile", "-NonInteractive", "-Command"]
    c2 = find_shell(windows=True, exists=fs(), which=which(powershell="C:/ps51.exe"), git_exec_path=lambda: None,
                    environ=ENV)  # fmt: skip
    assert c2.exe == "C:/ps51.exe"
    with pytest.raises(SandboxError):
        find_shell(windows=True, exists=fs(), which=which(cmd="C:/cmd.exe"), git_exec_path=lambda: None, environ=ENV)


def test_posix() -> None:
    assert find_shell(windows=False, which=which(bash="/bin/bash")).exe == "/bin/bash"
    assert find_shell(windows=False, which=which(sh="/bin/sh")).exe == "/bin/sh"


# 真实 Windows 上的 Job Object / Git Bash / PowerShell 用例见 tests/unit/windows/test_windows_real.py（W2-33）


def _no_subprocess() -> str | None:
    raise AssertionError("有 PATH 上的 git 时不应该再起子进程问 git --exec-path")


@pytest.mark.parametrize(
    "git_exe",
    [f"{GIT}/cmd/git.exe", rf"{GIT}\bin\git.exe", f"{GIT}/mingw64/bin/git.exe", "D:/PortableGit/cmd/git.exe"],
)
def test_git_on_path_found_without_subprocess(git_exe: str) -> None:
    """v0.3：桌面端 / PowerShell 环境里 PATH 上是 Git\\cmd\\git.exe 启动器；直接推出 bin\\bash.exe，不起 git。"""
    root = git_exe.replace("\\", "/").rsplit("/", 3 if "/mingw64/" in git_exe else 2)[0]
    c = find_shell(windows=True, exists=fs(f"{root}/bin/bash.exe"), which=which(git=git_exe),
                   git_exec_path=_no_subprocess, environ={})  # fmt: skip
    assert c.kind == "bash" and c.exe.replace("\\", "/") == f"{root}/bin/bash.exe"


def test_program_files_checked_before_git_exec_path() -> None:
    c = find_shell(windows=True, exists=fs(f"{GIT}/bin/bash.exe"), which=which(), git_exec_path=_no_subprocess,
                   environ=ENV)  # fmt: skip
    assert c.exe.replace("\\", "/") == f"{GIT}/bin/bash.exe"


def test_run_quiet_uses_files_not_pipes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import sys
    import time

    from triwitness.sandbox.local import run_quiet

    py = sys.executable
    assert run_quiet([py, "-c", "print(' hi ')"], timeout=30) == "hi"
    assert run_quiet([py, "-c", "import sys; sys.exit(3)"], timeout=30) is None
    assert run_quiet(["definitely-not-a-command-xyz"], timeout=5) is None
    # 孙进程握着输出也不会把调用方卡住：超时就返回
    t0 = time.monotonic()
    child = "import time; time.sleep(30)"
    code = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','{child}']); time.sleep(30)"
    assert run_quiet([py, "-c", code], timeout=1) is None
    assert time.monotonic() - t0 < 15
