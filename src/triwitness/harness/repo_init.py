"""所选文件夹不是 git 仓库时自动初始化（0.5.0）。

none 后端靠 git worktree、docker 后端靠 git archive，都需要 git 仓库。桌面端允许选任意文件夹，
以前选了普通文件夹就会在建沙箱时失败（或卡住）。现在开始仓库工作前：

- 文件夹已经是仓库、或在某个仓库里面（含子目录、worktree、bare 仓库旁），一律不碰；
- 否则 `git init` → 本仓库没有 user.name / user.email 时写本地兜底身份（不改全局配置）
  → `git add -A`（遵守文件夹里已有的 .gitignore）→ 提交 `TriWitness: initial snapshot`（空文件夹也提交）。

所有 git 调用走 run_capture（输出写临时文件、stdin 为空、超时杀进程树），避免 Windows git 启动器卡死。
"""

from __future__ import annotations

from pathlib import Path

from triwitness.core.errors import SandboxError
from triwitness.sandbox.local import run_capture, run_quiet

FALLBACK_NAME = "TriWitness"
FALLBACK_EMAIL = "triwitness@local"
COMMIT_MESSAGE = "TriWitness: initial snapshot"
GIT_TIMEOUT_S = 120


def inside_git_repo(path: Path) -> bool:
    """path 本身或任何上级目录是 git 仓库（工作区或 git 目录内部）。"""
    if any((p / ".git").exists() for p in (path, *path.parents)):  # rev-parse 遇到 safe.directory 也会失败，先看目录
        return True
    out = run_quiet(["git", "-C", str(path), "rev-parse", "--is-inside-work-tree", "--is-inside-git-dir"],
                    timeout=30)  # fmt: skip
    return out is not None and "true" in out.split()


def _git(repo: Path, *args: str) -> int | None:
    code, _ = run_capture(["git", "-C", str(repo), *args], timeout=GIT_TIMEOUT_S)
    return code


def ensure_git_repo(repo: Path) -> bool:
    """需要时把 repo 初始化成 git 仓库并做首次提交。返回 True 表示这次做了初始化。"""
    if not repo.is_dir():
        raise SandboxError(f"所选文件夹不存在：{repo}")
    if inside_git_repo(repo):
        return False
    if run_quiet(["git", "--version"], timeout=30) is None:
        raise SandboxError("所选文件夹不是 git 仓库，且本机找不到 git，无法自动初始化（请先安装 Git）")
    if _git(repo, "init", "-q") != 0:
        raise SandboxError(f"自动初始化 git 仓库失败（git init）：{repo}")
    # 只看本仓库能读到的配置（含全局）；缺了才写本地兜底，不动全局配置
    if run_quiet(["git", "-C", str(repo), "config", "user.name"], timeout=30) is None:
        _git(repo, "config", "user.name", FALLBACK_NAME)
    if run_quiet(["git", "-C", str(repo), "config", "user.email"], timeout=30) is None:
        _git(repo, "config", "user.email", FALLBACK_EMAIL)
    if _git(repo, "add", "-A") != 0:
        raise SandboxError(f"自动初始化 git 仓库失败（git add -A）：{repo}")
    code = _git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "--no-verify",
                "-m", COMMIT_MESSAGE)  # fmt: skip
    if code != 0:
        raise SandboxError(f"自动初始化 git 仓库失败（首次提交）：{repo}")
    return True


__all__ = ["COMMIT_MESSAGE", "FALLBACK_EMAIL", "FALLBACK_NAME", "ensure_git_repo", "inside_git_repo"]
