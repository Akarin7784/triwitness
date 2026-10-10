"""命令行解析：把 bash / PowerShell 命令拆成简单命令（spec 006 §4.2）。

不是完整的 shell 解析器，只覆盖权限判定需要的子集；拿不准时抛 ShellParseError，由引擎按 ask 处理。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_COMMAND_CHARS = 10_000
_OPS = ("&&", "||", "|&", ";;", ";", "|", "&", "\n")
_REDIR_RE = re.compile(r"^(\d*|&)(>>|>\||>&|<>|<<<|<<-|<<|>|<&|<)$")
_REDIR_INLINE_RE = re.compile(r"^(\d*|&)(>>|>\||>&|<<<|<<-|<<|>|<&|<)(.+)$")
_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_DANGEROUS_EXPANSION = re.compile(r"\$\{[^}]*@[PEAKa]\}|\$\{![^}]*\}|=\(|\$\{[^}]*\$\(")
_KEYWORD_PREFIX = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "time"}
_KEYWORD_ALONE = {"fi", "done", "esac", "}", "else", "then", "do"}


class ShellParseError(ValueError):
    """无法可靠解析（引号不闭合、括号不平衡、操作符后为空、危险展开、过长……）。"""


@dataclass
class Word:
    raw: str  # 原文（含引号）
    value: str  # 去引号后的值
    quoted: bool = False
    has_glob: bool = False  # 含未加引号的 * ? [


@dataclass
class Redirect:
    op: str  # > >> < 2> &> 等（去掉 fd 前缀后的核心操作符）
    target: str
    fd: str = ""


@dataclass
class SimpleCommand:
    words: list[Word] = field(default_factory=list)
    assigns: list[tuple[str, str]] = field(default_factory=list)
    redirects: list[Redirect] = field(default_factory=list)
    nested: bool = False  # 来自 $(...)、反引号、子 shell

    @property
    def argv(self) -> list[str]:
        return [w.value for w in self.words]

    @property
    def raw_text(self) -> str:
        return " ".join(w.raw for w in self.words)

    @property
    def value_text(self) -> str:
        return " ".join(w.value for w in self.words)


@dataclass
class ParsedCommand:
    commands: list[SimpleCommand]


class _Lexer:
    def __init__(self, text: str) -> None:
        self.s = text
        self.i = 0
        self.commands: list[SimpleCommand] = []
        self.pending_heredocs: list[tuple[str, bool]] = []

    # ------------------------------------------------------------ 主循环
    def parse(self, *, nested: bool = False, stop: str | None = None) -> None:
        cur = SimpleCommand(nested=nested)
        expect_command = True  # 刚遇到操作符，后面必须有命令
        saw_op = False
        while True:
            self._skip_blanks()
            if self.i >= len(self.s):
                break
            c = self.s[self.i]
            if stop is not None and c == stop:
                self.i += 1
                self._finish(cur)
                if saw_op and expect_command and cur.words == [] and not cur.assigns:
                    raise ShellParseError("操作符后缺少命令")
                return
            if c == "#" and (self.i == 0 or self.s[self.i - 1] in " \t\n;&|("):
                while self.i < len(self.s) and self.s[self.i] != "\n":
                    self.i += 1
                continue
            op = self._match_op()
            if op is not None:
                if op == "\n":
                    self._consume_heredocs()
                    if not cur.words and not cur.assigns and not cur.redirects:
                        continue  # 空行；`a &&\n b` 也允许
                empty = not cur.words and not cur.assigns and not cur.redirects
                if empty and (op in ("&&", "||", "|", "|&", ";;") or (op in (";", "&") and not self.commands)):
                    raise ShellParseError(f"操作符 {op!r} 前缺少命令")
                self._finish(cur)
                cur = SimpleCommand(nested=nested)
                saw_op = True
                expect_command = op in ("&&", "||", "|", "|&")
                continue
            if c == "(" and not cur.words:
                self.i += 1
                if self.s.startswith("(", self.i):  # (( 算术 ))
                    raise ShellParseError("不支持 (( ))")
                self.parse(nested=True, stop=")")
                continue
            if c == ")":
                raise ShellParseError("括号不平衡")
            if c in "<>" and self.s.startswith("(", self.i + 1):  # 进程替换 <( ) >( )
                self.i += 2
                self.parse(nested=True, stop=")")
                cur.words.append(Word(raw="<(…)", value="<(…)"))
                continue
            if c == "(":
                if self.s.startswith("()", self.i):
                    raise ShellParseError("不支持函数定义")
                raise ShellParseError("命令中间出现未加引号的 (")
            before = self.i
            word = self._read_word()
            if word is None:
                if self.i == before:
                    raise ShellParseError(f"无法解析的字符 {c!r}")
                continue
            red = _REDIR_RE.match(word.raw) if not word.quoted else None
            if red is None:
                red_inline = (
                    re.match(r"^(\d*|&)(>>|>\||>&|<<<|<<-|<<|>|<&|<)(.+)$", word.raw) if not word.quoted else None
                )
                if red_inline is not None and not word.raw.startswith(("<(", ">(")):
                    fd, op_, tgt = red_inline.groups()
                    self._add_redirect(cur, fd, op_, tgt)
                    expect_command = False
                    continue
            if red is not None:
                fd, op_ = red.groups()
                self._skip_blanks()
                tgt_word = self._read_word()
                if tgt_word is None:
                    raise ShellParseError("重定向缺少目标")
                self._add_redirect(cur, fd, op_, tgt_word.value)
                expect_command = False
                continue
            if not cur.words and _ASSIGN_RE.match(word.raw):
                k, _, v = word.value.partition("=")
                cur.assigns.append((k, v))
            else:
                cur.words.append(word)
            expect_command = False
        if stop is not None:
            raise ShellParseError("括号不平衡")
        if self.pending_heredocs:
            raise ShellParseError("heredoc 未结束")
        if saw_op and expect_command:
            raise ShellParseError("命令以操作符结尾")
        self._finish(cur)

    # ------------------------------------------------------------ 辅助
    def _finish(self, cur: SimpleCommand) -> None:
        if not cur.words and not cur.assigns and not cur.redirects:
            return
        # 去掉控制流关键字
        while cur.words and cur.words[0].raw in _KEYWORD_PREFIX and not cur.words[0].quoted:
            cur.words.pop(0)
        if cur.words and cur.words[0].raw in ("for", "select", "case") and not cur.words[0].quoted:
            if cur.words[0].raw == "case":
                raise ShellParseError("不支持 case 语句")
            return  # `for x in a b c` 本身不执行命令
        if len(cur.words) == 1 and cur.words[0].raw in _KEYWORD_ALONE:
            return
        if cur.words and cur.words[0].raw.endswith("()"):
            raise ShellParseError("不支持函数定义")
        self.commands.append(cur)

    def _add_redirect(self, cur: SimpleCommand, fd: str, op: str, target: str) -> None:
        if op in ("<<", "<<-"):
            self.pending_heredocs.append((target.strip("'\""), op == "<<-"))
            return
        if op == "<<<":
            return  # here-string：数据
        cur.redirects.append(Redirect(op=op, target=target, fd=fd))

    def _consume_heredocs(self) -> None:
        while self.pending_heredocs:
            delim, strip_tabs = self.pending_heredocs.pop(0)
            while True:
                if self.i >= len(self.s):
                    raise ShellParseError(f"heredoc 缺少结束符 {delim}")
                end = self.s.find("\n", self.i)
                line = self.s[self.i : end if end != -1 else len(self.s)]
                self.i = end + 1 if end != -1 else len(self.s)
                if (line.lstrip("\t") if strip_tabs else line) == delim:
                    break

    def _skip_blanks(self) -> None:
        while self.i < len(self.s):
            if self.s[self.i] in " \t\r":
                self.i += 1
            elif self.s.startswith("\\\n", self.i):
                self.i += 2
            else:
                break

    def _match_op(self) -> str | None:
        for op in _OPS:
            if self.s.startswith(op, self.i):
                # `>&` / `&>` 是重定向，不是后台运行
                if op == "&" and (self.s.startswith("&>", self.i) or (self.i > 0 and self.s[self.i - 1] in "<>")):
                    return None
                if op == "|" and self.i > 0 and self.s[self.i - 1] == ">":
                    return None
                self.i += len(op)
                return op
        return None

    def _read_word(self) -> Word | None:
        raw: list[str] = []
        val: list[str] = []
        quoted = False
        glob = False
        s = self.s
        while self.i < len(s):
            c = s[self.i]
            sofar = "".join(raw)
            if c in " \t\r\n;|()":
                if not (c == "|" and sofar.endswith(">")):  # `>|` 是重定向
                    break
            elif c == "&":
                if not (sofar.endswith(("<", ">")) or (not raw and s.startswith("&>", self.i))):
                    break
            elif c in "<>" and raw and not (sofar.isdigit() or sofar == "&" or sofar[-1] in "<>&"):
                break  # 单词后紧跟重定向：`echo hi>out`
            if c == "\\":
                if self.i + 1 >= len(s):
                    raise ShellParseError("末尾反斜杠")
                raw.append(s[self.i : self.i + 2])
                val.append(s[self.i + 1])
                self.i += 2
                continue
            if c == "'":
                end = s.find("'", self.i + 1)
                if end == -1:
                    raise ShellParseError("单引号未闭合")
                raw.append(s[self.i : end + 1])
                val.append(s[self.i + 1 : end])
                self.i = end + 1
                quoted = True
                continue
            if c == '"':
                self.i += 1
                start = self.i - 1
                buf: list[str] = []
                while True:
                    if self.i >= len(s):
                        raise ShellParseError("双引号未闭合")
                    d = s[self.i]
                    if d == "\\" and self.i + 1 < len(s):
                        nxt = s[self.i + 1]
                        buf.append(nxt if nxt in '"\\$`\n' else d + nxt)
                        self.i += 2
                        continue
                    if d == '"':
                        self.i += 1
                        break
                    if d == "$" and s.startswith("$(", self.i):
                        buf.append(self._substitution())
                        continue
                    if d == "`":
                        buf.append(self._backtick())
                        continue
                    buf.append(d)
                    self.i += 1
                raw.append(s[start : self.i])
                val.append("".join(buf))
                quoted = True
                continue
            if c == "$" and s.startswith("$(", self.i):
                if s.startswith("$((", self.i):
                    end = s.find("))", self.i)
                    if end == -1:
                        raise ShellParseError("算术展开未闭合")
                    raw.append(s[self.i : end + 2])
                    val.append(s[self.i : end + 2])
                    self.i = end + 2
                    continue
                start = self.i
                v = self._substitution()
                raw.append(s[start : self.i])
                val.append(v)
                continue
            if c == "`":
                start = self.i
                v = self._backtick()
                raw.append(s[start : self.i])
                val.append(v)
                continue
            if c == "$" and s.startswith("${", self.i):
                end = s.find("}", self.i)
                if end == -1:
                    raise ShellParseError("${ 未闭合")
                raw.append(s[self.i : end + 1])
                val.append(s[self.i : end + 1])
                self.i = end + 1
                continue
            if c in "*?[":
                glob = True
            raw.append(c)
            val.append(c)
            self.i += 1
        if not raw:
            return None
        return Word(raw="".join(raw), value="".join(val), quoted=quoted, has_glob=glob)

    def _substitution(self) -> str:
        """解析 $( ... )，内部命令作为嵌套命令加入；返回占位值。"""
        self.i += 2
        self.parse(nested=True, stop=")")
        return "$(…)"

    def _backtick(self) -> str:
        end = self.s.find("`", self.i + 1)
        if end == -1:
            raise ShellParseError("反引号未闭合")
        inner = self.s[self.i + 1 : end]
        sub = _Lexer(inner)
        sub.parse(nested=True)
        for c in sub.commands:
            c.nested = True
        self.commands.extend(sub.commands)
        self.i = end + 1
        return "`…`"


def parse_bash(cmd: str) -> ParsedCommand:
    if len(cmd) > MAX_COMMAND_CHARS:
        raise ShellParseError(f"命令超过 {MAX_COMMAND_CHARS} 字符")
    if _DANGEROUS_EXPANSION.search(cmd):
        raise ShellParseError("含危险的参数 / 进程替换")
    if not cmd.strip():
        raise ShellParseError("空命令")
    lx = _Lexer(cmd)
    lx.parse()
    if not lx.commands:
        raise ShellParseError("没有可执行的命令")
    return ParsedCommand(commands=lx.commands)


# ---------------------------------------------------------------- 包装剥离

# 包装命令 → 需要跳过的“带值选项”
_WRAPPERS: dict[str, set[str]] = {
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "time": set(),
    "nice": {"-n", "--adjustment"},
    "nohup": set(),
    "stdbuf": {"-i", "-o", "-e"},
    "command": set(),
    "builtin": set(),
    "noglob": set(),
}
SAFE_ENV_ASSIGNMENTS = frozenset(
    {"NODE_ENV", "RUST_BACKTRACE", "RUST_LOG", "CI", "LANG", "LC_ALL", "TZ", "NO_COLOR", "FORCE_COLOR", "TERM",
     "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE", "DEBUG"}
)  # fmt: skip


def _basename(prog: str) -> str:
    b = prog.replace("\\", "/").rsplit("/", 1)[-1]
    low = b.lower()
    for ext in (".exe", ".cmd", ".bat"):
        if low.endswith(ext):
            return b[: -len(ext)]
    return b


def strip_wrappers(cmd: SimpleCommand) -> SimpleCommand:
    """剥离 timeout / nice / nohup / xargs(无参) / env 等包装，返回新的 SimpleCommand。"""
    words = list(cmd.words)
    assigns = list(cmd.assigns)
    changed = True
    while changed and words:
        changed = False
        prog = _basename(words[0].value)
        if prog == "command" and len(words) > 1 and words[1].value in ("-v", "-V"):
            break
        if prog in _WRAPPERS:
            takes = _WRAPPERS[prog]
            j = 1
            while j < len(words) and words[j].value.startswith("-") and words[j].value != "-":
                opt = words[j].value
                j += 2 if opt in takes and "=" not in opt else 1
            if prog == "timeout":
                j += 1  # DURATION
            words = words[j:]
            changed = True
        elif prog == "xargs" and len(words) > 1 and not words[1].value.startswith("-"):
            words = words[1:]
            changed = True
        elif prog == "env":
            j = 1
            while j < len(words) and (words[j].value.startswith("-") or _ASSIGN_RE.match(words[j].value)):
                if _ASSIGN_RE.match(words[j].value):
                    k, _, v = words[j].value.partition("=")
                    assigns.append((k, v))
                j += 1
            words = words[j:]
            changed = True
    return SimpleCommand(words=words, assigns=assigns, redirects=cmd.redirects, nested=cmd.nested)


def program(cmd: SimpleCommand) -> str:
    return _basename(cmd.words[0].value) if cmd.words else ""


_EXEC_STRING: dict[str, set[str]] = {
    "sh": {"-c"}, "bash": {"-c"}, "zsh": {"-c"}, "dash": {"-c"}, "ksh": {"-c"}, "fish": {"-c"},
    "python": {"-c"}, "python3": {"-c"}, "py": {"-c"}, "node": {"-e", "--eval", "-p"}, "deno": {"eval"},
    "perl": {"-e", "-E"}, "ruby": {"-e"}, "php": {"-r"},
    "pwsh": {"-c", "-command", "-encodedcommand", "-ec"}, "powershell": {"-c", "-command", "-encodedcommand", "-ec"},
    "cmd": {"/c", "/k"},
}  # fmt: skip
_ALWAYS_EXEC = {"eval", "source", ".", "exec", "xargs", "su", "sudo", "doas", "watch", "setsid", "flock", "ionice"}


def is_exec_string(cmd: SimpleCommand) -> bool:
    """会把一段字符串当命令执行的形式（sh -c、python -c、eval、find -exec……）。"""
    if not cmd.words:
        return False
    prog = program(cmd).lower()
    args = [w.value.lower() for w in cmd.words[1:]]
    if prog in _ALWAYS_EXEC:
        return True
    flags = _EXEC_STRING.get(prog)
    if flags and any(a in flags for a in args):
        return True
    return prog == "find" and any(a in ("-exec", "-execdir", "-ok", "-okdir", "-delete") for a in args)


# ---------------------------------------------------------------- PowerShell（最小子集）

PS_ALIASES: dict[str, str] = {
    "ls": "Get-ChildItem", "dir": "Get-ChildItem", "gci": "Get-ChildItem",
    "cat": "Get-Content", "gc": "Get-Content", "type": "Get-Content",
    "rm": "Remove-Item", "del": "Remove-Item", "ri": "Remove-Item", "rmdir": "Remove-Item", "rd": "Remove-Item",
    "erase": "Remove-Item",
    "cp": "Copy-Item", "copy": "Copy-Item", "cpi": "Copy-Item", "mv": "Move-Item", "move": "Move-Item",
    "mi": "Move-Item", "iwr": "Invoke-WebRequest", "curl": "Invoke-WebRequest", "wget": "Invoke-WebRequest",
    "irm": "Invoke-RestMethod", "iex": "Invoke-Expression", "kill": "Stop-Process", "spps": "Stop-Process",
    "echo": "Write-Output", "write": "Write-Output", "sc": "Set-Content", "ni": "New-Item", "cd": "Set-Location",
    "sl": "Set-Location", "chdir": "Set-Location", "pwd": "Get-Location", "gl": "Get-Location",
    "sls": "Select-String", "gi": "Get-Item", "ac": "Add-Content", "start": "Start-Process", "saps": "Start-Process",
}  # fmt: skip


def parse_powershell(cmd: str) -> ParsedCommand:
    """拆分 `;`、`|`、`&&`、`||`、换行；脚本块 `{}`、子表达式 `$( )`、`&` 调用运算符一律视为无法解析。"""
    if len(cmd) > MAX_COMMAND_CHARS:
        raise ShellParseError(f"命令超过 {MAX_COMMAND_CHARS} 字符")
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    quote: str | None = None
    while i < len(cmd):
        c = cmd[i]
        if quote:
            if c == "`" and i + 1 < len(cmd):
                buf.append(cmd[i : i + 2])
                i += 2
                continue
            if c == quote:
                quote = None
            elif quote == '"' and cmd.startswith("$(", i):
                raise ShellParseError("PowerShell 子表达式不支持")
            buf.append(c)
            i += 1
            continue
        if c in "'\"":
            quote = c
            buf.append(c)
            i += 1
            continue
        if c in "{}" or cmd.startswith("$(", i) or cmd.startswith("@(", i):
            raise ShellParseError("PowerShell 脚本块 / 子表达式不支持")
        two = cmd[i : i + 2]
        if two in ("&&", "||"):
            parts.append("".join(buf))
            buf = []
            i += 2
            continue
        if c == "&":
            raise ShellParseError("PowerShell 调用运算符 & 不支持")
        if c in ";|\n":
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    if quote:
        raise ShellParseError("引号未闭合")
    parts.append("".join(buf))
    out: list[SimpleCommand] = []
    for idx, p in enumerate(parts):
        p = p.strip()
        if not p:
            if 0 < idx < len(parts) - 1 or (idx == len(parts) - 1 and len(parts) > 1):
                raise ShellParseError("操作符两侧缺少命令")
            continue
        words: list[Word] = []
        for m in re.finditer(r"'[^']*'|\"(?:`.|[^\"])*\"|\S+", p):
            t = m.group(0)
            v = t[1:-1] if t[:1] in "'\"" and len(t) >= 2 else t
            words.append(Word(raw=t, value=v, quoted=t[:1] in "'\""))
        if words:
            head = words[0].value
            canon = PS_ALIASES.get(head.lower(), head)
            words[0] = Word(raw=canon, value=canon)
            out.append(SimpleCommand(words=words))
    if not out:
        raise ShellParseError("没有可执行的命令")
    return ParsedCommand(commands=out)
