"""AC15：Windows 上 Git Bash 查找与 PowerShell 兜底（注入假文件系统，在 Linux 上模拟）。"""

from __future__ import annotations

import sys

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


@pytest.mark.skipif(sys.platform != "win32", reason="Job Object 只在 Windows 上测（W2-33 Windows CI）")
async def test_windows_job_object_kills_tree(tmp_path) -> None:  # type: ignore[no-untyped-def]  # pragma: no cover
    from triwitness.sandbox.proc import run_tree

    r = await run_tree(
        ["powershell", "-NoProfile", "-Command",
         "Start-Process -NoNewWindow ping -ArgumentList '-n','300','127.0.0.1'; Start-Sleep 300"],
        cwd=str(tmp_path), env=dict(__import__("os").environ), timeout_s=2, max_output_bytes=10000,
    )  # fmt: skip
    assert r.timed_out
