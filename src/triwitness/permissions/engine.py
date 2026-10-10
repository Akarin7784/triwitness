"""权限引擎（spec 006 §5–§7）：deny → ask → allow，模式默认，非交互 ask→deny，审计。

引擎是“护栏”：在无沙箱后端下它不是安全边界（ADR-0005 §3.2）。真正不可关闭的硬底线在别处实现：
子进程环境变量白名单（sandbox.base.scrub_host_env）、超时杀进程树（各后端）、审计（本模块，所有模式都记录）。
"""

from __future__ import annotations

import os
import posixpath
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from triwitness.permissions.audit import AuditLog
from triwitness.permissions.config import EffectivePolicy
from triwitness.permissions.mode import ModeController
from triwitness.permissions.paths import NormPath, compile_path_pattern, escape_glob, normalize_path, to_posix_root
from triwitness.permissions.rules import (
    Category,
    Decision,
    Rule,
    match_command,
    match_domain,
    match_mcp,
)
from triwitness.permissions.shell import (
    SAFE_ENV_ASSIGNMENTS,
    ShellParseError,
    SimpleCommand,
    is_exec_string,
    parse_bash,
    parse_powershell,
    program,
    strip_wrappers,
)

PROTECTED_DIRS = (".git", ".triwitness", ".tw")
MAX_SAVED_RULES = 5
_RANK = {"allow": 0, "ask": 1, "deny": 2}

READ_ONLY_PROGRAMS = frozenset(
    {"ls", "cat", "head", "tail", "wc", "pwd", "echo", "printf", "which", "diff", "stat", "du", "file", "rg", "grep",
     "egrep", "fgrep", "tree", "cd", "true", "false", "basename", "dirname", "realpath", "readlink", "date", "whoami",
     "cut", "tr", "nl", "md5sum", "sha1sum", "sha256sum", "uniq", "test", "[", "find", "git", "type", "hostname"}
)  # fmt: skip
GIT_READ_ONLY = frozenset(
    {"status", "log", "diff", "show", "rev-parse", "ls-files", "blame", "describe", "shortlog", "ls-tree", "cat-file",
     "rev-list", "merge-base", "grep", "reflog"}
)  # fmt: skip
PS_READ_ONLY = frozenset(
    {"get-childitem", "get-content", "get-location", "test-path", "select-string", "get-item", "write-output",
     "resolve-path", "measure-object", "get-date", "get-command", "git"}
)  # fmt: skip
READ_FILE_ARGS = frozenset(
    {"cat", "head", "tail", "wc", "stat", "diff", "file", "du", "ls", "tree", "less", "more", "nl", "md5sum", "sha1sum",
     "sha256sum", "sort", "uniq", "cut", "source", ".", "get-content", "get-childitem", "get-item", "test-path"}
)  # fmt: skip
EDIT_FILE_ARGS = frozenset(
    {"rm", "rmdir", "mv", "cp", "touch", "mkdir", "chmod", "chown", "chgrp", "ln", "truncate", "install", "tee",
     "unlink", "shred", "remove-item", "set-content", "add-content", "new-item", "copy-item", "move-item", "out-file",
     "clear-content", "rename-item"}
)  # fmt: skip
_SKIP_FIRST_ARG = frozenset({"chmod", "chown", "chgrp"})
_NULL_TARGETS = frozenset({"/dev/null", "nul", "$null", "-"})


@dataclass
class Action:
    category: Category
    value: str  # 命令 / 路径 / 域名 / mcp 工具名
    tool: str = ""  # 具体工具名（bash / run_tests / read_file ...）
    cwd: str | None = None  # 命令或相对路径的工作目录（默认工作区根）


@dataclass
class Verdict:
    decision: Decision
    reason: str
    rule: Rule | None = None
    by_policy: bool = False  # 非交互把 ask 改判为 deny
    suggested_rules: list[str] = field(default_factory=list)
    sub: list[Verdict] = field(default_factory=list)

    @property
    def rule_raw(self) -> str | None:
        return self.rule.raw if self.rule else None


def _worst(vs: list[Verdict]) -> Verdict | None:
    return max(vs, key=lambda v: _RANK[v.decision]) if vs else None


class PermissionEngine:
    def __init__(
        self,
        policy: EffectivePolicy,
        *,
        windows: bool | None = None,
        home: str | None = None,
        workspace: str | None = None,
        resolve: Callable[[str], str] | None = None,
        long_name: Callable[[str], str | None] | None = None,
        audit: AuditLog | None = None,
        context: dict[str, str] | None = None,
        controller: ModeController | None = None,
    ) -> None:
        self.policy = policy
        self.windows = os.name == "nt" if windows is None else windows
        self.home = to_posix_root(home or str(Path.home()), windows=self.windows)
        self.workspace = to_posix_root(workspace or str(policy.workspace), windows=self.windows)
        self.roots = [NormPath(self.workspace, self.windows)] + [
            self._norm(d, self.workspace) for d in policy.additional_directories
        ]
        self.resolve = resolve
        self.long_name = long_name
        self.audit = audit
        self.context = dict(context or {})
        self.controller = controller
        self.session_rules: list[Rule] = []
        self._ws_np = NormPath(self.workspace, self.windows)

    # ------------------------------------------------------------ 公共入口
    @property
    def mode(self) -> str:
        return self.controller.mode if self.controller is not None else self.policy.mode

    def check(self, action: Action) -> Verdict:
        v = self._check(action)
        if self.mode == "full_access" and v.decision == "ask":
            v = Verdict("allow", f"full_access：{v.reason}", v.rule, sub=v.sub)
        if v.decision == "ask" and not self.policy.interactive:
            v = Verdict("deny", f"非交互运行，需要确认的操作一律拒绝（{v.reason}）", v.rule, by_policy=True, sub=v.sub)
        if v.decision == "ask" and not v.suggested_rules:
            v.suggested_rules = self.suggest_rules(action, v)
        if self.audit is not None:
            self.audit.record(
                {
                    **self.context,
                    "backend": self.policy.backend,
                    "mode": self.mode,
                    "interactive": self.policy.interactive,
                    "category": action.category,
                    "tool": action.tool,
                    "action": action.value,
                    "decision": v.decision,
                    "rule": v.rule_raw,
                    "rule_source": v.rule.source if v.rule else None,
                    "reason": v.reason,
                    "by": "policy" if (v.by_policy or v.decision != "ask") else None,
                }
            )
        return v

    def remember(self, action: Action, verdict: Verdict, scope: Literal["session", "always"]) -> list[str]:
        """用户选“本次任务内允许 / 总是允许”：返回要加的规则；session 立即生效，always 由调用方写入 local 文件。"""
        from triwitness.permissions.rules import parse_rule

        rules = verdict.suggested_rules or self.suggest_rules(action, verdict)
        for raw in rules:
            self.session_rules.append(parse_rule(raw, "allow", "session", source_root=self.workspace))
        return rules

    def suggest_rules(self, action: Action, verdict: Verdict) -> list[str]:
        if action.category in ("Bash", "PowerShell"):
            out: list[str] = []
            parse = parse_bash if action.category == "Bash" else parse_powershell
            try:
                subs = [strip_wrappers(c) for c in parse(action.value).commands]
            except ShellParseError:
                return []
            for sub in subs:
                if not sub.words:
                    continue
                if self._sub_allowed_without_prompt(sub, action):
                    continue
                if self._first_command_match("ask", action.category, self._forms(sub)):
                    continue  # ask 规则优先于 allow，记住也没用
                r = f"{action.category}({sub.value_text})"
                if r not in out:
                    out.append(r)
            return out[:MAX_SAVED_RULES]
        if action.category in ("Read", "Edit"):
            np = self._norm(action.value, action.cwd or self.workspace)
            return [f"{action.category}(/{escape_glob(np.path)})"]
        if action.category == "Fetch":
            return [f"Fetch(domain:{action.value.lower()})"]
        return [f"Mcp({action.value})"]

    # ------------------------------------------------------------ 规则检索
    def _rules(self, kind: Decision, category: str) -> list[Rule]:
        unrestricted = self.mode == "unrestricted"
        out = []
        for r in [*self.policy.rules, *self.session_rules]:
            if r.kind != kind or r.category != category:
                continue
            if not r.applies(backend=self.policy.backend, mode=self.mode):
                continue
            if unrestricted and r.source == "default":
                continue  # 勇士模式解除内置默认规则；用户自己写的 deny 仍生效
            out.append(r)
        return out

    def _first_command_match(self, kind: Decision, category: str, forms: list[str]) -> Rule | None:
        ci = category == "PowerShell" or self.windows
        for r in self._rules(kind, category):
            if any(match_command(r.pattern, f, ci=ci) for f in forms):
                return r
        return None

    # ------------------------------------------------------------ 分派
    def _check(self, action: Action) -> Verdict:
        if action.category in ("Bash", "PowerShell"):
            return self._check_command(action)
        if action.category in ("Read", "Edit"):
            return self._check_path(action.category, action.value, action.cwd or self.workspace, tool=action.tool)
        if action.category == "Fetch":
            return self._check_simple(action, lambda r: match_domain(r.pattern, action.value))
        return self._check_simple(action, lambda r: match_mcp(r.pattern, action.value))

    def _check_simple(self, action: Action, match: Callable[[Rule], bool]) -> Verdict:
        for kind in ("deny", "ask"):
            for r in self._rules(kind, action.category):
                if match(r):
                    return Verdict(kind, f"命中 {kind} 规则", r)
        for r in self._rules("allow", action.category):
            if match(r):
                return Verdict("allow", "命中 allow 规则", r)
        return self._mode_default(action.category, outside=True)

    def _mode_default(self, what: str, *, outside: bool = False) -> Verdict:
        m = self.mode
        if m in ("unrestricted", "full_access"):
            return Verdict("allow", f"{m} 模式")
        if m == "plan":
            return Verdict("deny", "plan 模式只允许只读操作")
        if m == "auto" and not outside:
            return Verdict("allow", "auto 模式（沙箱内）")
        return Verdict("ask", f"{what} 需要确认")

    # ------------------------------------------------------------ 路径
    def _norm(self, raw: str, cwd: str) -> NormPath:
        return normalize_path(raw, cwd=cwd, home=self.home, windows=self.windows, long_name=self.long_name)

    def _resolved(self, np: NormPath) -> NormPath:
        if self.resolve is None or np.flags:
            return np
        try:
            real = self.resolve(np.path)
        except OSError:
            return np
        return self._norm(real, "/")

    def _path_rule_match(self, kind: Decision, category: str, nps: list[NormPath], *, all_forms: bool) -> Rule | None:
        """同一配置源内按顺序处理 `!` 排除；deny/ask 任一形式匹配即命中，allow 要求所有形式都匹配。"""
        cats = ["Read", "Edit"] if (category == "Edit" and kind != "allow") else [category]
        restrictive = kind != "allow"
        rules = [r for c in cats for r in self._rules(kind, c)]
        if not rules:
            return None

        def matches(np: NormPath) -> Rule | None:
            hit: Rule | None = None
            by_source: dict[str, bool] = {}
            for r in rules:
                if r.pattern is None:
                    return r
                pat = compile_path_pattern(
                    r.pattern,
                    restrictive=restrictive,
                    source_root=r.source_root or self.workspace,
                    cwd=self.workspace,
                    home=self.home,
                    windows=self.windows,
                )
                ok = pat.regex.match(np.path) is not None
                if pat.negated:
                    if ok and by_source.get(r.source):
                        by_source[r.source] = False
                        hit = None
                    continue
                if ok:
                    by_source[r.source] = True
                    hit = hit or r
            return hit if any(by_source.values()) else None

        hits = [matches(np) for np in nps]
        if all_forms:
            return hits[0] if all(h is not None for h in hits) else None
        return next((h for h in hits if h is not None), None)

    def _inside(self, np: NormPath) -> bool:
        return any(np.is_within(r) for r in self.roots)

    def _protected(self, np: NormPath) -> bool:
        for root in self.roots[:1]:
            for d in PROTECTED_DIRS:
                if np.is_within(NormPath(posixpath.join(root.path, d), self.windows)):
                    return True
        return False

    def _check_path(self, category: str, raw: str, cwd: str, *, tool: str = "", derived: bool = False) -> Verdict:
        np = self._norm(raw, cwd)
        if self.mode == "unrestricted":
            r = self._path_rule_match("deny", category, [np, self._resolved(np)], all_forms=False)
            if r:
                return Verdict("deny", f"命中 deny 规则（{category} {np.path}）", r)
            return Verdict("allow", "unrestricted 模式")
        if "ads" in np.flags:
            return Verdict("deny", f"拒绝 NTFS 备用数据流路径：{raw}")
        if "reserved" in np.flags:
            return Verdict("deny", f"拒绝 Windows 保留设备名：{raw}")
        if "unc" in np.flags:
            return Verdict("ask", f"网络路径（访问会发送 Windows 凭证）：{raw}")
        if "short_name" in np.flags:
            return Verdict("ask", f"无法展开 8.3 短文件名：{raw}")
        if "unresolved_var" in np.flags:
            return Verdict("ask", f"路径含变量 / 命令替换，无法确定目标：{raw}")
        real = self._resolved(np)
        forms = [np] if real.key == np.key else [np, real]
        r = self._path_rule_match("deny", category, forms, all_forms=False)
        if r:
            return Verdict("deny", f"命中 deny 规则（{category} {np.path}）", r)
        if category == "Edit" and any(self._protected(f) for f in forms):
            return Verdict("deny", f"受保护路径只读：{np.path}")
        r = self._path_rule_match("ask", category, forms, all_forms=False)
        if r:
            return Verdict("ask", f"命中 ask 规则（{category} {np.path}）", r)
        r = self._path_rule_match("allow", category, forms, all_forms=True)
        if r:
            return Verdict("allow", "命中 allow 规则", r)
        inside = all(self._inside(f) for f in forms)
        if category == "Read":
            if inside:
                return Verdict("allow", "工作区内读取")
            if self.mode in ("full_access",):
                return Verdict("allow", "full_access 模式")
            where = "经符号链接指向工作区外" if self._inside(np) else "工作区外"
            return Verdict("ask", f"读取{where}的文件：{real.path}")
        # Edit
        if self.mode == "plan":
            return Verdict("deny", "plan 模式不修改文件")
        if inside:
            if self.mode == "ask":
                return Verdict("ask", f"修改文件：{np.path}")
            return Verdict("allow", "工作区内修改")
        if self.mode == "full_access":
            return Verdict("allow", "full_access 模式")
        return Verdict("ask", f"修改工作区外的文件：{real.path}")

    # ------------------------------------------------------------ 命令
    def _forms(self, sub: SimpleCommand) -> list[str]:
        forms = [sub.raw_text, sub.value_text]
        if sub.words:
            base = program(sub)
            if base != sub.words[0].value:
                forms.append(" ".join([base, *[w.value for w in sub.words[1:]]]))
        return list(dict.fromkeys(f for f in forms if f))

    def _check_command(self, action: Action) -> Verdict:
        cat = action.category
        try:
            parsed = parse_bash(action.value) if cat == "Bash" else parse_powershell(action.value)
        except ShellParseError as e:
            r = self._first_command_match("deny", cat, [action.value])
            if r:
                return Verdict("deny", "命中 deny 规则", r)
            if self.mode == "unrestricted":
                return Verdict("allow", "unrestricted 模式")
            return Verdict("ask", f"无法解析命令（{e}）")
        # 整条命令也过一遍 deny（如 `Bash(* | sh)` 这类跨子命令的模式）
        r = self._first_command_match("deny", cat, [" ".join(action.value.split())])
        if r:
            return Verdict("deny", "命中 deny 规则", r)
        cwd = action.cwd or self.workspace
        subs: list[Verdict] = []
        for raw_sub in parsed.commands:
            sub = strip_wrappers(raw_sub)
            v = self._check_sub(sub, action, cwd)
            subs.append(v)
            # 跟踪 `cd <字面路径>`，供后续子命令解析相对路径
            if sub.words and program(sub).lower() in ("cd", "set-location") and len(sub.words) > 1:
                tgt = sub.words[1].value
                if "$" not in tgt and not raw_sub.nested:
                    cwd = self._norm(tgt, cwd).path
        worst = _worst(subs)
        assert worst is not None
        return Verdict(worst.decision, worst.reason, worst.rule, sub=subs)

    def _path_args(self, sub: SimpleCommand) -> tuple[list[str], list[str], list[str]]:
        """返回 (读目标, 写目标, 所有像路径的参数)。"""
        reads: list[str] = []
        edits: list[str] = []
        args_all: list[str] = []
        prog = program(sub).lower()
        rest = sub.words[1:]
        positional = [w.value for w in rest if not w.value.startswith("-") or w.value == "-"]
        for w in rest:
            v = w.value
            if v.startswith("-") and "=" in v:
                args_all.append(v.split("=", 1)[1])
            elif not v.startswith("-"):
                args_all.append(v)
        if prog in ("grep", "egrep", "fgrep", "rg", "select-string"):
            has_e = any(w.value in ("-e", "-f", "--regexp", "--file", "-pattern") for w in rest)
            reads.extend(positional if has_e else positional[1:])
        elif prog == "cd" or prog == "set-location":
            reads.extend(positional[:1])
        elif prog in READ_FILE_ARGS:
            reads.extend(positional)
        if prog in EDIT_FILE_ARGS:
            edits.extend(positional[1:] if prog in _SKIP_FIRST_ARG else positional)
        if prog == "sed" and any(w.value.startswith("-i") or w.value == "--in-place" for w in rest):
            edits.extend(positional[1:])
        for red in sub.redirects:
            if red.op in (">&", "<&") or red.target.lower() in _NULL_TARGETS or red.target.startswith("&"):
                continue
            (reads if red.op == "<" else edits).append(red.target)
        return reads, edits, args_all

    def _is_read_only(self, sub: SimpleCommand) -> bool:
        if not sub.words:
            return True
        prog = program(sub).lower()
        args = [w.value for w in sub.words[1:]]
        if sub.redirects and any(r.op not in ("<", ">&", "<&") for r in sub.redirects):
            # 有输出重定向：命令本身仍可只读，写目标另行检查
            pass
        if prog == "git":
            if not args or args[0].startswith("-"):
                return False  # git -C / -c 可执行其他目录的钩子
            subcmd, rest = args[0], args[1:]
            if any(a.startswith("--output") or a == "--ext-diff" for a in rest):
                return False
            if subcmd in GIT_READ_ONLY:
                return True
            if subcmd == "branch":
                return all(
                    a in ("--list", "-a", "-r", "-v", "-vv", "--all", "--remotes", "--show-current") for a in rest
                )
            if subcmd == "remote":
                return rest in ([], ["-v"])
            if subcmd == "stash":
                return rest[:1] == ["list"]
            return False
        if prog in PS_READ_ONLY:
            return True
        if prog not in READ_ONLY_PROGRAMS:
            return False
        if prog == "find":
            bad = {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprintf", "-fls", "-fprint0"}
            return not any(a in bad for a in args) and not any(w.has_glob and not w.quoted for w in sub.words[1:])
        if prog == "file":
            return not any(a in ("-m", "-f", "--magic-file", "--files-from") for a in args)
        if prog in ("sort",):
            return not any(a.startswith(("-o", "--output")) for a in args)
        return True

    def _assigns_safe(self, sub: SimpleCommand) -> bool:
        return all(k in SAFE_ENV_ASSIGNMENTS for k, _ in sub.assigns)

    def _explicit_allow(self, sub: SimpleCommand, cat: str) -> Rule | None:
        if not self._assigns_safe(sub):
            return None
        ci = cat == "PowerShell" or self.windows
        exec_str = is_exec_string(sub)
        for r in self._rules("allow", cat):
            if exec_str and not r.exact:
                continue
            if r.pattern is None and exec_str:
                continue
            if any(match_command(r.pattern, f, ci=ci) for f in (sub.raw_text, sub.value_text)):
                return r
        return None

    def _sub_allowed_without_prompt(self, sub: SimpleCommand, action: Action) -> bool:
        return self._explicit_allow(sub, action.category) is not None or self._is_read_only(sub)

    def _check_sub(self, sub: SimpleCommand, action: Action, cwd: str) -> Verdict:
        cat = action.category
        if not sub.words:
            return Verdict("allow", "仅变量赋值")
        forms = self._forms(sub)
        r = self._first_command_match("deny", cat, forms)
        if r:
            return Verdict("deny", f"命中 deny 规则：{sub.value_text}", r)
        reads, edits, args_all = self._path_args(sub)
        unrestricted = self.mode == "unrestricted"
        # 所有像路径的参数都过一遍 Read/Edit 的 deny（如 `cp .env /tmp/x`）
        for a in args_all:
            if a.startswith(("http://", "https://")):
                continue
            np = self._norm(a, cwd)
            if np.flags & {"unc", "unresolved_var"}:
                continue
            hit = self._path_rule_match("deny", "Edit", [np, self._resolved(np)], all_forms=False)
            if hit:
                return Verdict("deny", f"命中 deny 规则（参数 {a}）", hit)
        if unrestricted:
            return Verdict("allow", "unrestricted 模式")
        derived = [self._check_path("Read", p, cwd, derived=True) for p in reads]
        derived += [self._check_path("Edit", p, cwd, derived=True) for p in edits]
        dv = _worst(derived)
        if dv is not None and dv.decision == "deny":
            return dv
        r = self._first_command_match("ask", cat, forms)
        if r:
            return Verdict("ask", f"命中 ask 规则：{sub.value_text}", r)
        if dv is not None and dv.decision == "ask":
            return dv
        exec_str = is_exec_string(sub)
        allow_rule = self._explicit_allow(sub, cat)
        if allow_rule is not None:
            return Verdict("allow", "命中 allow 规则", allow_rule)
        if self._is_read_only(sub) and not exec_str:
            return Verdict("allow", "只读命令")
        if action.tool == "run_tests" and self.mode in ("auto_edit", "auto", "full_access"):
            return Verdict("allow", "任务配置的测试命令")
        if exec_str and self.mode not in ("auto", "full_access"):
            return Verdict("ask" if self.mode != "plan" else "deny", f"执行字符串形式的命令：{sub.value_text}")
        if self.mode in ("auto", "full_access"):
            return Verdict("allow", f"{self.mode} 模式")
        if self.mode == "plan":
            return Verdict("deny", "plan 模式只允许只读命令")
        return Verdict("ask", f"运行命令：{sub.value_text}")
