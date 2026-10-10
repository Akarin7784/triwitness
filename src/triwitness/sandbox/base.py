"""沙箱运行时协议（spec 002 §4，ADR-0005）。

四个后端：none（本机 + worktree + 权限引擎）、docker、wsl2（推迟）、remote（桩）。
本模块只放协议、数据模型、后端选择和不依赖任何后端的纯函数，便于离线单测。
"""

from __future__ import annotations

import asyncio
import posixpath
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from triwitness.core.errors import SandboxError

BackendName = Literal["none", "docker", "wsl2", "remote"]
BACKEND_ORDER: tuple[BackendName, ...] = ("docker", "wsl2", "none")
PLACEHOLDER_PREFIX = "tw-placeholder"
SECRET_KEY_RE = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL", re.I)

# none 后端传给子进程的宿主环境变量白名单（spec 002 §5.3-4）；大小写不敏感比较（Windows）
HOST_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        "PATH", "HOME", "USERPROFILE", "LANG", "LANGUAGE", "TEMP", "TMP", "TMPDIR", "SYSTEMROOT", "SYSTEMDRIVE",
        "WINDIR", "COMSPEC", "PATHEXT", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES",
        "PROGRAMFILES(X86)", "HOMEDRIVE", "HOMEPATH", "USERNAME", "USER", "LOGNAME", "SHELL", "TERM", "TZ",
        "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR",
        "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS",
    }
)  # fmt: skip


class Capabilities(BaseModel):
    isolation: Literal["none", "container", "vm", "remote"]
    network_enforced: bool
    clean_env: bool
    host_fs_visible: bool
    allows_full_access: bool


class ExecResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    truncated: bool = False


class SandboxSpec(BaseModel):
    image: str | None = None
    repo: Path | None = None
    base_ref: str = "HEAD"
    workdir: str = "/workspace/repo"
    cpus: float = Field(default=2.0, gt=0)
    memory_mb: int = Field(default=4096, gt=0)
    disk_mb: int | None = None
    network: Literal["none", "allowlist", "host"] = "none"
    allowlist: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    user: str = "1000:1000"
    max_output_bytes: int = Field(default=200_000, gt=0)


class Probe(BaseModel):
    available: bool
    reason: str | None = None
    version: str | None = None
    fixable_by_installer: bool = False


@runtime_checkable
class Sandbox(Protocol):
    id: str
    spec: SandboxSpec
    backend: BackendName

    async def exec(
        self, cmd: str, *, timeout_s: int = 120, cwd: str | None = None, env: dict[str, str] | None = None
    ) -> ExecResult: ...
    async def read_file(self, path: str) -> bytes: ...
    async def write_file(self, path: str, data: bytes, mode: int = 0o644) -> None: ...
    async def snapshot(self, label: str) -> str: ...
    async def restore(self, ref: str) -> None: ...
    async def diff(self, base: str) -> str: ...
    async def close(self) -> None: ...


@runtime_checkable
class SandboxBackend(Protocol):
    name: BackendName
    capabilities: Capabilities

    async def probe(self) -> Probe: ...
    async def create(self, spec: SandboxSpec) -> Sandbox: ...


# ---------------------------------------------------------------- 后端选择


@dataclass
class BackendChoice:
    backend: SandboxBackend
    reason: str
    probes: dict[str, Probe]


async def select_backend(
    pref: BackendName | Literal["auto"],
    backends: Iterable[SandboxBackend],
    *,
    eval_mode: bool = False,
) -> BackendChoice:
    """spec 002 §5.1。

    - eval：只接受 docker（或显式 wsl2），不可用则报错，绝不回退到 none；
    - 显式偏好：不可用则报错（由 UI 询问是否本次改用 none）；
    - auto：docker → wsl2 → none。
    """
    by_name: dict[str, SandboxBackend] = {b.name: b for b in backends}
    probes: dict[str, Probe] = {}

    async def _probe(name: str) -> Probe:
        b = by_name.get(name)
        if b is None:
            p = Probe(available=False, reason="未注册")
        else:
            try:
                p = await asyncio.wait_for(b.probe(), timeout=5)
            except TimeoutError:
                p = Probe(available=False, reason="探测超时")
            except Exception as e:  # probe 不允许抛错，兜底
                p = Probe(available=False, reason=f"探测失败：{type(e).__name__}")
        probes[name] = p
        return p

    if eval_mode:
        want: BackendName = "wsl2" if pref == "wsl2" else "docker"
        p = await _probe(want)
        if not p.available:
            raise SandboxError(f"评测必须使用沙箱后端 {want}，当前不可用：{p.reason}（不会回退到无沙箱）")
        return BackendChoice(backend=by_name[want], reason=f"eval 强制 {want}", probes=probes)

    if pref != "auto":
        p = await _probe(pref)
        if not p.available:
            raise SandboxError(f"沙箱后端 {pref} 不可用：{p.reason}")
        return BackendChoice(backend=by_name[pref], reason="用户指定", probes=probes)

    for name in BACKEND_ORDER:
        p = await _probe(name)
        if p.available:
            skipped = [f"{k}：{v.reason}" for k, v in probes.items() if k != name]
            reason = "auto" + (f"（跳过 {'；'.join(skipped)}）" if skipped else "")
            return BackendChoice(backend=by_name[name], reason=reason, probes=probes)
    raise SandboxError("没有可用的沙箱后端（none 后端需要 git）")


# ---------------------------------------------------------------- remote 桩


class RemoteSandboxBackend:
    """E2B 协议云沙箱（阿里云 Agent Sandbox / 火山引擎）。只留接口（spec 002 §5.5）。"""

    name: BackendName = "remote"
    capabilities = Capabilities(
        isolation="remote", network_enforced=True, clean_env=True, host_fs_visible=False, allows_full_access=True
    )

    async def probe(self) -> Probe:
        return Probe(available=False, reason="未实现")

    async def create(self, spec: SandboxSpec) -> Sandbox:
        raise NotImplementedError("remote 后端未实现（spec 002 §5.5）")


# ---------------------------------------------------------------- 纯函数


def truncate_output(data: bytes | str, max_bytes: int) -> tuple[str, bool]:
    """超过 max_bytes 时保留头尾各一半，中间插入 `...[省略 N 字节]...`（spec 002 §5.2-2）。"""
    raw = data.encode("utf-8", "replace") if isinstance(data, str) else data
    if len(raw) <= max_bytes:
        return raw.decode("utf-8", "replace"), False
    half = max_bytes // 2
    omitted = len(raw) - 2 * half
    head = raw[:half].decode("utf-8", "ignore")
    tail = raw[-half:].decode("utf-8", "ignore")
    return f"{head}\n...[省略 {omitted} 字节]...\n{tail}", True


def validate_sandbox_env(env: Mapping[str, str]) -> None:
    """键名像密钥的变量，值必须以 tw-placeholder 开头（spec 002 §5、AC7）。"""
    bad = [k for k, v in env.items() if SECRET_KEY_RE.search(k) and not v.startswith(PLACEHOLDER_PREFIX)]
    if bad:
        raise SandboxError(f"沙箱 env 中疑似真实密钥：{', '.join(sorted(bad))}（值必须以 {PLACEHOLDER_PREFIX} 开头）")


def scrub_host_env(environ: Mapping[str, str], extra: Sequence[str] = ()) -> dict[str, str]:
    """none 后端子进程环境：只留白名单 + 显式声明的变量；像密钥的键一律剔除（AC11）。"""
    allowed = {k.upper() for k in HOST_ENV_ALLOWLIST} | {k.upper() for k in extra}
    out: dict[str, str] = {}
    for k, v in environ.items():
        up = k.upper()
        if SECRET_KEY_RE.search(up):
            continue
        if up in allowed or up.startswith("LC_"):
            out[k] = v
    return out


def check_sandbox_path(
    path: str,
    *,
    workdir: str,
    extra_roots: Sequence[str] = ("/tmp", "/workspace/.tw"),
    resolve: Callable[[str], str] | None = None,
) -> str:
    """沙箱内（POSIX）路径校验：相对路径按 workdir 解析，拒绝 `..` 与符号链接逃逸（AC4）。

    resolve：把路径解析成真实路径（容器内 `readlink -f`）；为 None 时只做词法检查。
    返回规范化后的绝对路径。
    """
    if "\x00" in path:
        raise SandboxError("路径含 NUL 字符")
    absp = posixpath.normpath(path if path.startswith("/") else posixpath.join(workdir, path))
    roots = [posixpath.normpath(r) for r in (workdir, *extra_roots)]

    def inside(p: str) -> bool:
        return any(p == r or p.startswith(r.rstrip("/") + "/") for r in roots)

    if not inside(absp):
        raise SandboxError(f"路径越界：{path}（只允许 {', '.join(roots)}）")
    if resolve is not None:
        real = posixpath.normpath(resolve(absp))
        if not inside(real):
            raise SandboxError(f"路径经符号链接逃逸：{path} → {real}")
    return absp
