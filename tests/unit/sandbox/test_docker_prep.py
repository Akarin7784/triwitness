"""0.5.0：docker 后端准备阶段——git archive 不走管道、拉镜像有时限、发进度。不需要真的 docker。"""

from __future__ import annotations

import io
import subprocess
import tarfile
import threading
from pathlib import Path

import pytest
from docker.errors import ImageNotFound

from triwitness.core.errors import SandboxError
from triwitness.sandbox import docker as dk
from triwitness.sandbox.base import SANDBOX_PROGRESS


def test_repo_tar_uses_run_capture(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "a.txt").write_text("1", encoding="utf-8")
    g = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*g, "add", "-A"], check=True)
    subprocess.run([*g, "commit", "-qm", "i"], check=True)
    data = dk._repo_tar(repo, "HEAD", "workspace/repo")
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        assert "workspace/repo/a.txt" in tf.getnames()
    with pytest.raises(SandboxError, match="退出码"):
        dk._repo_tar(repo, "no-such-ref", "workspace/repo")


class SlowImages:
    def __init__(self) -> None:
        self.release = threading.Event()

    def get(self, image: str) -> None:
        raise ImageNotFound("nope")

    def pull(self, image: str) -> None:
        self.release.wait(5)


class Client:
    def __init__(self) -> None:
        self.images = SlowImages()


async def test_pull_timeout_reports_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TW_DOCKER_PULL_TIMEOUT", "1")
    seen: list[tuple[str, str]] = []
    token = SANDBOX_PROGRESS.set(lambda st, status, msg: seen.append((st, status)))
    c = Client()
    try:
        with pytest.raises(SandboxError, match="超时"):
            await dk.DockerSandboxBackend(client=c)._ensure_image(c, "python:3.12-slim")
    finally:
        SANDBOX_PROGRESS.reset(token)
        c.images.release.set()
    assert seen == [("pull_image", "running"), ("pull_image", "failed")]


def _init(repo: Path, *, commit: bool = True, files: bool = False) -> None:
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    if commit:
        g = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
        if files:
            (repo / "a.txt").write_text("1", encoding="utf-8")
            subprocess.run([*g, "add", "-A"], check=True)
        subprocess.run([*g, "commit", "-q", "--allow-empty", "-m", "i"], check=True)


def test_repo_tar_uses_archive_output_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """回归：归档由 `git archive -o` 写文件，不再依赖 stdout 句柄（Windows 上曾读到空内容）。"""
    from triwitness.sandbox import local

    calls: list[list[str]] = []
    real = local.run_capture

    def spy(argv: list[str], **kw: object) -> tuple[int | None, bytes]:
        calls.append(argv)
        return real(argv, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(local, "run_capture", spy)
    repo = tmp_path / "r"
    _init(repo)
    dk._repo_tar(repo, "HEAD", "workspace/repo")
    archive = [a for a in calls if "archive" in a]
    assert archive and "-o" in archive[0]


def test_repo_tar_empty_tree_snapshot(tmp_path: Path) -> None:
    """自动初始化的空文件夹（只有 --allow-empty 首次提交）也能打包成合法 tar。"""
    repo = tmp_path / "r"
    _init(repo)
    data = dk._repo_tar(repo, "HEAD", "workspace/repo")
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        assert tf.getnames() == []


def test_repo_tar_no_commit_clear_error(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    _init(repo, commit=False)
    with pytest.raises(SandboxError, match="还没有任何提交"):
        dk._repo_tar(repo, "HEAD", "workspace/repo")


def test_repo_tar_empty_output_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """模拟 Windows 症状：git 退出码 0 但输出为空——给出明确错误而不是 tarfile ReadError。"""
    from triwitness.sandbox import local

    real = local.run_capture

    def fake(argv: list[str], **kw: object) -> tuple[int | None, bytes]:
        if "archive" in argv:
            return 0, b""  # 不写 -o 文件
        return real(argv, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(local, "run_capture", fake)
    repo = tmp_path / "r"
    _init(repo)
    with pytest.raises(SandboxError, match="输出为空或被截断"):
        dk._repo_tar(repo, "HEAD", "workspace/repo")


def test_repo_tar_garbage_output_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """模拟截断 / CRLF 改写后的坏 tar：转成 SandboxError。"""
    from triwitness.sandbox import local

    real = local.run_capture

    def fake(argv: list[str], **kw: object) -> tuple[int | None, bytes]:
        if "archive" in argv:
            Path(argv[argv.index("-o") + 1]).write_bytes(b"x\r\n" * 400)
            return 0, b""
        return real(argv, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(local, "run_capture", fake)
    repo = tmp_path / "r"
    _init(repo, files=True)
    with pytest.raises(SandboxError, match="不是有效的 tar"):
        dk._repo_tar(repo, "HEAD", "workspace/repo")
