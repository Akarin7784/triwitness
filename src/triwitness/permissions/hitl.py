"""人工确认点（04 §3.7，W4-10；spec 010 §8.3）：改依赖声明、改 CI / 构建配置。

这两类改动影响面超出本次 Issue（供应链、所有人的流水线），不交给审核模型（auto_review）自动放行：
- 交互运行 → 一定问人（approval_requested，tool 仍是 Edit / Bash，reason 写明是哪个确认点）；
- 非交互（终端非 TTY、CI）→ 拒绝并告诉模型原因；
- 评测（eval_mode）与 full_access 不经过这里（评测禁止人工介入；full_access 是用户自己解除的护栏）。
命令侧只拦“会改依赖声明”的命令（uv add、npm install <包>…）；`pip install -r` 之类只装不改声明的沿用权限规则。
"""

from __future__ import annotations

import fnmatch
import posixpath
import re
from dataclasses import dataclass
from typing import Literal

HitlKind = Literal["dependency", "ci_config"]
LABELS: dict[HitlKind, str] = {"dependency": "修改依赖声明", "ci_config": "修改 CI / 构建配置"}

DEPENDENCY_FILES = (
    "pyproject.toml", "setup.py", "setup.cfg", "requirements*.txt", "requirements/*.txt", "constraints*.txt",
    "Pipfile", "Pipfile.lock", "poetry.lock", "uv.lock", "pdm.lock", "environment.yml", "environment.yaml",
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb",
    "Cargo.toml", "Cargo.lock", "go.mod", "go.sum", "Gemfile", "Gemfile.lock", "pom.xml", "build.gradle",
    "build.gradle.kts", "composer.json", "composer.lock",
)  # fmt: skip
CI_FILES = (
    ".github/workflows/*", ".github/actions/*", ".gitlab-ci.yml", ".circleci/*", "azure-pipelines.yml",
    "Jenkinsfile", ".travis.yml", "bitbucket-pipelines.yml", "Makefile", "Dockerfile", "*.Dockerfile",
    "docker-compose*.yml", "docker-compose*.yaml", "tox.ini", "noxfile.py", ".pre-commit-config.yaml",
)  # fmt: skip
_DEP_CMD = re.compile(
    r"(?:^|[;&|]\s*|\s)(?:"
    r"uv\s+(?:add|remove)\b|uv\s+lock\s+.*--upgrade|poetry\s+(?:add|remove|update)\b|pdm\s+(?:add|remove|update)\b"
    r"|pipenv\s+(?:install|uninstall|update)\s+(?:-\S+\s+)*[^-\s]|npm\s+(?:i|install|add|uninstall|update|upgrade)\s+(?:-\S+\s+)*[^-\s]"
    r"|pnpm\s+(?:add|remove|update|up)\b|yarn\s+(?:add|remove|upgrade)\b|bun\s+(?:add|remove)\b"
    r"|cargo\s+(?:add|remove|update)\b|go\s+get\b|go\s+mod\s+tidy\b|bundle\s+(?:add|update)\b"
    r"|composer\s+(?:require|remove|update)\b)"
)


@dataclass(frozen=True)
class HitlPoint:
    kind: HitlKind
    target: str  # 文件路径或命令

    @property
    def label(self) -> str:
        return LABELS[self.kind]


def _match(path: str, globs: tuple[str, ...]) -> bool:
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    base = posixpath.basename(p)
    for g in globs:
        if "/" in g:
            if fnmatch.fnmatch(p, g) or fnmatch.fnmatch(p, "*/" + g):
                return True
        elif fnmatch.fnmatch(base, g):
            return True
    return False


def classify_edit(path: str) -> HitlKind | None:
    if _match(path, CI_FILES):
        return "ci_config"
    if _match(path, DEPENDENCY_FILES):
        return "dependency"
    return None


def classify_command(command: str) -> HitlKind | None:
    return "dependency" if _DEP_CMD.search(" " + command) else None


def hitl_point(category: str, value: str, *, dependency: bool = True, ci: bool = True) -> HitlPoint | None:
    """权限动作 → 人工确认点；不属于任何确认点返回 None。"""
    kind: HitlKind | None = None
    if category == "Edit":
        kind = classify_edit(value)
    elif category in ("Bash", "PowerShell"):
        kind = classify_command(value)
    if (kind == "dependency" and not dependency) or (kind == "ci_config" and not ci):
        return None
    return HitlPoint(kind, value) if kind else None


__all__ = ["CI_FILES", "DEPENDENCY_FILES", "LABELS", "HitlKind", "HitlPoint", "classify_command", "classify_edit",
           "hitl_point"]  # fmt: skip
