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
