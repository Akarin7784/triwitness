"""SandboxBackend 协议、后端选择（spec 002 AC16）与纯函数。"""

from __future__ import annotations

import asyncio
from typing import cast

import pytest

from triwitness.core.errors import SandboxError
from triwitness.sandbox.base import (
    BackendName,
    Capabilities,
    Probe,
    RemoteSandboxBackend,
    Sandbox,
    SandboxBackend,
    SandboxSpec,
    check_sandbox_path,
    scrub_host_env,
    select_backend,
    truncate_output,
    validate_sandbox_env,
)

CAPS = Capabilities(isolation="container", network_enforced=True, clean_env=True, host_fs_visible=False,
                    allows_full_access=True)  # fmt: skip


class Fake:
    def __init__(self, name: str, available: bool = True, *, raises: bool = False, hang: bool = False) -> None:
        self.name: BackendName = cast(BackendName, name)
        self.capabilities = CAPS
        self._p = Probe(available=available, reason=None if available else "没装")
        self.raises = raises
        self.hang = hang
        self.probed = 0

    async def probe(self) -> Probe:
        self.probed += 1
        if self.raises:
            raise RuntimeError("boom")
        if self.hang:
            await asyncio.sleep(60)
        return self._p

    async def create(self, spec: SandboxSpec) -> Sandbox:
        raise NotImplementedError


def test_protocol_conformance() -> None:
    assert isinstance(Fake("docker"), SandboxBackend)
    assert isinstance(RemoteSandboxBackend(), SandboxBackend)


async def test_auto_prefers_docker() -> None:
    c = await select_backend("auto", [Fake("none"), Fake("wsl2"), Fake("docker")])
    assert c.backend.name == "docker"


async def test_auto_falls_back_in_order() -> None:
    c = await select_backend("auto", [Fake("docker", False), Fake("wsl2", raises=True), Fake("none")])
    assert c.backend.name == "none"
    assert "docker" in c.reason and "wsl2" in c.reason
    assert c.probes["wsl2"].reason and "RuntimeError" in c.probes["wsl2"].reason


async def test_probe_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    real_wait_for = asyncio.wait_for

    async def fast(aw, timeout):  # type: ignore[no-untyped-def]
        return await real_wait_for(aw, 0.01)

    monkeypatch.setattr(asyncio, "wait_for", fast)
    c = await select_backend("auto", [Fake("docker", hang=True), Fake("none")])
    assert c.backend.name == "none"
    assert c.probes["docker"].reason == "探测超时"


async def test_explicit_unavailable_raises() -> None:
    with pytest.raises(SandboxError):
        await select_backend("docker", [Fake("docker", False), Fake("none")])
    c = await select_backend("wsl2", [Fake("docker"), Fake("wsl2")])
    assert c.backend.name == "wsl2"


async def test_ac16_eval_never_falls_back() -> None:
    none = Fake("none")
    with pytest.raises(SandboxError, match="不会回退"):
        await select_backend("auto", [Fake("docker", False), none], eval_mode=True)
    assert none.probed == 0
    with pytest.raises(SandboxError):
        await select_backend("none", [Fake("docker", False), none], eval_mode=True)
    c = await select_backend("none", [Fake("docker"), none], eval_mode=True)
    assert c.backend.name == "docker"


async def test_nothing_available() -> None:
    with pytest.raises(SandboxError):
        await select_backend("auto", [Fake("docker", False)])


async def test_remote_stub() -> None:
    r = RemoteSandboxBackend()
    assert not (await r.probe()).available
    with pytest.raises(NotImplementedError):
        await r.create(SandboxSpec())


def test_truncate_output() -> None:
    assert truncate_output("short", 100) == ("short", False)
    out, t = truncate_output("A" * 500 + "B" * 500, 100)
    assert t
    assert out.startswith("A" * 50) and out.endswith("B" * 50)
    assert "省略 900 字节" in out
    out2, _ = truncate_output("中" * 100, 31)  # 多字节边界不崩
    assert "省略" in out2


def test_validate_sandbox_env() -> None:
    validate_sandbox_env({"DEEPSEEK_API_KEY": "tw-placeholder-1", "FOO": "bar"})
    with pytest.raises(SandboxError, match="GITHUB_TOKEN"):
        validate_sandbox_env({"GITHUB_TOKEN": "ghp_real"})


def test_scrub_host_env_hard_floor() -> None:
    environ = {
        "PATH": "/bin",
        "Path": "C:\\Windows",
        "LC_ALL": "C",
        "DEEPSEEK_API_KEY": "sk-real",
        "GITHUB_TOKEN": "x",
        "AWS_SECRET_ACCESS_KEY": "x",
        "MY_PASSWORD": "x",
        "RANDOM": "x",
        "HTTPS_PROXY": "http://p",
    }
    out = scrub_host_env(environ, extra=["RANDOM", "GITHUB_TOKEN"])
    assert set(out) == {"PATH", "Path", "LC_ALL", "RANDOM", "HTTPS_PROXY"}  # 显式声明也带不走密钥


@pytest.mark.parametrize(
    ("path", "ok"),
    [
        ("src/a.py", True),
        ("/workspace/repo/x", True),
        ("/tmp/x", True),
        ("../etc/passwd", False),
        ("/etc/passwd", False),
        ("/workspace/repo/../other", False),
        ("a\x00b", False),
    ],
)
def test_check_sandbox_path(path: str, ok: bool) -> None:
    if ok:
        assert check_sandbox_path(path, workdir="/workspace/repo").startswith("/")
    else:
        with pytest.raises(SandboxError):
            check_sandbox_path(path, workdir="/workspace/repo")


def test_check_sandbox_path_symlink_escape() -> None:
    with pytest.raises(SandboxError, match="符号链接"):
        check_sandbox_path("link", workdir="/workspace/repo", resolve=lambda p: "/root/.ssh/id_rsa")
