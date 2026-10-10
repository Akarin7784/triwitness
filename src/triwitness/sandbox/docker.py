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
import shutil
import subprocess
import tarfile
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import docker
from docker.errors import DockerException, ImageNotFound, NotFound

from triwitness.config import tw_home
from triwitness.core.errors import SandboxError
from triwitness.sandbox.base import (
    BackendName,
    Capabilities,
    ExecResult,
    OutputCollector,
    Probe,
    Sandbox,
    SandboxSpec,
    check_sandbox_path,
    validate_sandbox_env,
)
from triwitness.sandbox.gitsnap import GitSnapshotter, git

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
            out, err = OutputCollector(self.spec.max_output_bytes), OutputCollector(self.spec.max_output_bytes)
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

    # ------------------------------------------------------------ 快照（W1-17）
    # 容器镜像里不一定有 git：在宿主上维护一个“镜像目录”（GIT_DIR 在外），快照前把容器 workdir 同步过来，
    # 用与 none 后端相同的 GitSnapshotter；restore 后再把镜像目录推回容器。
    async def init_mirror(self, home: Path) -> None:
        self.mirror_root = home / "runs" / f"docker-{self.id}"
        self.mirror = self.mirror_root / "tree"
        self.mirror_git = self.mirror_root / "tree.git"
        shutil.rmtree(self.mirror_root, ignore_errors=True)
        self.mirror.mkdir(parents=True)
        env = {"GIT_DIR": str(self.mirror_git), "GIT_WORK_TREE": str(self.mirror)}
        await git("init", "-q", "--bare", str(self.mirror_git), cwd=self.mirror_root)
        await git("config", "core.bare", "false", cwd=self.mirror, env=env)
        await self._pull()
        await git("add", "-A", cwd=self.mirror, env=env)
        await git("commit", "-q", "--allow-empty", "--no-verify", "-m", "tw base", cwd=self.mirror, env=env)
        _, sha, _ = await git("rev-parse", "HEAD", cwd=self.mirror, env=env)
        self.snap = GitSnapshotter(self.mirror, self.id, base=sha.decode().strip(), env=env)

    async def _pull(self) -> None:
        """容器 workdir → 镜像目录（整目录替换；跳过 .git / .tw；tarfile data 过滤器防逃逸）。"""
        wd = self.spec.workdir.rstrip("/")

        def run() -> None:
            stream, _ = self.container.get_archive(wd)
            data = b"".join(stream)
            for child in self.mirror.iterdir():
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                for m in tf.getmembers():
                    parts = [x for x in m.name.split("/") if x not in ("", ".")][1:]
                    if not parts or parts[0] in (".git", ".tw"):
                        continue
                    m.name = "/".join(parts)
                    try:
                        tf.extract(m, self.mirror, filter="data")
                    except tarfile.FilterError as e:
                        raise SandboxError(f"同步工作区失败（不安全的条目 {m.name}）：{e}") from e

        await asyncio.to_thread(run)

    async def _push(self) -> None:
        """镜像目录 → 容器 workdir（先清空 workdir，再以 uid 1000 放回）。"""
        wd = self.spec.workdir.rstrip("/")
        code, out = await self._raw(["find", wd, "-mindepth", "1", "-delete"])
        if code != 0:
            raise SandboxError(f"清空工作区失败：{out.decode(errors='replace')[:300]}")

        def owned(ti: tarfile.TarInfo) -> tarfile.TarInfo:
            ti.uid = ti.gid = SANDBOX_UID
            ti.uname = ti.gname = "tw"
            return ti

        def run() -> None:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tf:
                tf.add(self.mirror, arcname=posixpath.basename(wd), filter=owned)
            self.container.put_archive(posixpath.dirname(wd) or "/", buf.getvalue())

        await asyncio.to_thread(run)

    def _snap(self) -> GitSnapshotter:
        snap = getattr(self, "snap", None)
        if snap is None:
            raise SandboxError("快照未初始化")
        return snap

    async def snapshot(self, label: str) -> str:
        snap = self._snap()
        await self._pull()
        return await snap.snapshot(label)

    async def restore(self, ref: str) -> None:
        snap = self._snap()
        await self._pull()
        await snap.restore(ref)
        await self._push()

    async def diff(self, base: str = "base") -> str:
        snap = self._snap()
        await self._pull()
        return await snap.diff(base)

    async def apply_patch(self, patch: str) -> None:
        """在宿主镜像目录上 `git apply`，再推回容器（Grader 用：镜像里不需要 git）。"""
        self._snap()
        if not patch.strip():
            return
        await self._pull()
        env = {"GIT_DIR": str(self.mirror_git), "GIT_WORK_TREE": str(self.mirror)}
        data = patch.encode("utf-8") if patch.endswith("\n") else (patch + "\n").encode("utf-8")
        await git("apply", "--whitespace=nowarn", "-", cwd=self.mirror, env=env, input=data)
        await self._push()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        _LIVE.pop(self.container.id, None)
        with contextlib.suppress(NotFound):
            await asyncio.to_thread(self.container.remove, force=True)
        root = getattr(self, "mirror_root", None)
        if root is not None:
            shutil.rmtree(root, ignore_errors=True)


class DockerSandboxBackend:
    name: BackendName = "docker"
    capabilities = Capabilities(
        isolation="container", network_enforced=True, clean_env=True, host_fs_visible=False, allows_full_access=True
    )

    def __init__(self, client: Any | None = None, *, home: Path | None = None) -> None:
        self._client = client
        self._home = home

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
        try:
            await sb.init_mirror(self._home or tw_home())
        except Exception:
            await sb.close()
            raise
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
