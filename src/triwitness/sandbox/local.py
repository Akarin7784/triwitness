"""none 后端（本机，spec 002 §5.3，W1-41）：git worktree 隔离 + 权限引擎护栏。

硬底线（任何审批模式、包括 unrestricted 都不可关闭）：
- 子进程环境只用白名单（`scrub_host_env`），密钥类变量与“值等于密钥”的变量永不下传；
- 每次 exec 一棵独立进程树，超时（及结束后残留）整树杀掉（POSIX 进程组 / Windows Job Object）。
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from triwitness.config import tw_home
from triwitness.core.errors import SandboxError
from triwitness.core.ids import new_run_id
from triwitness.sandbox.base import (
    BackendName,
    Capabilities,
    ExecResult,
    Probe,
    Sandbox,
    SandboxSpec,
    scrub_host_env,
    validate_sandbox_env,
)
from triwitness.sandbox.gitsnap import GitSnapshotter, git
from triwitness.sandbox.proc import run_tree

ShellKind = Literal["bash", "powershell"]
FinishAction = Literal["apply", "keep", "discard"]
_LIVE: dict[str, LocalSandbox] = {}


# ---------------------------------------------------------------- shell 选择


@dataclass(frozen=True)
class ShellChoice:
    kind: ShellKind
    exe: str
    reason: str

    def argv(self, cmd: str) -> list[str]:
        if self.kind == "bash":
            return [self.exe, "-c", cmd]
        return [self.exe, "-NoProfile", "-NonInteractive", "-Command", cmd]


def _is_wsl_bash(p: str) -> bool:
    low = p.replace("/", "\\").lower()
    return low.endswith("\\system32\\bash.exe") or "\\windowsapps\\" in low


def find_shell(
    *,
    windows: bool | None = None,
    setting: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    exists: Callable[[str], bool] = os.path.isfile,
    git_exec_path: Callable[[], str | None] | None = None,
    environ: dict[str, str] | None = None,
) -> ShellChoice:
    """AC15：Windows 上 bash 工具走 Git Bash；找不到时退回 PowerShell（pwsh 7 优先，5.1 兜底），不支持 cmd.exe。

    Git Bash 查找顺序：设置项 → `git --exec-path` 推出 `<git>/bin/bash.exe` → `%ProgramFiles%\\Git\\bin\\bash.exe`。
    绝不使用 `System32\\bash.exe`（那是 WSL 启动器）。
    """
    windows = sys.platform == "win32" if windows is None else windows
    env = os.environ if environ is None else environ
    if not windows:
        for name in ("bash", "sh"):
            p = which(name)
            if p:
                return ShellChoice("bash", p, name)
        raise SandboxError("找不到 bash 或 sh")
    cands: list[tuple[str, str]] = []
    if setting:
        cands.append((setting, "设置项"))
    gx = (git_exec_path or _git_exec_path)()
    if gx:
        # <git>/mingw64/libexec/git-core → <git>
        root = Path(gx.replace("\\", "/")).parents[2]
        cands.append((str(root / "bin" / "bash.exe"), "git --exec-path"))
    for var in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA"):
        base = env.get(var) or env.get(var.upper())
        if base:
            sub = "Programs/Git" if var == "LOCALAPPDATA" else "Git"
            cands.append((str(Path(base) / sub / "bin" / "bash.exe"), f"%{var}%"))
    for p, why in cands:
        if not _is_wsl_bash(p) and exists(p):
            return ShellChoice("bash", p, f"Git Bash（{why}）")
    for name in ("pwsh", "powershell"):
        p = which(name)
        if p:
            return ShellChoice("powershell", p, f"未找到 Git Bash，改用 {name}")
    raise SandboxError("找不到 Git Bash 或 PowerShell")


def _git_exec_path() -> str | None:
    try:
        r = subprocess.run(["git", "--exec-path"], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() or None


# ---------------------------------------------------------------- 会话


class LocalSandbox:
    backend: BackendName = "none"

    def __init__(
        self,
        spec: SandboxSpec,
        *,
        repo: Path,
        worktree: Path,
        run_id: str,
        branch: str,
        base: str,
        tw_dir: Path,
        shell: ShellChoice,
        home: Path,
    ) -> None:
        self.spec = spec
        self.repo = repo
        self.worktree = worktree
        self.run_id = run_id
        self.id = run_id
        self.branch = branch
        self.base = base
        self.tw_dir = tw_dir
        self.shell = shell
        self.home = home
        self.snap = GitSnapshotter(worktree, run_id, base=base)
        self._closed = False

    # ------------------------------------------------------------ 环境与路径
    def child_env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """硬底线：白名单 + 显式声明；密钥类永不下传（不受审批模式影响）。"""
        extra = dict(extra or {})
        validate_sandbox_env(extra)
        env = scrub_host_env(os.environ, extra=self.spec.env_passthrough)
        env.update(self.spec.env)
        env.update(extra)
        env["TW_WORKSPACE"] = str(self.worktree)
        env["TW_DIR"] = str(self.tw_dir)
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        return env

    def _raw_roots(self) -> list[Path]:
        return [self.worktree, self.tw_dir, *(Path(d) for d in self.spec.additional_directories)]

    def resolve_path(self, path: str) -> Path:
        """相对路径按 worktree 解析；拒绝越界（`..`）与符号链接逃逸（真实路径也必须在允许的根内）。

        受保护路径（.git/ 等）由权限引擎判定（unrestricted 可解除），这里只管越界。"""
        if "\x00" in path:
            raise SandboxError("路径含 NUL 字符")
        p = Path(path)
        if not p.is_absolute():
            p = self.worktree / p
        lexical = Path(os.path.normpath(p))
        if not any(_within(lexical, Path(os.path.normpath(r))) for r in self._raw_roots()):
            raise SandboxError(f"路径越界：{path}")
        real = lexical.resolve()
        if not any(_within(real, r.resolve()) for r in self._raw_roots()):
            raise SandboxError(f"路径经符号链接逃逸：{path} → {real}")
        return real

    # ------------------------------------------------------------ Sandbox 协议
    async def exec(
        self, cmd: str, *, timeout_s: int = 120, cwd: str | None = None, env: dict[str, str] | None = None
    ) -> ExecResult:
        if self._closed:
            raise SandboxError("沙箱已关闭")
        workdir = self.resolve_path(cwd) if cwd else self.worktree
        r = await run_tree(
            self.shell.argv(cmd),
            cwd=str(workdir),
            env=self.child_env(env),
            timeout_s=timeout_s,
            max_output_bytes=self.spec.max_output_bytes,
        )
        return ExecResult(
            exit_code=r.exit_code,
            stdout=r.stdout,
            stderr=r.stderr,
            duration_ms=r.duration_ms,
            timed_out=r.timed_out,
            truncated=r.truncated,
        )

    async def read_file(self, path: str) -> bytes:
        p = self.resolve_path(path)
        try:
            return await asyncio.to_thread(p.read_bytes)
        except FileNotFoundError as e:
            raise SandboxError(f"文件不存在：{path}") from e
        except IsADirectoryError as e:
            raise SandboxError(f"不是普通文件：{path}") from e

    async def write_file(self, path: str, data: bytes, mode: int = 0o644) -> None:
        p = self.resolve_path(path)

        def run() -> None:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            with contextlib.suppress(OSError):
                p.chmod(mode)

        await asyncio.to_thread(run)

    async def snapshot(self, label: str) -> str:
        return await self.snap.snapshot(label)

    async def restore(self, ref: str) -> None:
        await self.snap.restore(ref)

    async def diff(self, base: str = "base") -> str:
        return await self.snap.diff(base)

    async def close(self) -> None:
        """只释放会话；worktree 留给用户在 UI 里选“应用 / 保留 / 丢弃”（finish）。"""
        self._closed = True
        _LIVE.pop(self.run_id, None)

    # ------------------------------------------------------------ 结束
    async def finish(self, action: FinishAction) -> str | None:
        """apply：把 diff 应用到用户仓库工作区（不提交、不切分支），然后丢弃 worktree；
        keep：把改动提交到分支 tw/<run_id> 并移除 worktree，分支保留；discard：移除 worktree 并删分支。
        返回 apply 时应用的 diff，或 keep 时的提交 sha。"""
        result: str | None = None
        if action == "apply":
            patch = await self.diff("base")
            if patch.strip():
                await git("apply", "--whitespace=nowarn", "-", cwd=self.repo, input=patch.encode())
            result = patch
        elif action == "keep":
            await git("add", "-A", "--", ".", ":(exclude).tw", cwd=self.worktree)
            code, _, _ = await git("diff", "--cached", "--quiet", cwd=self.worktree, check=False)
            if code != 0:
                await git("commit", "-q", "--no-verify", "-m", f"tw: run {self.run_id}", cwd=self.worktree)
            _, sha, _ = await git("rev-parse", "HEAD", cwd=self.worktree)
            result = sha.decode().strip()
        await self.snap.drop_refs()
        await git("worktree", "remove", "--force", str(self.worktree), cwd=self.repo, check=False)
        await git("worktree", "prune", cwd=self.repo, check=False)
        if action != "keep":
            await git("branch", "-D", self.branch, cwd=self.repo, check=False)
        shutil.rmtree(self.worktree, ignore_errors=True)
        await self.close()
        return result


def _within(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
    except ValueError:
        return False
    return True


# ---------------------------------------------------------------- 后端


class LocalSandboxBackend:
    name: BackendName = "none"
    capabilities = Capabilities(
        isolation="none", network_enforced=False, clean_env=False, host_fs_visible=True, allows_full_access=False
    )

    def __init__(self, *, home: Path | None = None, shell: ShellChoice | None = None) -> None:
        self._home = home
        self._shell = shell

    @property
    def home(self) -> Path:
        return self._home or tw_home()

    async def probe(self) -> Probe:
        exe = shutil.which("git")
        if not exe:
            return Probe(available=False, reason="未安装 git")
        try:
            _, out, _ = await git("--version", cwd=Path.cwd(), timeout=5)
            shell = self._shell or find_shell()
        except SandboxError as e:
            return Probe(available=False, reason=str(e))
        return Probe(available=True, version=f"{out.decode().strip()}；{shell.reason}")

    async def create(self, spec: SandboxSpec) -> Sandbox:
        validate_sandbox_env(spec.env)
        if spec.repo is None:
            raise SandboxError("none 后端需要 repo（git 仓库）")
        code, top, _ = await git("rev-parse", "--show-toplevel", cwd=spec.repo, check=False)
        if code != 0:
            raise SandboxError(f"需要 git 仓库：{spec.repo}")
        repo = Path(top.decode().strip())
        run_id = spec.run_id or new_run_id()
        if not all(c.isalnum() or c in "-_." for c in run_id):
            raise SandboxError(f"run_id 含非法字符：{run_id!r}")
        _, base, _ = await git("rev-parse", "--verify", f"{spec.base_ref}^{{commit}}", cwd=repo)
        base_sha = base.decode().strip()
        wt = self.home / "worktrees" / run_id
        if wt.exists():
            raise SandboxError(f"worktree 已存在：{wt}")
        wt.parent.mkdir(parents=True, exist_ok=True)
        branch = f"tw/{run_id}"
        await git("worktree", "add", "--detach", "-q", str(wt), base_sha, cwd=repo)
        try:
            await git("switch", "-q", "-c", branch, cwd=wt)
        except SandboxError:
            await git("worktree", "remove", "--force", str(wt), cwd=repo, check=False)
            raise
        tw_dir = self.home / "runs" / run_id / ".tw"
        tw_dir.mkdir(parents=True, exist_ok=True)
        (tw_dir.parent / "owner.pid").write_text(str(os.getpid()), encoding="utf-8")
        sb = LocalSandbox(
            spec.model_copy(update={"workdir": str(wt), "run_id": run_id}),
            repo=repo,
            worktree=wt,
            run_id=run_id,
            branch=branch,
            base=base_sha,
            tw_dir=tw_dir,
            shell=self._shell or find_shell(),
            home=self.home,
        )
        _LIVE[run_id] = sb
        return sb

    async def gc(self) -> list[str]:
        """`tw sandbox gc`：清理崩溃残留的 worktree（其所属进程已不在）。返回清理的 run_id。"""
        root = self.home / "worktrees"
        cleaned: list[str] = []
        if not root.is_dir():
            return cleaned
        for wt in sorted(root.iterdir()):
            run_id = wt.name
            if run_id in _LIVE or _owner_alive(self.home / "runs" / run_id / "owner.pid"):
                continue
            gitfile = wt / ".git"
            repo: Path | None = None
            if gitfile.is_file():
                txt = gitfile.read_text(encoding="utf-8").strip()
                if txt.startswith("gitdir:"):
                    # <repo>/.git/worktrees/<name>
                    repo = Path(txt.split(":", 1)[1].strip()).parents[2]
            if repo is not None and repo.exists():
                await git("worktree", "remove", "--force", str(wt), cwd=repo, check=False)
                await git("worktree", "prune", cwd=repo, check=False)
                await git("branch", "-D", f"tw/{run_id}", cwd=repo, check=False)
                _, refs, _ = await git("for-each-ref", "--format=%(refname)", f"refs/tw/ckpt/{run_id}/", cwd=repo,
                                       check=False)  # fmt: skip
                for ref in refs.decode().split():
                    await git("update-ref", "-d", ref, cwd=repo, check=False)
            shutil.rmtree(wt, ignore_errors=True)
            cleaned.append(run_id)
        return cleaned


def _owner_alive(pidfile: Path) -> bool:
    try:
        pid = int(pidfile.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        return False  # 保守：Windows 上不探测，交给用户确认后的 gc
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
