"""改动文件的静态检查（04 §4.1 F，W3-08）：ruff、pyright、bandit、密钥扫描。

- 只看改动的 .py 文件；给了基线沙箱时只把**新增**的问题算失败（仓库原有的告警不怪 Agent）。
- 工具不在沙箱里（任务镜像通常没装 ruff / pyright / bandit）→ `skipped`，并写明原因；不为此联网安装。
- 密钥扫描是纯函数，只扫 diff 新增行，不依赖任何工具。
"""

from __future__ import annotations

import json
import re
import shlex
from typing import Literal

from pydantic import BaseModel, Field

from triwitness.sandbox.base import ExecResult, Sandbox
from triwitness.verify.diffutil import added_lines, split_patch

Status = Literal["pass", "fail", "skipped"]

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("assigned_secret", re.compile(
        r"(?i)\b[A-Z0-9_]*(?:api_?key|secret|token|password|passwd)[A-Z0-9_]*\s*[=:]\s*['\"][^'\"\s]{12,}['\"]")),
]  # fmt: skip
_MISSING = re.compile(r"No module named|command not found|not recognized as|: not found", re.I)


class SecretHit(BaseModel):
    path: str
    line: int
    kind: str


class StaticReport(BaseModel):
    checks: dict[str, Status] = Field(default_factory=dict)
    details: dict[str, str] = Field(default_factory=dict)
    bandit_medium_high: int = 0  # 新增的中 / 高告警（风险因子 security_scan）
    secrets: list[SecretHit] = Field(default_factory=list)


def scan_secrets(patch: str) -> list[SecretHit]:
    out: list[SecretHit] = []
    for fp in split_patch(patch):
        for no, text in added_lines(fp):
            for kind, pat in SECRET_PATTERNS:
                if pat.search(text):
                    out.append(SecretHit(path=fp.path, line=no, kind=kind))
                    break
    return out


def changed_python(patch: str) -> list[str]:
    return sorted(fp.path for fp in split_patch(patch) if fp.path.endswith(".py") and not fp.deleted)


def _missing(r: ExecResult) -> bool:
    return r.exit_code in (126, 127) or bool(_MISSING.search(r.stderr + r.stdout[:500]))


def _json(text: str) -> object | None:
    i = min((x for x in (text.find("{"), text.find("[")) if x >= 0), default=-1)
    if i < 0:
        return None
    try:
        return json.loads(text[i:])
    except ValueError:
        return None


def _name(path: str) -> str:
    """问题 id 里只留文件名：基线与修复后在不同工作区，绝对路径不同（Windows 还是反斜杠）。"""
    return path.replace("\\", "/").rsplit("/", 1)[-1]


# 每个工具：命令模板 + 从输出里取“问题 id 列表”（用 id 集合比较，基线已有的不算）
def _ruff_ids(out: object) -> list[str]:
    if not isinstance(out, list):
        return []
    return [f"{_name(d.get('filename', ''))}:{d.get('code')}:{d.get('message')}" for d in out]


def _pyright_ids(out: object) -> list[str]:
    if not isinstance(out, dict):
        return []
    diags = out.get("generalDiagnostics") or []
    return [f"{_name(d.get('file', ''))}:{d.get('rule', '')}:{d.get('message', '')}"
            for d in diags if d.get("severity") == "error"]  # fmt: skip


def _bandit_ids(out: object) -> list[str]:
    if not isinstance(out, dict):
        return []
    return [f"{_name(r.get('filename', ''))}:{r.get('test_id')}:{r.get('code', '').strip()[:80]}"
            for r in out.get("results") or [] if r.get("issue_severity") in ("MEDIUM", "HIGH")]  # fmt: skip


TOOLS = {
    "ruff": ("{py} -m ruff check --no-cache --output-format=json --exit-zero {files}", _ruff_ids),
    "pyright": ("pyright --outputjson {files}", _pyright_ids),
    "bandit": ("{py} -m bandit -q -f json {files}", _bandit_ids),
}


async def _issues(sb: Sandbox, name: str, files: list[str], py: str, timeout_s: int) -> list[str] | str:
    """问题 id 列表；工具不可用时返回原因字符串。"""
    tmpl, parse = TOOLS[name]
    r = await sb.exec(tmpl.format(py=py, files=" ".join(shlex.quote(f) for f in files)), timeout_s=timeout_s)
    if _missing(r):
        return f"{name} 不可用（沙箱里没装）"
    out = _json(r.stdout)
    if out is None:
        return f"{name} 输出无法解析（exit {r.exit_code}）：{(r.stderr or r.stdout)[-200:]}"
    return parse(out)


async def run_static_checks(
    sb: Sandbox,
    patch: str,
    *,
    base: Sandbox | None = None,
    python: str = "python",
    tools: tuple[str, ...] = ("ruff", "pyright", "bandit"),
    timeout_s: int = 300,
) -> StaticReport:
    rep = StaticReport()
    files = changed_python(patch)
    for name in tools:
        if not files:
            rep.checks[name], rep.details[name] = "skipped", "没有改动 .py 文件"
            continue
        now = await _issues(sb, name, files, python, timeout_s)
        if isinstance(now, str):
            rep.checks[name], rep.details[name] = "skipped", now
            continue
        before: list[str] = []
        if base is not None:
            existing = [f for f in files if not any(fp.path == f and fp.new_file for fp in split_patch(patch))]
            prev = await _issues(base, name, existing, python, timeout_s) if existing else []
            before = prev if isinstance(prev, list) else []
        new = [i for i in now if i not in set(before)]
        if name == "bandit":
            rep.bandit_medium_high = len(new)
        rep.checks[name] = "fail" if new else "pass"
        rep.details[name] = (f"新增 {len(new)} 条：" + "；".join(new[:5])) if new else (
            f"基线已有 {len(before)} 条，未新增" if before else "无问题")  # fmt: skip
    rep.secrets = scan_secrets(patch)
    rep.checks["secrets"] = "fail" if rep.secrets else "pass"
    rep.details["secrets"] = "；".join(f"{h.path}:{h.line} {h.kind}" for h in rep.secrets[:5]) if rep.secrets else "无"
    return rep


__all__ = ["SecretHit", "StaticReport", "changed_python", "run_static_checks", "scan_secrets"]
