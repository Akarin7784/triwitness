"""路径规范化与 gitignore 风格匹配（spec 006 §4.3）。

所有路径统一成 POSIX 形式再比较：Windows `C:\\Users\\A` → `/c/Users/A`（与 Git Bash 一致），比较时大小写不敏感。
纯函数：真实文件系统相关的两步（符号链接解析、8.3 短名展开）通过回调注入，便于在 Linux 上测试 Windows 行为。
"""

from __future__ import annotations

import posixpath
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache

RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
_SHORT_NAME_RE = re.compile(r"~\d+(?=[./]|$)")
_DRIVE_RE = re.compile(r"^([A-Za-z]):(?:/|$)")
_GITBASH_DRIVE_RE = re.compile(r"^/([A-Za-z])(?:/|$)")


@dataclass(frozen=True)
class NormPath:
    path: str  # 规范化后的 POSIX 绝对路径（保留原大小写）
    windows: bool = False
    flags: frozenset[str] = field(default_factory=frozenset)  # unc / ads / reserved / short_name / unresolved_var

    @property
    def key(self) -> str:
        return self.path.lower() if self.windows else self.path

    def is_within(self, root: NormPath) -> bool:
        a, b = self.key, root.key.rstrip("/")
        return a == b or a.startswith(b + "/") or b == ""


def _drive_to_posix(p: str) -> str:
    m = _DRIVE_RE.match(p)
    if m:
        return "/" + m.group(1).lower() + p[2:]
    return p


def normalize_path(
    raw: str,
    *,
    cwd: str,
    home: str,
    windows: bool = False,
    long_name: Callable[[str], str | None] | None = None,
) -> NormPath:
    """把工具或命令里出现的路径规范化。cwd / home 本身应已是规范化的 POSIX 形式。"""
    flags: set[str] = set()
    p = raw.strip()
    if "$" in p or "`" in p or "…" in p:
        flags.add("unresolved_var")
    if windows:
        p = p.replace("\\", "/")
        for pre in ("//?/UNC/", "//./UNC/"):
            if p.upper().startswith(pre):
                p = "//" + p[len(pre) :]
        for pre in ("//?/", "//./"):
            if p.startswith(pre):
                p = p[len(pre) :]
        if p.startswith("//") and not p.startswith("///"):
            flags.add("unc")
            return NormPath(path=posixpath.normpath(p), windows=True, flags=frozenset(flags))
        if p.lower().startswith("/cygdrive/"):
            p = p[len("/cygdrive") :]
        p = _drive_to_posix(p)
        m = _GITBASH_DRIVE_RE.match(p)
        if m:
            p = "/" + m.group(1).lower() + p[2:]
    if p == "~" or p.startswith("~/"):
        p = home + p[1:]
    if not p.startswith("/"):
        p = posixpath.join(cwd, p)
    p = posixpath.normpath(p)
    if p.startswith("//"):
        p = "/" + p.lstrip("/")
    if windows:
        segs = p.split("/")
        out: list[str] = []
        for i, seg in enumerate(segs):
            if i == 0:
                out.append(seg)
                continue
            s = seg.rstrip(". ") if seg not in (".", "..") else seg
            if ":" in s:
                flags.add("ads")
            stem = s.split(".", 1)[0].upper().rstrip()
            if stem in RESERVED_NAMES:
                flags.add("reserved")
            out.append(s)
        p = posixpath.normpath("/".join(out))
        if _SHORT_NAME_RE.search(p):
            expanded = long_name(p) if long_name is not None else None
            if expanded:
                p = normalize_path(expanded, cwd=cwd, home=home, windows=True).path
            else:
                flags.add("short_name")
    return NormPath(path=p, windows=windows, flags=frozenset(flags))


def windows_long_name(p: str) -> str | None:
    """真实 Windows 上把 8.3 短名展开（`/c/Users/RUNNER~1/x` → `C:\\Users\\runneradmin\\x`）。

    逐级向上找到存在的前缀再展开，不存在的尾部原样接回；其他平台返回 None。"""
    if sys.platform != "win32":
        return None
    import ctypes

    m = re.match(r"^/([a-zA-Z])(/.*)?$", p)
    if not m:
        return None
    cur = m.group(1).upper() + ":" + (m.group(2) or "/").replace("/", "\\")
    tail: list[str] = []
    fn = ctypes.windll.kernel32.GetLongPathNameW
    fn.restype = ctypes.c_uint
    fn.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    while True:
        buf = ctypes.create_unicode_buffer(32768)
        n = fn(cur, buf, 32768)
        if 0 < n < 32768:
            out = buf.value
            return out.rstrip("\\") + "\\" + "\\".join(reversed(tail)) if tail else out
        head, _, leaf = cur.rpartition("\\")
        if not leaf:  # 已到盘符根仍不存在
            return None
        tail.append(leaf)
        cur = head + "\\" if head.endswith(":") else head


def to_posix_root(p: str, *, windows: bool) -> str:
    """把配置里的根目录（工作区、家目录）转成 POSIX 形式。"""
    return normalize_path(p, cwd="/", home="/", windows=windows).path


# ---------------------------------------------------------------- gitignore 风格模式


def _glob_to_regex(body: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            out.append(re.escape(body[i + 1]))
            i += 2
            continue
        if body.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if body.startswith("/**", i) and i + 3 == len(body):
            out.append("(?:/.*)?")
            i += 3
            continue
        if body.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            end = body.find("]", i + 1)
            if end == -1:
                out.append(re.escape(c))
            else:
                cls = body[i + 1 : end]
                if cls.startswith("!"):
                    cls = "^" + cls[1:]
                out.append("[" + cls.replace("\\", "\\\\") + "]")
                i = end
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


@dataclass(frozen=True)
class PathPattern:
    raw: str
    regex: re.Pattern[str]
    negated: bool


@lru_cache(maxsize=4096)
def compile_path_pattern(
    pattern: str, *, restrictive: bool, source_root: str, cwd: str, home: str, windows: bool
) -> PathPattern:
    """编译 Read/Edit 规则的路径部分。

    - `//p` 绝对；`~/p` 家目录；`/p` 相对配置源根；`p` / `./p` 相对当前工作区根；
    - 不含 `/` 的裸名在任意深度匹配；目录模式同时匹配其下所有文件；
    - restrictive（deny/ask）时，单段目录模式 `seg/**` 也在任意深度匹配（allow 只匹配根下）。
    """
    raw = pattern
    negated = pattern.startswith("!")
    if negated:
        pattern = pattern[1:]
    if pattern.startswith("//"):
        anchor, body = "", pattern[2:]
        if windows:
            m = re.match(r"^([A-Za-z])(/|$)", body)
            if m:
                body = m.group(1).lower() + body[1:]
    elif pattern.startswith("~/"):
        anchor, body = home, pattern[2:]
    elif pattern.startswith("/") and not negated:
        anchor, body = source_root, pattern[1:]
    else:
        anchor = cwd
        body = pattern[2:] if pattern.startswith("./") else pattern.lstrip("/")
        stripped = body.rstrip("/")
        single_dir = re.fullmatch(r"[^/*?\[\]]+/\*\*", stripped) is not None
        if "/" not in stripped or (restrictive and single_dir):
            body = "**/" + stripped
    anchor = anchor.rstrip("/")
    rx = "^" + re.escape(anchor) + "/" + _glob_to_regex(body.rstrip("/")) + "(?:/.*)?$"
    return PathPattern(raw=raw, regex=re.compile(rx, re.IGNORECASE if windows else 0), negated=negated)


def escape_glob(path: str) -> str:
    """把字面路径转义成只匹配自身的模式（“总是允许”生成规则时用）。"""
    return re.sub(r"([*?\[\]!])", r"\\\1", path)
