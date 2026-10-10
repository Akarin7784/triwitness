"""docker 后端集成测试（spec 002 AC1–AC4、AC7–AC9、AC12）。需要 Docker；不可用时跳过。

本地：`sg docker -c "uv run pytest -m integration tests/integration/sandbox"`
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from triwitness.core.errors import SandboxError
from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.docker import LABEL, DockerSandbox, DockerSandboxBackend

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def backend(tmp_path_factory: pytest.TempPathFactory) -> DockerSandboxBackend:
    b = DockerSandboxBackend(home=tmp_path_factory.mktemp("twhome"))
    probe = asyncio.run(b.probe())
    if not probe.available:
        pytest.skip(f"Docker 不可用：{probe.reason}")
    return b


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()

    def git(*a: str) -> None:
        subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    (r / "hello.py").write_text("print('hi')\n")
    (r / "sub").mkdir()
    (r / "sub" / "data.txt").write_text("data\n")
    git("add", "-A")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    return r


async def make(backend: DockerSandboxBackend, repo: Path | None = None, **kw: object) -> DockerSandbox:
    sb = await backend.create(SandboxSpec(repo=repo, memory_mb=512, cpus=1, **kw))  # type: ignore[arg-type]
    assert isinstance(sb, DockerSandbox)
    return sb


async def test_repo_copied_and_non_root(backend: DockerSandboxBackend, repo: Path) -> None:
    sb = await make(backend, repo)
    try:
        r = await sb.exec("id -u && cat hello.py && ls sub && touch new.txt && echo ok")
        assert r.exit_code == 0, r.stderr
        lines = r.stdout.split()
        assert lines[0] != "0"  # AC8
        assert "print('hi')" in r.stdout and "data.txt" in r.stdout and lines[-1] == "ok"
        assert not (repo / "new.txt").exists()  # 宿主仓库不变
    finally:
        await sb.close()


async def test_ac1_network_none(backend: DockerSandboxBackend) -> None:
    sb = await make(backend)
    try:
        r = await sb.exec(
            "python -c \"import urllib.request; urllib.request.urlopen('https://example.com', timeout=5)\"",
            timeout_s=30,
        )
        assert r.exit_code != 0
        r2 = await sb.exec("pip download --no-cache-dir -q -d /tmp/x requests", timeout_s=60)
        assert r2.exit_code != 0
    finally:
        await sb.close()


async def test_ac2_ac12_timeout_kills_tree(backend: DockerSandboxBackend) -> None:
    sb = await make(backend)
    try:
        t0 = asyncio.get_running_loop().time()
        r = await sb.exec("(sleep 100 &) ; bash -c 'sleep 100 & sleep 100'", timeout_s=1)
        assert asyncio.get_running_loop().time() - t0 < 5
        assert r.timed_out and r.exit_code == 124
        await asyncio.sleep(0.5)
        ps = await sb.exec("ps -eo pid,args 2>/dev/null || ls /proc | grep -c '^[0-9]'")
        assert "sleep 100" not in ps.stdout
        ok = await sb.exec("echo still-alive")
        assert ok.stdout.strip() == "still-alive"
        assert not ok.timed_out
    finally:
        await sb.close()


async def test_ac3_truncation(backend: DockerSandboxBackend) -> None:
    sb = await make(backend, max_output_bytes=10_000)
    try:
        r = await sb.exec("head -c 1048576 /dev/zero | tr '\\0' 'x'; echo END")
        assert r.truncated
        assert len(r.stdout.encode()) <= 10_000 + 100
        assert r.stdout.rstrip().endswith("END")
    finally:
        await sb.close()


async def test_ac4_path_escape(backend: DockerSandboxBackend, repo: Path) -> None:
    sb = await make(backend, repo)
    try:
        assert await sb.read_file("hello.py") == b"print('hi')\n"
        await sb.write_file("sub/new/out.txt", b"abc")
        assert await sb.read_file("/workspace/repo/sub/new/out.txt") == b"abc"
        with pytest.raises(SandboxError):
            await sb.read_file("../../etc/passwd")
        await sb.exec("ln -s /etc/passwd evil")
        with pytest.raises(SandboxError, match="符号链接"):
            await sb.read_file("evil")
        with pytest.raises(SandboxError):
            await sb.write_file("evil", b"x")
    finally:
        await sb.close()


async def test_ac7_env_placeholders(backend: DockerSandboxBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-fake-host-value-0000000000")  # 宿主有密钥也不会进容器
    with pytest.raises(SandboxError):
        await make(backend, env={"GITHUB_TOKEN": "ghp_xxx"})
    sb = await make(backend, env={"GITHUB_TOKEN": "tw-placeholder-1"})
    try:
        r = await sb.exec("echo $GITHUB_TOKEN; env | grep -c '^DEEPSEEK' || true")
        assert r.stdout.split()[0] == "tw-placeholder-1"
        assert r.stdout.split()[1] == "0"
        with pytest.raises(SandboxError):
            await sb.exec("true", env={"API_KEY": "real"})
    finally:
        await sb.close()


async def test_ac9_concurrent_and_cleanup(backend: DockerSandboxBackend) -> None:
    sbs = await asyncio.gather(*[make(backend) for _ in range(8)])
    try:
        rs = await asyncio.gather(*[s.exec("python --version") for s in sbs])
        assert all(r.exit_code == 0 and "Python 3.12" in (r.stdout + r.stderr) for r in rs)
    finally:
        await asyncio.gather(*[s.close() for s in sbs])
    ids = {s.container.id for s in sbs}
    left = backend.client().containers.list(all=True, filters={"label": f"{LABEL}=true"})
    assert not ids & {c.id for c in left}


async def test_gc_removes_orphans(backend: DockerSandboxBackend) -> None:
    orphan = backend.client().containers.run(
        "python:3.12-slim", ["sleep", "infinity"], detach=True, labels={LABEL: "true"}, network_mode="none"
    )
    assert await backend.gc() >= 1
    assert orphan.id not in {c.id for c in backend.client().containers.list(all=True)}


async def test_ac5_ac6_snapshot_restore_diff(backend: DockerSandboxBackend, repo: Path) -> None:
    sb = await make(backend, repo)
    try:
        await sb.write_file("hello.py", b"print('s1')\n")
        await sb.write_file("added.txt", b"new\n")
        assert await sb.snapshot("s1") == f"refs/tw/ckpt/{sb.id}/s1"
        await sb.write_file("hello.py", b"print('after')\n")
        await sb.exec("echo later > later.txt && rm added.txt && mkdir -p .tw && echo n > .tw/NOTES.md")
        await sb.restore("s1")
        assert await sb.read_file("hello.py") == b"print('s1')\n"
        assert await sb.read_file("added.txt") == b"new\n"
        ls = await sb.exec("ls -A; id -u; stat -c %u hello.py")
        assert "later.txt" not in ls.stdout
        uid = ls.stdout.split()[-1]
        assert uid != "0"  # 推回后仍归非 root 用户所有
        w = await sb.exec("echo ok > hello.py && cat hello.py")
        assert w.stdout.strip() == "ok"
        await sb.exec("mkdir -p .tw && echo n > .tw/NOTES.md")
        d = await sb.diff()
        assert "added.txt" in d and "hello.py" in d
        assert "NOTES.md" not in d
        assert (await sb.diff("s1")).count("diff --git") == 1  # 只有 hello.py 变了
        assert repo.joinpath("hello.py").read_text() == "print('hi')\n"  # 宿主仓库不变
    finally:
        await sb.close()
