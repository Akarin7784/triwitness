"""规则语法 `Tool` / `Tool(specifier)`（spec 006 §4）。"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, cast, get_args

from triwitness.core.errors import ConfigError

Decision = Literal["allow", "ask", "deny"]
Category = Literal["Read", "Edit", "Bash", "PowerShell", "Fetch", "Mcp"]
Source = Literal["default", "user", "project", "local", "session", "managed"]
CATEGORIES: tuple[str, ...] = get_args(Category)
PATH_CATEGORIES = ("Read", "Edit")
COMMAND_CATEGORIES = ("Bash", "PowerShell")
# 小写工具名 → 类别（方便用户写 bash(...)、read_file(...)）
_ALIASES = {
    "bash": "Bash", "run_tests": "Bash", "powershell": "PowerShell", "pwsh": "PowerShell",
    "read": "Read", "read_file": "Read", "list_files": "Read", "grep": "Read",
    "edit": "Edit", "edit_file": "Edit", "write_file": "Edit", "write": "Edit",
    "fetch": "Fetch", "webfetch": "Fetch", "mcp": "Mcp",
}  # fmt: skip
_RULE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\((.*)\))?\s*$", re.S)


@dataclass(frozen=True)
class Rule:
    raw: str
    category: Category
    pattern: str | None  # None = 整个工具
    kind: Decision
    source: Source
    source_root: str = ""  # `/path` 锚点（项目根或 ~/.triwitness）
    backends: frozenset[str] | None = None  # 只在这些后端生效
    modes: frozenset[str] | None = None  # 只在这些模式生效
    warning: str | None = None

    @property
    def exact(self) -> bool:
        return self.pattern is not None and "*" not in self.pattern

    def applies(self, *, backend: str, mode: str) -> bool:
        return (self.backends is None or backend in self.backends) and (self.modes is None or mode in self.modes)


def parse_rule(
    raw: str,
    kind: Decision,
    source: Source,
    *,
    source_root: str = "",
    backends: frozenset[str] | None = None,
    modes: frozenset[str] | None = None,
) -> Rule:
    m = _RULE_RE.match(raw)
    if not m:
        raise ConfigError(f"规则语法错误：{raw!r}（应为 Tool 或 Tool(specifier)）")
    name, spec = m.group(1), m.group(2)
    cat = name if name in CATEGORIES else _ALIASES.get(name.lower())
    if cat is None:
        raise ConfigError(f"未知工具类别 {name!r}（规则 {raw!r}；可用：{', '.join(CATEGORIES)}）")
    pattern: str | None = None if spec is None else spec.strip()
    warning: str | None = None
    if pattern in ("", "*"):
        pattern = None
    if pattern is not None and cat in COMMAND_CATEGORIES:
        if pattern.endswith(":*"):
            pattern = pattern[:-2] + " *"
        pattern = " ".join(pattern.split())
        if kind == "allow":
            first = pattern.find("*")
            words_before = pattern[:first].split() if first >= 0 else []
            if first >= 0 and len(words_before) < 2 and pattern.split()[0] not in ("ls", "cat", "echo", "pwd"):
                warning = f"allow 规则 {raw!r} 的 * 出现在子命令之前，可能放行过宽"
    if pattern is not None and cat == "Fetch":
        if not pattern.startswith("domain:"):
            raise ConfigError(f"Fetch 规则必须写成 Fetch(domain:<host>)：{raw!r}")
        pattern = pattern[len("domain:") :].strip().lower().rstrip(".")
        if pattern == "*":
            pattern = None if kind != "allow" else "*"
    if kind == "allow" and pattern is not None and pattern.startswith("!"):
        raise ConfigError(f"! 排除只能用于 deny / ask 规则：{raw!r}")
    return Rule(
        raw=raw.strip(),
        category=cast(Category, cat),
        pattern=pattern,
        kind=kind,
        source=source,
        source_root=source_root,
        backends=backends,
        modes=modes,
        warning=warning,
    )


@lru_cache(maxsize=4096)
def _command_regex(pattern: str, ci: bool) -> re.Pattern[str]:
    parts = [re.escape(p) for p in pattern.split("*")]
    rx = ".*".join(parts)
    if pattern.endswith(" *") and pattern.count("*") == 1:
        rx = f"(?:{rx}|{re.escape(pattern[:-2])})"
    return re.compile(rf"^{rx}$", re.S | (re.IGNORECASE if ci else 0))


def match_command(pattern: str | None, command: str, *, ci: bool = False) -> bool:
    """命令模式匹配：`*` 匹配任意文本（含空格）；末尾 ` *` 也匹配不带参数的裸命令。"""
    if pattern is None:
        return True
    return _command_regex(pattern, ci).match(" ".join(command.split())) is not None


def match_domain(pattern: str | None, host: str) -> bool:
    """`example.com` 精确；`*.example.com` 任意深度子域（不含顶级）；其他位置的 `*` 只匹配一段。"""
    if pattern is None or pattern == "*":
        return True
    host = host.lower().rstrip(".")
    if pattern.startswith("*."):
        return host.endswith(pattern[1:])
    rx = r"\.".join("[^.]+" if seg == "*" else re.escape(seg).replace(r"\*", "[^.]*") for seg in pattern.split("."))
    return re.fullmatch(rx, host) is not None


def match_mcp(pattern: str | None, name: str) -> bool:
    return pattern is None or fnmatch.fnmatchcase(name, pattern)
