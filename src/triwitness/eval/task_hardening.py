"""评测任务的防作弊加固（W5，landscape 2026-10-11 §4.2；arXiv 2609.08149 / 2609.06780）。

与 verify/anticheat.py（补丁是否改测试）互补：这里管任务本身别泄露答案。

公开基准里最大的偏差来源是“抄答案”：从 git 历史 / 上游托管站 / 任务元数据里找到修复。这里放任务工厂和沙箱共用的规则：
- `CODE_HOSTS`：沙箱出网时屏蔽的代码托管域名（保留 PyPI 等依赖镜像）；
- `anon_task_id()`：实例 ID 匿名化（原 ID 带仓库名 + PR 号，等于答案定位符）；
- `sanitize_instruction()`：去掉 Issue 正文里指向提交 / PR / 对比的链接和完整 SHA；
- `audit_task()`：静态检查一个任务目录（新任务应全部通过；旧任务只报告，不改动隐藏测试）。

镜像本身已经是“无历史”的：源码来自 base_commit 的归档包，没有 .git（比“单提交仓库”更严格）；
新任务的镜像另外禁用 git hooks（`core.hooksPath=/dev/null`）。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

CODE_HOSTS: tuple[str, ...] = (
    "github.com", "api.github.com", "raw.githubusercontent.com", "codeload.github.com", "objects.githubusercontent.com",
    "gist.github.com", "gist.githubusercontent.com", "gitlab.com", "bitbucket.org", "gitee.com", "gitcode.com",
    "gitcode.net", "codeberg.org", "sourceforge.net", "git.sr.ht", "huggingface.co", "datasets-server.huggingface.co",
)  # fmt: skip
# git 只允许本地协议：沙箱里 git clone / fetch 任何远端都会失败（pip 的 git+https 依赖也会失败，所以依赖要在构建时装好）
GIT_ENV: dict[str, str] = {"GIT_ALLOW_PROTOCOL": "file", "GIT_TERMINAL_PROMPT": "0"}

_SHA = re.compile(r"\b[0-9a-f]{40}\b")
_LINK = re.compile(
    r"https?://(?:www\.)?(?:github\.com|gitlab\.com|gitee\.com|gitcode\.com)/[\w.-]+/[\w.-]+/"
    r"(?:-/)?(?:commit|commits|pull|pulls|merge_requests|compare|tree|blob)/[^\s)\]>\"']+"
)
_ANON = re.compile(r"^t-[0-9a-f]{10}$")
HOOKS_OFF = "RUN git config --system core.hooksPath /dev/null"


def anon_task_id(instance_id: str, *, salt: str = "triwitness") -> str:
    """稳定、不可逆的匿名 ID：t-<sha256(salt:instance_id) 前 10 位>。映射记在 task.toml 的 metadata 里。"""
    return "t-" + hashlib.sha256(f"{salt}:{instance_id}".encode()).hexdigest()[:10]


def sanitize_instruction(text: str) -> tuple[str, list[str]]:
    """去掉提交 / PR / 对比 / 分支文件链接与 40 位 SHA；返回（新文本, 被去掉的片段）。"""
    removed: list[str] = []

    def drop(m: re.Match[str]) -> str:
        removed.append(m[0])
        return "[链接已移除]"

    out = _LINK.sub(drop, text)

    def drop_sha(m: re.Match[str]) -> str:
        removed.append(m[0])
        return "[提交号已移除]"

    out = _SHA.sub(drop_sha, out)
    return out, removed


@dataclass(frozen=True)
class AuditFinding:
    level: Literal["error", "warn"]
    code: str
    message: str


def audit_task(d: Path, *, base_commit: str | None = None) -> list[AuditFinding]:
    """静态检查（不构建镜像）：答案定位符、隐藏测试 / 参考解进镜像、git 历史、出网。"""
    import tomllib

    out: list[AuditFinding] = []
    meta: dict = {}
    toml = d / "task.toml"
    if toml.is_file():
        meta = tomllib.loads(toml.read_text(encoding="utf-8"))
    md = meta.get("metadata") or {}
    sha = base_commit or md.get("base_commit")
    if not _ANON.match(d.name):
        out.append(AuditFinding("warn", "id_not_anonymized", f"任务 ID {d.name} 未匿名化（可能暴露仓库名 / PR 号）"))
    instr = d / "instruction.md"
    if instr.is_file():
        text = instr.read_text(encoding="utf-8")
        _, removed = sanitize_instruction(text)
        if removed:
            out.append(AuditFinding("warn", "instruction_links", f"Issue 正文含 {len(removed)} 个提交 / PR 链接或 SHA"))
        if sha and sha[:12] in text:
            out.append(AuditFinding("error", "instruction_base_sha", "Issue 正文含 base_commit"))
    df = d / "environment" / "Dockerfile"
    if df.is_file():
        text = df.read_text(encoding="utf-8")
        body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
        if re.search(r"\bgit\s+clone\b", body):
            out.append(AuditFinding("error", "git_clone", "Dockerfile 用 git clone（镜像里会有完整历史）"))
        if re.search(r"^\s*(COPY|ADD)\s+[^\n]*\b(tests|solution)\b", body, re.M):
            out.append(AuditFinding("error", "hidden_in_image", "Dockerfile 把 tests/ 或 solution/ 拷进镜像"))
        if "core.hooksPath" not in body and "git" in body:
            out.append(AuditFinding("warn", "git_hooks", "镜像没有禁用 git hooks"))
    env = meta.get("environment") or {}
    if env.get("network_mode", "no-network") != "no-network":
        out.append(AuditFinding("error", "network", f"运行时网络为 {env.get('network_mode')}（应为 no-network）"))
    return out


__all__ = ["CODE_HOSTS", "GIT_ENV", "HOOKS_OFF", "AuditFinding", "anon_task_id", "audit_task", "sanitize_instruction"]
