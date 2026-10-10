"""docker 沙箱后端（spec 002 §5.2，W1-16）。

- 容器：`sleep infinity` 常驻；默认断网、非 root（1000:1000）、cap_drop ALL、no-new-privileges、pids/cpu/内存限制；
- 仓库：`git archive <base_ref>` 打包后以 uid 1000 放进 /workspace/repo（宿主仓库不被改动）；
- exec：每条命令在独立会话（setsid）里跑，看门狗超时后 `kill -KILL -<pgid>` 杀整棵进程树（硬底线）；
- 输出流式读取，只保留头尾，超过上限截断；
- snapshot / restore / diff 留给 W1-17。
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import io
import posixpath
import subprocess
import tarfile
import time
import uuid
from collections import deque
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import docker
from docker.errors import DockerException, ImageNotFound, NotFound

from triwitness.core.errors import SandboxError
from triwitness.sandbox.base import (
    BackendName,
    Capabilities,
    ExecResult,
    Probe,
    Sandbox,
    SandboxSpec,
    check_sandbox_path,
    truncate_output,
    validate_sandbox_env,
)

DEFAULT_IMAGE = "python:3.12-slim"
LABEL = "tw.managed"
SANDBOX_UID = 1000
PIDS_LIMIT = 512
_LIVE: dict[str, DockerSandbox] = {}


def _client() -> Any:
    return docker.from_env(timeout=30)


def _tar_bytes(entries: Sequence[tuple[str, bytes | None, int]], *, uid: int = SANDBOX_UID) -> bytes:
    """entries: (路径, 内容 / None 表示目录, mode)。"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, data, mode in entries:
            ti = tarfile.TarInfo(name)
            ti.uid = ti.gid = uid
            ti.uname = ti.gname = "tw"
            ti.mtime = int(time.time())
            ti.mode = mode
            if data is None:
                ti.type = tarfile.DIRTYPE
                tf.addfile(ti)
            else:
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def _repo_tar(repo: Path, base_ref: str, prefix: str) -> bytes:
    """`git archive` → 重写成 uid 1000、带前缀目录的 tar。"""
    try:
        raw = subprocess.run(
            ["git", "-C", str(repo), "archive", "--format=tar", base_ref],
            capture_output=True,
            check=True,
            timeout=300,
        ).stdout
    except (OSError, subprocess.SubprocessError) as e:
        raise SandboxError(f"打包仓库失败（git archive {base_ref}）：{e}") from e
    out = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(raw)) as src, tarfile.open(fileobj=out, mode="w") as dst:
        for m in src.getmembers():
            if m.name in ("pax_global_header",) or m.type == tarfile.XGLTYPE:
                continue
            m.name = posixpath.join(prefix, m.name)
            m.uid = m.gid = SANDBOX_UID
            m.uname = m.gname = "tw"
            dst.addfile(m, src.extractfile(m) if m.isfile() else None)
    return out.getvalue()


class _Collector:
    """流式收集输出：保留头部 max/2 与尾部 max/2 字节。"""

    def __init__(self, max_bytes: int) -> None:
        self.half = max_bytes // 2
        self.head = bytearray()
        self.tail: deque[bytes] = deque()
        self.tail_len = 0
        self.total = 0

    def add(self, chunk: bytes) -> None:
        self.total += len(chunk)
        room = self.half - len(self.head)
        if room > 0:
            self.head += chunk[:room]
            chunk = chunk[room:]
        if chunk:
            self.tail.append(chunk)
            self.tail_len += len(chunk)
            while self.tail and self.tail_len - len(self.tail[0]) >= self.half:
                self.tail_len -= len(self.tail.popleft())

    def result(self) -> tuple[str, bool]:
        tail = b"".join(self.tail)
        if self.total <= 2 * self.half:
            return truncate_output(bytes(self.head) + tail, 2 * self.half)
        tail = tail[-self.half :]
        omitted = self.total - len(self.head) - len(tail)
        head_s = bytes(self.head).decode("utf-8", "ignore")
        tail_s = tail.decode("utf-8", "ignore")
        return f"{head_s}\n...[省略 {omitted} 字节]...\n{tail_s}", True


class DockerSandbox:
    backend: BackendName = "docker"

    def __init__(self, client: Any, container: Any, spec: SandboxSpec) -> None:
        self.client = client
        self.container = container
        self.spec = spec
        self.id = container.id[:12]
        self._closed = False

    # ------------------------------------------------------------ exec
    async def exec(
        self, cmd: str, *, timeout_s: int = 120, cwd: str | None = None, env: dict[str, str] | None = None
    ) -> ExecResult:
        env = dict(env or {})
        validate_sandbox_env(env)
        workdir = check_sandbox_path(cwd, workdir=self.spec.workdir) if cwd else self.spec.workdir
        tag = uuid.uuid4().hex[:10]
        marker = f"/tmp/.tw-timeout-{tag}"
        # 命令放在环境变量里，避免二次转义；看门狗也放进独立进程组，结束时一并清掉
        wrapper = (
            'setsid bash -c "$TW_CMD" </dev/null & p=$!; '
            f'setsid bash -c "sleep {int(timeout_s)}; touch {marker}; kill -KILL -- -$p 2>/dev/null" '
            ">/dev/null 2>&1 </dev/null & w=$!; "
            "wait $p; rc=$?; kill -KILL -- -$w 2>/dev/null; "
            f"if [ -e {marker} ]; then rm -f {marker}; exit 124; fi; exit $rc"
        )
        full_env = {**self.spec.env, **env, "TW_CMD": cmd}
        api = self.client.api
        started = time.monotonic()

        def run() -> tuple[str, bool, str, bool, int, bool]:
            ex = api.exec_create(
                self.container.id,
                ["bash", "-c", wrapper],
                user=self.spec.user,
                workdir=workdir,
                environment=full_env,
            )
            out, err = _Collector(self.spec.max_output_bytes), _Collector(self.spec.max_output_bytes)
            for o, e in api.exec_start(ex["Id"], stream=True, demux=True):
                if o:
                    out.add(o)
                if e:
                    err.add(e)
            code = api.exec_inspect(ex["Id"]).get("ExitCode")
            so, t1 = out.result()
            se, t2 = err.result()
            return so, t1, se, t2, -1 if code is None else int(code), False

        try:
            so, t1, se, t2, code, _ = await asyncio.wait_for(asyncio.to_thread(run), timeout=timeout_s + 30)
        except TimeoutError:
            # 看门狗也失灵时的兜底：杀掉容器内所有非 PID 1 进程
            await asyncio.to_thread(self._kill_all)
            return ExecResult(
                exit_code=124,
                stdout="",
                stderr="超时（兜底清理）",
                duration_ms=int((time.monotonic() - started) * 1000),
                timed_out=True,
            )
        except DockerException as e:
            raise SandboxError(f"docker exec 失败：{e}") from e
        timed_out = code == 124 and (time.monotonic() - started) >= timeout_s - 0.5
        if timed_out:
            se = (se + f"\n[超时 {timeout_s}s，已杀掉整个进程组]").strip()
        return ExecResult(
            exit_code=code,
            stdout=so,
            stderr=se,
            duration_ms=int((time.monotonic() - started) * 1000),
            timed_out=timed_out,
            truncated=t1 or t2,
        )

    def _kill_all(self) -> None:
        with contextlib.suppress(DockerException):
            self.container.exec_run(["sh", "-c", "kill -KILL -1"], user="root")

    async def _raw(self, argv: list[str], *, user: str | None = None) -> tuple[int, bytes]:
        def run() -> tuple[int, bytes]:
            r = self.container.exec_run(argv, user=user or self.spec.user)
            return int(r.exit_code or 0), r.output or b""

        return await asyncio.to_thread(run)

    async def _resolve(self, path: str) -> str:
        code, out = await self._raw(["readlink", "-m", "--", path])
        if code != 0:
            raise SandboxError(f"无法解析路径：{path}")
        return out.decode().strip()

    async def _checked(self, path: str) -> str:
        absp = check_sandbox_path(path, workdir=self.spec.workdir)
        real = await self._resolve(absp)
        try:
            return check_sandbox_path(real, workdir=self.spec.workdir)
        except SandboxError as e:
            raise SandboxError(f"路径经符号链接逃逸：{path} → {real}") from e

    # ------------------------------------------------------------ 文件
    async def read_file(self, path: str) -> bytes:
        real = await self._checked(path)

        def run() -> bytes:
            try:
                stream, _ = self.container.get_archive(real)
            except NotFound as e:
                raise SandboxError(f"文件不存在：{path}") from e
            with tarfile.open(fileobj=io.BytesIO(b"".join(stream))) as tf:
                m = tf.next()
                if m is None or not m.isfile():
                    raise SandboxError(f"不是普通文件：{path}")
                f = tf.extractfile(m)
                assert f is not None
                return f.read()

        return await asyncio.to_thread(run)

    async def write_file(self, path: str, data: bytes, mode: int = 0o644) -> None:
        real = await self._checked(path)
        parent, name = posixpath.split(real)
        code, out = await self._raw(["mkdir", "-p", "--", parent])
        if code != 0:
            raise SandboxError(f"创建目录失败：{out.decode(errors='replace')}")
        payload = _tar_bytes([(name, data, mode)])
        ok = await asyncio.to_thread(self.container.put_archive, parent, payload)
        if not ok:
            raise SandboxError(f"写入失败：{path}")

    # ------------------------------------------------------------ W1-17
    async def snapshot(self, label: str) -> str:
        raise NotImplementedError("snapshot 在 W1-17 实现")

    async def restore(self, ref: str) -> None:
        raise NotImplementedError("restore 在 W1-17 实现")

    async def diff(self, base: str) -> str:
        raise NotImplementedError("diff 在 W1-17 实现")

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        _LIVE.pop(self.container.id, None)
        with contextlib.suppress(NotFound):
            await asyncio.to_thread(self.container.remove, force=True)


class DockerSandboxBackend:
    name: BackendName = "docker"
    capabilities = Capabilities(
        isolation="container", network_enforced=True, clean_env=True, host_fs_visible=False, allows_full_access=True
    )

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def client(self) -> Any:
        if self._client is None:
            self._client = _client()
        return self._client

    async def probe(self) -> Probe:
        def run() -> Probe:
            try:
                c = self.client()
                c.ping()
                v = c.version().get("Version")
            except DockerException as e:
                msg = str(e)
                if "Permission denied" in msg or "PermissionError" in msg:
                    return Probe(available=False, reason="无权访问 Docker（当前用户不在 docker 组）")
                return Probe(available=False, reason="Docker 未安装或未启动", fixable_by_installer=True)
            return Probe(available=True, version=v)

        return await asyncio.to_thread(run)

    async def create(self, spec: SandboxSpec) -> Sandbox:
        validate_sandbox_env(spec.env)
        if spec.network == "allowlist":
            raise SandboxError("network=allowlist 尚未实现（W2）")
        image = spec.image or DEFAULT_IMAGE
        client = self.client()
        repo_tar = _repo_tar(spec.repo, spec.base_ref, spec.workdir.lstrip("/")) if spec.repo else None

        def run() -> DockerSandbox:
            try:
                client.images.get(image)
            except ImageNotFound:
                client.images.pull(image)
            kwargs: dict[str, Any] = {
                "command": ["sleep", "infinity"],
                "detach": True,
                "init": True,
                "labels": {LABEL: "true"},
                "network_mode": "none" if spec.network == "none" else "bridge",
                "nano_cpus": int(spec.cpus * 1e9),
                "mem_limit": f"{spec.memory_mb}m",
                "memswap_limit": f"{spec.memory_mb}m",
                "pids_limit": PIDS_LIMIT,
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges"],
                "environment": {},
                "name": f"tw-{uuid.uuid4().hex[:12]}",
            }
            if spec.disk_mb:
                kwargs["storage_opt"] = {"size": f"{spec.disk_mb}M"}
            container = client.containers.run(image, **kwargs)
            try:
                wd = spec.workdir.lstrip("/")
                parts = wd.split("/")
                dirs = [("/".join(parts[: i + 1]), None, 0o755) for i in range(len(parts))]
                dirs.append(("workspace/.tw", None, 0o755))
                container.put_archive("/", _tar_bytes(dirs))
                if repo_tar:
                    container.put_archive("/", repo_tar)
            except Exception:
                container.remove(force=True)
                raise
            return DockerSandbox(client, container, spec)

        try:
            sb = await asyncio.to_thread(run)
        except DockerException as e:
            raise SandboxError(f"创建 docker 沙箱失败：{e}") from e
        _LIVE[sb.container.id] = sb
        return sb

    async def gc(self) -> int:
        """清理崩溃残留的 tw 容器（`tw sandbox gc`）。"""

        def run() -> int:
            n = 0
            for c in self.client().containers.list(all=True, filters={"label": f"{LABEL}=true"}):
                if c.id in _LIVE:
                    continue
                with contextlib.suppress(NotFound):
                    c.remove(force=True)
                    n += 1
            return n

        return await asyncio.to_thread(run)


@atexit.register
def _cleanup() -> None:  # pragma: no cover - 进程退出时
    for sb in list(_LIVE.values()):
        with contextlib.suppress(Exception):
            sb.container.remove(force=True)
    _LIVE.clear()


__all__ = ["DEFAULT_IMAGE", "DockerSandbox", "DockerSandboxBackend"]
