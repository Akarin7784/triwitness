"""UI-19：沙箱环境检测与安装计划，全部离线（注入 which / run）。"""

from __future__ import annotations

import pytest

from triwitness.sandbox.doctor import decode, detect, elevated, install_plan, run_install


def fake(rcs: dict[str, tuple[int, bytes]]):  # type: ignore[no-untyped-def]
    calls: list[list[str]] = []

    def run(cmd: list[str], timeout: float) -> tuple[int, bytes]:
        calls.append(cmd)
        return rcs.get(cmd[0], (1, b""))

    return run, calls


def test_linux_docker_running() -> None:
    run, calls = fake({"docker": (0, b"27.3.1\n")})
    r = detect(platform="linux", which=lambda n: "/usr/bin/" + n, run=run)
    assert r.docker.state == "ok" and r.docker.version == "27.3.1" and r.sandbox_ready
    assert r.wsl.state == "n/a" and r.recommended == []
    assert calls == [["docker", "info", "--format", "{{.ServerVersion}}"]]


def test_docker_installed_but_stopped() -> None:
    run, _ = fake({"docker": (1, b"Cannot connect to the Docker daemon")})
    r = detect(platform="linux", which=lambda n: n, run=run)
    assert r.docker.state == "stopped" and not r.sandbox_ready and r.recommended == []


def test_windows_nothing_installed() -> None:
    run, calls = fake({})
    r = detect(platform="win32", which=lambda n: "C:/winget.exe" if n == "winget" else None, run=run)
    assert (r.docker.state, r.wsl.state, r.winget.state) == ("missing", "missing", "ok")
    assert r.recommended == ["wsl", "docker"] and calls == []


def test_windows_wsl_utf16_status() -> None:
    out = "默认版本: 2\r\n".encode("utf-16-le")
    run, _ = fake({"wsl": (0, out)})
    r = detect(platform="win32", which=lambda n: None if n == "docker" else n, run=run)
    assert r.wsl.state == "ok" and r.wsl.version == "2" and r.recommended == ["docker"]


def test_wsl_not_enabled() -> None:
    run, _ = fake({"wsl": (50, "请启用".encode("utf-16-le"))})
    r = detect(platform="win32", which=lambda n: n, run=run)
    assert r.wsl.state == "missing" and "wsl" in r.recommended


def test_decode_variants() -> None:
    assert decode("中文".encode("gb18030")) == "中文"
    assert decode(b"\xff\xfe" + "ok".encode("utf-16-le")) == "ok"


def test_plans() -> None:
    d = install_plan("docker", platform="win32")
    assert d.supported and d.needs_elevation and d.display.startswith("winget install -e --id Docker.DockerDesktop")
    assert d.command[0] == "powershell" and "-Verb RunAs" in d.command[-1] and d.fallback_urls
    w = install_plan("wsl", platform="win32")
    assert w.display == "wsl --install --no-distribution" and w.reboot_hint
    assert not install_plan("docker", platform="linux").supported
    assert not install_plan("wsl", platform="darwin").supported
    r = detect(platform="win32", which=lambda n: None, run=fake({})[0])
    assert not install_plan("docker", platform="win32", report=r).supported  # 没有 winget


def test_elevated_quotes() -> None:
    cmd = elevated(["winget", "install", "--id", "a'b"])
    assert "'install --id a''b'" in cmd[-1]


def test_run_install_requires_supported_plan() -> None:
    with pytest.raises(ValueError):
        run_install(install_plan("docker", platform="linux"))
    run, calls = fake({"powershell": (0, b"done")})
    assert run_install(install_plan("wsl", platform="win32"), run=run) == (0, "done")
    assert calls[0][0] == "powershell"
