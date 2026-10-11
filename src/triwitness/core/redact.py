"""文本脱敏：审计日志、事件 display、轨迹导出共用（spec 005 §5.5、spec 006 §10）。"""

from __future__ import annotations

import re
from typing import Any

# 值的字符类不含反斜杠：JSON 文本里 `\"` / `\\` / `\n` 是转义序列，吃掉一半会让后面的引号失去转义、弄坏 JSON
# （W5-13 git-leak-recovery：`secret ===\"` 被替换成 `secret =***"`，3 份 artifact 不再是合法 JSON）。
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "sk-***"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "gh*_***"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA***"),
    (re.compile(r"(?i)(authorization\s*:\s*(?:(?:bearer|basic|token)\s+)?)(?!\*\*\*)[^\s'\"\\]+"), r"\1***"),
    (re.compile(r"(?i)(bearer\s+)(?!\*\*\*)[A-Za-z0-9._\-+/=]{4,}"), r"\1***"),
    (re.compile(r"(?i)(x-api-key\s*:\s*)[^\s'\"\\]+"), r"\1***"),
    (
        re.compile(
            r"(?i)\b([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD)[A-Z0-9_]*)(\s*[=:]\s*)(\\*['\"]?)([^\s'\"\\]+)"
        ),
        r"\1\2\3***",
    ),
]


def redact_text(text: str, *, max_len: int | None = None) -> str:
    """去掉常见密钥形态；可选截断到 max_len 字符（末尾加 …）。"""
    out = text
    for pat, rep in _PATTERNS:
        out = pat.sub(rep, out)
    if max_len is not None and len(out) > max_len:
        out = out[: max_len - 1] + "…"
    return out


def redact_obj(obj: Any) -> Any:
    """逐个字符串脱敏（dict / list 递归）；用于先脱敏、再序列化的 JSON 产物，保证结果一定是合法 JSON。"""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [redact_obj(v) for v in obj]
    return obj
