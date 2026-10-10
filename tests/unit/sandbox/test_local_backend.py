"""none 后端（本机）：spec 002 AC10–AC14 + 硬底线（密钥不下传、超时杀进程树）。只需要 git，默认跑。"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

from triwitness.core.errors import SandboxError
from triwitness.sandbox.base import SandboxBackend, SandboxSpec
from triwitness.sandbox.local import LocalSandbox, LocalSandboxBackend

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX 用例；Windows 用例见 W2-33")

FAKE_KEY = "sk-fakefakefakefakefake000000"


def sh(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "user-repo"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    (r / "a.py").write_text("print('a')\n")
    (r / ".gitignore").write_text(".venv/\n")
    sh(r, "add", "-A")
    sh(r, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    (r / "dirty.txt").write_text("用户未提交的改动\n")
    return r


@pytest.fixture
def backend(tmp_path: Path) -> LocalSandboxBackend:
    return LocalSandboxBackend(home=tmp_path / "twhome")


async def make(backend: LocalSandboxBackend, repo: Path, run_id: str = "r1", **kw: object) -> LocalSandbox:
    sb = await backend.create(SandboxSpec(repo=repo, run_id=run_id, **kw))  # type: ignore[arg-type]
    assert isinstance(sb, LocalSandbox)
    return sb


async def test_probe(backend: LocalSandboxBackend) -> None:
    assert isinstance(backend, SandboxBackend)
    p = await backend.probe()
    assert p.available, p.reason


async def test_ac10_user_repo_untouched(backend: LocalSandboxBackend, repo: Path, tmp_path: Path) -> None:
    before = (sh(repo, "status", "--porcelain"), sh(repo, "branch", "--show-current"), sh(repo, "rev-parse", "HEAD"))
    sb = await make(backend, repo)
    assert sb.worktree == tmp_path / "twhome" / "worktrees" / "r1"
    assert sh(sb.worktree, "branch", "--show-current") == "tw/r1"
    assert not (sb.worktree / "dirty.txt").exists()  # 只带提交过的内容
    r = await sb.exec("echo hi > new.txt && pwd")
    assert r.exit_code == 0 and r.stdout.strip() == str(sb.worktree)
    after = (sh(repo, "status", "--porcelain"), sh(repo, "branch", "--show-current"), sh(repo, "rev-parse", "HEAD"))
    assert before == after
    assert not (repo / "new.txt").exists()
    assert sb.tw_dir == tmp_path / "twhome" / "runs" / "r1" / ".tw"
    await sb.finish("discard")


async def test_non_git_dir_rejected(backend: LocalSandboxBackend, tmp_path: Path) -> None:
    d = tmp_path / "plain"
    d.mkdir()
    with pytest.raises(SandboxError, match="git"):
        await backend.create(SandboxSpec(repo=d))


async def test_ac11_secrets_never_reach_subprocess(
    backend: LocalSandboxBackend, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_" + "x" * 36)
    monkeypatch.setenv("SNEAKY_ALIAS", FAKE_KEY)  # 改名带出
    monkeypatch.setenv("MY_TOOL_HOME", "/opt/tool")
    sb = await make(backend, repo, env_passthrough=["MY_TOOL_HOME", "GITHUB_TOKEN", "SNEAKY_ALIAS"])
    try:
        r = await sb.exec("env")
        assert r.exit_code == 0
        assert FAKE_KEY not in r.stdout
        assert "DEEPSEEK_API_KEY" not in r.stdout
        assert "GITHUB_TOKEN" not in r.stdout
        assert "MY_TOOL_HOME=/opt/tool" in r.stdout
        assert "PATH=" in r.stdout
        # 即使调用方显式传真实密钥也会被拒（只能传占位符）
        with pytest.raises(SandboxError):
            await sb.exec("true", env={"DEEPSEEK_API_KEY": FAKE_KEY})
        ok = await sb.exec("echo $DEEPSEEK_API_KEY", env={"DEEPSEEK_API_KEY": "tw-placeholder-1"})
        assert ok.stdout.strip() == "tw-placeholder-1"
    finally:
        await sb.finish("discard")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # 僵尸进程也算已死
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().split()[2] != "Z"
    except OSError:
        return False


async def test_ac12_timeout_kills_whole_tree(backend: LocalSandboxBackend, repo: Path) -> None:
    sb = await make(backend, repo)
    try:
        t0 = asyncio.get_running_loop().time()
        r = await sb.exec(
            "sleep 300 & echo $! > child.pid; bash -c 'sleep 300 & echo $! > grand.pid; wait' & wait", timeout_s=1
        )
        assert asyncio.get_running_loop().time() - t0 < 5
        assert r.timed_out and r.exit_code == 124
        await asyncio.sleep(0.3)
        for f in ("child.pid", "grand.pid"):
            pid = int((sb.worktree / f).read_text())
            assert not _alive(pid), f
    finally:
        await sb.finish("discard")


async def test_background_leftovers_killed_after_exit(backend: LocalSandboxBackend, repo: Path) -> None:
    sb = await make(backend, repo)
    try:
        r = await sb.exec("sleep 300 >/dev/null 2>&1 & echo $!")
        assert r.exit_code == 0 and not r.timed_out
        await asyncio.sleep(0.3)
        assert not _alive(int(r.stdout.strip()))
    finally:
        await sb.finish("discard")


async def test_output_truncation(backend: LocalSandboxBackend, repo: Path) -> None:
    sb = await make(backend, repo, max_output_bytes=10_000)
    try:
        r = await sb.exec("head -c 1048576 /dev/zero | tr '\\0' x; echo END")
        assert r.truncated and len(r.stdout.encode()) <= 10_100
        assert r.stdout.rstrip().endswith("END")
    finally:
        await sb.finish("discard")


async def test_path_safety(backend: LocalSandboxBackend, repo: Path, tmp_path: Path) -> None:
    sb = await make(backend, repo)
    try:
        assert await sb.read_file("a.py") == b"print('a')\n"
        await sb.write_file("sub/x.txt", b"x")
        assert (sb.worktree / "sub" / "x.txt").read_bytes() == b"x"
        await sb.write_file(str(sb.tw_dir / "NOTES.md"), b"n")
        with pytest.raises(SandboxError, match="越界"):
            await sb.read_file("../../user-repo/a.py")
        with pytest.raises(SandboxError, match="越界"):
            await sb.read_file("/etc/passwd")
        (sb.worktree / "evil").symlink_to("/etc/passwd")
        with pytest.raises(SandboxError, match="符号链接"):
            await sb.read_file("evil")
        with pytest.raises(SandboxError):
            await sb.exec("true", cwd="../..")
    finally:
        await sb.finish("discard")


# ------------------------------------------------------------------ AC13 = AC5 + AC6 on none
async def test_ac13_snapshot_restore_diff(backend: LocalSandboxBackend, repo: Path) -> None:
    sb = await make(backend, repo)
    try:
        head = sh(sb.worktree, "rev-parse", "HEAD")
        await sb.write_file("a.py", b"print('s1')\n")
        await sb.write_file("added.txt", b"new\n")
        (sb.worktree / ".venv").mkdir()
        (sb.worktree / ".venv" / "lib.py").write_text("ignored\n")
        ref = await sb.snapshot("s1")
        assert ref == "refs/tw/ckpt/r1/s1"
        await sb.write_file("a.py", b"print('after')\n")
        await sb.write_file("later.txt", b"later\n")
        (sb.worktree / "added.txt").unlink()
        await sb.restore("s1")
        assert (sb.worktree / "a.py").read_text() == "print('s1')\n"
        assert (sb.worktree / "added.txt").read_text() == "new\n"
        assert not (sb.worktree / "later.txt").exists()
        assert (sb.worktree / ".venv" / "lib.py").exists()  # 被忽略的文件不动
        assert sh(sb.worktree, "rev-parse", "HEAD") == head  # 分支不动
        assert sh(sb.worktree, "diff", "--cached", "--name-only") == ""  # 真实索引仍是 HEAD
        (sb.worktree / ".tw").mkdir()
        (sb.worktree / ".tw" / "NOTES.md").write_text("notes\n")
        d = await sb.diff()
        assert "added.txt" in d and "a.py" in d
        assert ".tw/NOTES.md" not in d and ".venv" not in d
        assert "later.txt" not in d
        d2 = await sb.diff("s1")
        assert d2.strip() == ""
        with pytest.raises(SandboxError):
            await sb.snapshot("bad label!")
        with pytest.raises(SandboxError):
            await sb.restore("nope")
    finally:
        await sb.finish("discard")


# ------------------------------------------------------------------ AC14 结束与 gc
async def test_ac14_discard_leaves_nothing(backend: LocalSandboxBackend, repo: Path) -> None:
    sb = await make(backend, repo)
    await sb.snapshot("s1")
    await sb.finish("discard")
    assert str(sb.worktree) not in sh(repo, "worktree", "list")
    assert sh(repo, "branch", "--list", "tw/r1") == ""
    assert sh(repo, "for-each-ref", "refs/tw/") == ""
    assert not sb.worktree.exists()


async def test_finish_keep_and_apply(backend: LocalSandboxBackend, repo: Path) -> None:
    sb = await make(backend, repo, run_id="k1")
    await sb.write_file("kept.txt", b"k\n")
    sha = await sb.finish("keep")
    assert sha and sh(repo, "show", "--name-only", "--format=", "tw/k1") == "kept.txt"
    assert not (repo / "kept.txt").exists()

    sb2 = await make(backend, repo, run_id="a1")
    await sb2.write_file("a.py", b"print('applied')\n")
    await sb2.write_file("brand_new.txt", b"n\n")
    patch = await sb2.finish("apply")
    assert patch and "brand_new.txt" in patch
    assert (repo / "a.py").read_text() == "print('applied')\n"
    assert (repo / "brand_new.txt").exists()
    assert (repo / "dirty.txt").exists()  # 用户原有改动保留
    assert sh(repo, "branch", "--show-current") == "main"
    assert sh(repo, "branch", "--list", "tw/a1") == ""


async def test_gc_cleans_crash_leftovers(backend: LocalSandboxBackend, repo: Path, tmp_path: Path) -> None:
    sb = await make(backend, repo, run_id="crash1")
    await sb.snapshot("s1")
    # 模拟崩溃：进程登记表里没有它，owner.pid 指向已不存在的进程
    from triwitness.sandbox import local

    local._LIVE.clear()
    (tmp_path / "twhome" / "runs" / "crash1" / "owner.pid").write_text("999999999")
    live = await make(backend, repo, run_id="live1")
    cleaned = await backend.gc()
    assert cleaned == ["crash1"]
    assert not sb.worktree.exists()
    assert sh(repo, "branch", "--list", "tw/crash1") == ""
    assert sh(repo, "for-each-ref", "refs/tw/ckpt/crash1/") == ""
    assert live.worktree.exists()
    await live.finish("discard")


async def test_concurrent_runs_isolated(backend: LocalSandboxBackend, repo: Path) -> None:
    sbs = await asyncio.gather(*[make(backend, repo, run_id=f"c{i}") for i in range(4)])
    try:
        await asyncio.gather(*[s.write_file("same.txt", s.run_id.encode()) for s in sbs])
        assert [(s.worktree / "same.txt").read_text() for s in sbs] == [s.run_id for s in sbs]
    finally:
        for s in sbs:
            await s.finish("discard")
