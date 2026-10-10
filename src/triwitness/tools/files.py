"""文件类工具（spec 003 §5.2，W1-19）：read_file / write_file / edit_file / list_files / grep。

所有访问都经 Sandbox；list_files / grep 在 none 后端用宿主 Python 实现（不依赖 rg），其他后端在沙箱里用 find / grep。
"""

from __future__ import annotations

import difflib
import fnmatch
import os
import re
import shlex
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from triwitness.core.errors import SandboxError
from triwitness.tools.base import BaseTool, SideEffects, ToolContext, ToolResult

MAX_READ_LINES = 400
MAX_LIST = 200
MAX_MATCHES = 100
SKIP_DIRS = {".git", ".tw", "node_modules", ".venv", "__pycache__"}


async def _exists(ctx: ToolContext, path: str) -> bool:
    try:
        await ctx.sandbox.read_file(path)
    except SandboxError as e:
        if "不存在" in str(e):
            return False
        raise
    return True


def _decode(data: bytes) -> str:
    return data.decode("utf-8", "replace")


# ---------------------------------------------------------------- read_file
class ReadFileParams(BaseModel):
    path: str = Field(description="文件路径（相对工作区根）")
    start_line: int = Field(default=1, ge=1, description="起始行（从 1 开始）")
    end_line: int | None = Field(default=None, ge=1, description="结束行（含）；省略则读到第 start_line+399 行")


class ReadFile(BaseTool):
    name = "read_file"
    Params = ReadFileParams
    refetchable = True

    async def run(self, params: ReadFileParams, ctx: ToolContext) -> ToolResult:
        try:
            data = await ctx.sandbox.read_file(params.path)
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="not_found" if "不存在" in str(e) else "sandbox")
        if b"\x00" in data[:8000]:
            return ToolResult(ok=False, content=f"{params.path} 是二进制文件（{len(data)} 字节）", error_code="binary")
        lines = _decode(data).splitlines()
        total = len(lines)
        start = params.start_line
        end = min(params.end_line or start + MAX_READ_LINES - 1, start + MAX_READ_LINES - 1, total)
        if total == 0:
            return ToolResult(ok=True, content=f"（{params.path} 是空文件）", data={"total_lines": 0})
        if start > total:
            return ToolResult(ok=False, content=f"start_line={start} 超出文件行数 {total}", error_code="range")
        body = "\n".join(f"{i:>6}\t{lines[i - 1]}" for i in range(start, end + 1))
        more = f"\n…（共 {total} 行；继续读用 start_line={end + 1}）" if end < total else ""
        return ToolResult(ok=True, content=body + more, data={"total_lines": total, "start": start, "end": end})


# ---------------------------------------------------------------- write_file
class WriteFileParams(BaseModel):
    path: str = Field(description="新文件路径（相对工作区根）")
    content: str = Field(description="完整文件内容")


class WriteFile(BaseTool):
    name = "write_file"
    Params = WriteFileParams
    side_effects: SideEffects = "workspace"

    async def run(self, params: WriteFileParams, ctx: ToolContext) -> ToolResult:
        try:
            if await _exists(ctx, params.path):
                return ToolResult(ok=False, content=f"{params.path} 已存在；修改已有文件请用 edit_file",
                                  error_code="exists")  # fmt: skip
            await ctx.sandbox.write_file(params.path, params.content.encode())
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="sandbox")
        n = params.content.count("\n") + (0 if params.content.endswith("\n") or not params.content else 1)
        return ToolResult(
            ok=True, content=f"已新建 {params.path}（{n} 行）", data={"path": params.path, "kind": "added"}
        )


# ---------------------------------------------------------------- edit_file
class EditFileParams(BaseModel):
    path: str = Field(description="要修改的文件")
    old_str: str = Field(min_length=1, description="要替换的原文，必须在文件中唯一出现（含足够上下文）")
    new_str: str = Field(description="替换后的文本")


def _line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


class EditFile(BaseTool):
    name = "edit_file"
    Params = EditFileParams
    side_effects: SideEffects = "workspace"

    async def run(self, params: EditFileParams, ctx: ToolContext) -> ToolResult:
        try:
            text = _decode(await ctx.sandbox.read_file(params.path))
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="not_found" if "不存在" in str(e) else "sandbox")
        old_str, new_str = params.old_str, params.new_str
        if "\r\n" in text and "\r" not in old_str and old_str not in text:
            # CRLF 文件（Windows 常见）：模型给的是 \n，按文件的换行风格匹配与写回
            old_str, new_str = old_str.replace("\n", "\r\n"), new_str.replace("\r\n", "\n").replace("\n", "\r\n")
        count = text.count(old_str)
        if count == 0:
            hint = ""
            first = params.old_str.strip().splitlines()[0] if params.old_str.strip() else ""
            if first:
                lines = text.splitlines()
                close = difflib.get_close_matches(first.strip(), [ln.strip() for ln in lines], n=3, cutoff=0.6)
                if close:
                    where = [
                        f"  第 {i + 1} 行：{lines[i].strip()}" for i, ln in enumerate(lines) if ln.strip() in close
                    ]
                    hint = "\n最相近的行：\n" + "\n".join(where[:3])
            return ToolResult(
                ok=False,
                content=(
                    f"old_str 在 {params.path} 中出现 0 次。"
                    f"先用 read_file 确认原文（空格、缩进、换行需完全一致）。{hint}"
                ),
                error_code="no_match",
            )
        if count > 1:
            starts = [m.start() for m in re.finditer(re.escape(old_str), text)]
            lines = ", ".join(str(_line_of(text, s)) for s in starts[:10])
            return ToolResult(
                ok=False,
                content=(
                    f"old_str 在 {params.path} 中出现 {count} 次（第 {lines} 行）。"
                    "请在 old_str 里多带几行上下文，使其唯一。"
                ),
                error_code="multiple_matches",
            )
        new = text.replace(old_str, new_str, 1)
        try:
            await ctx.sandbox.write_file(params.path, new.encode())
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="sandbox")
        line = _line_of(text, text.index(old_str))
        return ToolResult(ok=True, content=f"已修改 {params.path}（第 {line} 行附近）",
                          data={"path": params.path, "kind": "modified", "line": line})  # fmt: skip


# ---------------------------------------------------------------- 宿主路径辅助
def _host_root(ctx: ToolContext, path: str) -> Path | None:
    resolve = getattr(ctx.sandbox, "resolve_path", None)
    if resolve is None:
        return None
    return resolve(path)


def _walk(root: Path) -> list[Path]:
    out: list[Path] = []
    if root.is_file():
        return [root]
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        out.extend(Path(dirpath) / f for f in sorted(filenames) if f not in SKIP_DIRS)
    return out


def _rel(p: Path, base: Path) -> str:
    try:
        return p.relative_to(base).as_posix()
    except ValueError:
        return p.as_posix()


# ---------------------------------------------------------------- list_files
class ListFilesParams(BaseModel):
    path: str = Field(default=".", description="目录（相对工作区根）")
    glob: str | None = Field(default=None, description="文件名通配，如 *.py 或 src/**/*.ts")
    max: int = Field(default=MAX_LIST, ge=1, le=MAX_LIST, description="最多返回条数")


def _glob_ok(rel: str, glob: str | None) -> bool:
    if not glob:
        return True
    return fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(rel.rsplit("/", 1)[-1], glob)


class GitIgnore:
    """.gitignore 的常用子集（W2-07）：注释、`!` 取反、`dir/` 只匹配目录、含 `/` 的模式相对根锚定、
    其余匹配任意层的名字。最后一条匹配的规则生效；只读仓库根的 .gitignore（够 Agent 用，不追求和 git 完全一致）。"""

    def __init__(self, text: str = "") -> None:
        self.rules: list[tuple[str, bool, bool, bool]] = []  # (模式, 取反, 只匹配目录, 锚定)
        for raw in text.splitlines():
            line = raw.rstrip()
            if not line or line.startswith("#"):
                continue
            neg = line.startswith("!")
            line = line[1:] if neg else line
            dir_only = line.endswith("/")
            line = line.rstrip("/")
            anchored = "/" in line
            self.rules.append((line.lstrip("/"), neg, dir_only, anchored))

    def _match(self, rel: str, is_dir: bool) -> bool | None:
        hit: bool | None = None
        name = rel.rsplit("/", 1)[-1]
        for pat, neg, dir_only, anchored in self.rules:
            if dir_only and not is_dir:
                continue
            if fnmatch.fnmatchcase(rel if anchored else name, pat):
                hit = not neg
        return hit

    def ignored(self, rel: str) -> bool:
        if not self.rules:
            return False
        parts = rel.split("/")
        return any(self._match("/".join(parts[:i]), is_dir=i < len(parts)) for i in range(1, len(parts) + 1))


async def _gitignore(ctx: ToolContext) -> GitIgnore:
    try:
        return GitIgnore(_decode(await ctx.sandbox.read_file(".gitignore")))
    except SandboxError:
        return GitIgnore()


class ListFiles(BaseTool):
    name = "list_files"
    Params = ListFilesParams
    refetchable = True

    async def run(self, params: ListFilesParams, ctx: ToolContext) -> ToolResult:
        try:
            files = await collect_files(ctx, params.path)
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="sandbox")
        files = [f for f in files if _glob_ok(f, params.glob)]
        shown = files[: params.max]
        more = (
            f"\n…（共 {len(files)} 个，只显示前 {params.max} 个；用 glob 缩小范围）" if len(files) > params.max else ""
        )
        return ToolResult(ok=True, content="\n".join(shown) + more if shown else "（没有文件）",
                          data={"count": len(files)})  # fmt: skip


async def collect_files(ctx: ToolContext, path: str = ".") -> list[str]:
    """path 下所有文件（相对工作区根，已排序，跳过 SKIP_DIRS 与 .gitignore）。list_files / repo_map 共用。"""
    root = _host_root(ctx, path)
    if root is not None:
        base = _host_root(ctx, ".") or root
        files = [_rel(p, base) for p in _walk(root)]
    else:
        q = shlex.quote(path)
        r = await ctx.sandbox.exec(
            f"find {q} \\( -name .git -o -name .tw -o -name node_modules -o -name .venv -o -name __pycache__ \\) "
            f"-prune -o -type f -print 2>/dev/null | sed 's|^\\./||' | sort | head -n 5000"
        )
        files = [ln for ln in r.stdout.splitlines() if ln]
    ign = await _gitignore(ctx)
    return [f for f in files if not ign.ignored(f)]


# ---------------------------------------------------------------- grep
class GrepParams(BaseModel):
    pattern: str = Field(min_length=1, description="正则表达式（Python / ERE 语法）")
    path: str = Field(default=".", description="搜索的目录或文件")
    glob: str | None = Field(default=None, description="只搜匹配此通配的文件，如 *.py")
    context: int = Field(default=0, ge=0, le=5, description="每处匹配前后各带几行上下文")
    max_matches: int = Field(default=MAX_MATCHES, ge=1, le=200, description="最多返回多少处匹配")


def _regex_hint(pattern: str, err: re.error) -> str:
    """正则错误 → 可操作的修正建议（04 §3.4）。"""
    tips = []
    if any(c in pattern for c in "()[]{}") and ("unbalanced" in str(err) or "missing" in str(err)):
        tips.append("括号要成对；字面量括号写成 \\( \\) \\[ \\]")
    if pattern.startswith(("*", "+", "?")) or "nothing to repeat" in str(err):
        tips.append("* + ? 前面要有字符；任意字符用 .*")
    tips.append(f"或把整个模式当字面量：{re.escape(pattern)}")
    return f"正则错误：{err}。建议：" + "；".join(tips)


def _with_context(rel: str, lines: list[str], hits: list[int], n: int) -> list[str]:
    """hits 为 0 基行号；输出 path:行:内容（匹配）与 path-行-内容（上下文），不相邻的块之间用 -- 分隔。"""
    out: list[str] = []
    last = -2
    hit_set = set(hits)
    for h in hits:
        lo, hi = max(0, h - n), min(len(lines) - 1, h + n)
        if out and lo > last + 1:
            out.append("--")
        for i in range(max(lo, last + 1), hi + 1):
            sep = ":" if i in hit_set else "-"
            out.append(f"{rel}{sep}{i + 1}{sep}{lines[i][:300]}")
        last = max(last, hi)
    return out


class Grep(BaseTool):
    name = "grep"
    Params = GrepParams
    refetchable = True

    async def run(self, params: GrepParams, ctx: ToolContext) -> ToolResult:
        try:
            rx = re.compile(params.pattern)
        except re.error as e:
            return ToolResult(ok=False, content=_regex_hint(params.pattern, e), error_code="bad_regex")
        cap = params.max_matches
        out: list[str] = []
        n_hits = 0
        try:
            root = _host_root(ctx, params.path)
            if root is not None:
                base = _host_root(ctx, ".") or root
                ign = await _gitignore(ctx)
                for f in _walk(root):
                    rel = _rel(f, base)
                    if not _glob_ok(rel, params.glob) or ign.ignored(rel):
                        continue
                    try:
                        blob = f.read_bytes()
                    except OSError:
                        continue
                    if b"\x00" in blob[:8000]:
                        continue
                    lines = _decode(blob).splitlines()
                    hits = [i for i, line in enumerate(lines) if rx.search(line)]
                    if not hits:
                        continue
                    hits = hits[: cap + 1 - n_hits]
                    n_hits += len(hits)
                    if params.context:
                        if out:
                            out.append("--")
                        out.extend(_with_context(rel, lines, hits[:cap], params.context))
                    else:
                        out.extend(f"{rel}:{i + 1}:{lines[i][:300]}" for i in hits)
                    if n_hits > cap:
                        break
            else:
                inc = f"--include={shlex.quote(params.glob)} " if params.glob else ""
                ctxflag = f"-C {params.context} " if params.context else ""
                limit = (cap + 1) * (2 * params.context + 2)
                r = await ctx.sandbox.exec(
                    f"grep -rnIE {ctxflag}{inc}--exclude-dir=.git --exclude-dir=.tw -e {shlex.quote(params.pattern)} "
                    f"-- {shlex.quote(params.path)} 2>/dev/null | sed 's|^\\./||' | head -n {limit}"
                )
                out = [ln[:400] for ln in r.stdout.splitlines() if ln]
                n_hits = sum(1 for ln in out if re.match(r"^[^:]+:\d+:", ln))
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="sandbox")
        more = n_hits > cap
        data: dict[str, Any] = {"count": min(n_hits, cap), "more": more}
        if not out:
            return ToolResult(ok=True, content="（没有匹配）", data=data)
        if more and not params.context:
            out = out[:cap]
        tail = f"\n…（超过 {cap} 处，只显示前 {cap} 处；缩小 path / glob）" if more else ""
        return ToolResult(ok=True, content="\n".join(out) + tail, data=data)
