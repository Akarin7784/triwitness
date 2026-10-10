"""docker 后端的纯逻辑部分（不需要 Docker）。"""

from __future__ import annotations

import io
import tarfile

from docker.errors import DockerException

from triwitness.sandbox.base import SandboxBackend
from triwitness.sandbox.docker import DockerSandboxBackend, _Collector, _tar_bytes


def test_collector_small_passthrough() -> None:
    c = _Collector(100)
    c.add(b"hello ")
    c.add(b"world")
    assert c.result() == ("hello world", False)


def test_collector_keeps_head_and_tail() -> None:
    c = _Collector(100)
    for i in range(1000):
        c.add(f"{i:05d}\n".encode())
    out, truncated = c.result()
    assert truncated
    assert out.startswith("00000\n")
    assert out.rstrip().endswith("00999")
    assert "省略" in out
    assert len(out.encode()) <= 100 + 60


def test_tar_bytes_uid() -> None:
    data = _tar_bytes([("d", None, 0o755), ("d/f.txt", b"abc", 0o600)])
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        members = {m.name: m for m in tf.getmembers()}
    assert members["d"].isdir()
    assert members["d/f.txt"].uid == 1000
    assert members["d/f.txt"].mode == 0o600


class _BrokenClient:
    def ping(self) -> None:
        raise DockerException(
            "Error while fetching server API version: ('Connection aborted.', PermissionError(13, 'Permission denied'))"
        )


class _MissingClient:
    def ping(self) -> None:
        raise DockerException("Error while fetching server API version: FileNotFoundError")


async def test_probe_reports_reason() -> None:
    b = DockerSandboxBackend(client=_BrokenClient())
    assert isinstance(b, SandboxBackend)
    p = await b.probe()
    assert not p.available and p.reason and "docker 组" in p.reason
    p2 = await DockerSandboxBackend(client=_MissingClient()).probe()
    assert not p2.available and p2.fixable_by_installer
