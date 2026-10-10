"""repo_map 工具（04 §3.4，W2-08）：Python 符号图 + PageRank 排序的仓库摘要，给模型一张“先看哪里”的地图。

v0 只做 Python，用标准库 ast（不引入 tree-sitter 依赖；多语言留给后续，接口不变）：
1. 每个 .py 文件抽取定义（类 / 函数 / 方法签名）与引用到的名字；
2. 文件 A 引用了文件 B 定义的名字 → 边 A→B（权重 = 引用次数）；
3. 带个性化向量的 PageRank（focus_paths 与 Issue 里出现的名字加权），按分数从高到低输出签名，直到 max_tokens。
输出确定（同一仓库、同参数逐字节相同），可作为消融开关（configs/harness/repo-map.yaml）。
"""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from triwitness.core.errors import SandboxError
from triwitness.tools.base import BaseTool, ToolContext, ToolResult
from triwitness.tools.files import collect_files

MAX_FILES = 400
MAX_FILE_BYTES = 300_000
CHARS_PER_TOKEN = 3.0
_IGNORE_NAMES = frozenset(
    ["self", "cls", "None", "True", "False", "print", "len", "str", "int", "dict", "list", "set", "tuple", "object",
     "super", "isinstance", "range", "Exception", "__init__"]
)  # fmt: skip


@dataclass
class FileSymbols:
    path: str
    defs: list[tuple[str, str]] = field(default_factory=list)  # (名字, 签名行)
    refs: Counter[str] = field(default_factory=Counter)


def _sig(node: ast.FunctionDef | ast.AsyncFunctionDef, indent: str) -> str:
    a = node.args
    names = [x.arg for x in [*a.posonlyargs, *a.args]]
    if a.vararg:
        names.append("*" + a.vararg.arg)
    names += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        names.append("**" + a.kwarg.arg)
    kw = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{indent}{kw} {node.name}({', '.join(names)})"


def parse_symbols(path: str, source: str) -> FileSymbols:
    fs = FileSymbols(path)
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return fs
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            fs.defs.append((node.name, f"class {node.name}({bases}):" if bases else f"class {node.name}:"))
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef | ast.AsyncFunctionDef) and not (
                    sub.name.startswith("__") and sub.name != "__init__"
                ):
                    fs.defs.append((sub.name, _sig(sub, "    ")))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            fs.defs.append((node.name, _sig(node, "")))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    fs.defs.append((t.id, f"{t.id} = …"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            fs.refs[node.id] += 1
        elif isinstance(node, ast.Attribute):
            fs.refs[node.attr] += 1
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                fs.refs[a.name] += 1
    return fs


def pagerank(nodes: list[str], edges: dict[str, Counter[str]], personal: dict[str, float],
             *, damping: float = 0.85, iters: int = 50) -> dict[str, float]:  # fmt: skip
    if not nodes:
        return {}
    total_p = sum(personal.values()) or 1.0
    p = {n: personal.get(n, 0.0) / total_p for n in nodes} if personal else {n: 1 / len(nodes) for n in nodes}
    rank = dict(p)
    out_w = {n: sum(edges.get(n, Counter()).values()) for n in nodes}
    for _ in range(iters):
        nxt = {n: (1 - damping) * p[n] for n in nodes}
        dangling = sum(rank[n] for n in nodes if out_w[n] == 0)
        for n in nodes:
            if out_w[n]:
                for m, w in edges[n].items():
                    nxt[m] += damping * rank[n] * w / out_w[n]
        for n in nodes:
            nxt[n] += damping * dangling * p[n]
        rank = nxt
    return rank


def build_map(files: list[FileSymbols], *, focus: list[str] | None = None, mentions: set[str] | None = None,
              max_tokens: int = 2000) -> str:  # fmt: skip
    defined: dict[str, set[str]] = defaultdict(set)
    for f in files:
        for name, _ in f.defs:
            if len(name) >= 3 and name not in _IGNORE_NAMES:
                defined[name].add(f.path)
    edges: dict[str, Counter[str]] = defaultdict(Counter)
    for f in files:
        for name, cnt in f.refs.items():
            for target in defined.get(name, ()):
                if target != f.path:
                    edges[f.path][target] += cnt
    nodes = sorted(f.path for f in files)
    personal: dict[str, float] = {}
    for f in files:
        w = 1.0
        if focus and any(f.path == x or f.path.startswith(x.rstrip("/") + "/") for x in focus):
            w += 10.0
        if mentions and any(name in mentions for name, _ in f.defs):
            w += 5.0
        personal[f.path] = w
    rank = pagerank(nodes, edges, personal)
    by_path = {f.path: f for f in files}
    budget = int(max_tokens * CHARS_PER_TOKEN)
    out: list[str] = []
    used = 0
    for path in sorted(nodes, key=lambda n: (-rank[n], n)):
        f = by_path[path]
        if not f.defs:
            continue
        block = [f"{path}:"] + [f"  {sig}" for _, sig in f.defs]
        text = "\n".join(block)
        if used + len(text) + 1 > budget:
            room = budget - used - len(path) - 8
            if room > 40:  # 放得下文件名 + 前几个签名就放，剩下的省略
                keep, n = [f"{path}:"], len(path) + 1
                for line in block[1:]:
                    if n + len(line) + 1 > room:
                        break
                    keep.append(line)
                    n += len(line) + 1
                out.append("\n".join([*keep, "  …"]))
            break
        out.append(text)
        used += len(text) + 1
    return "\n".join(out)


class RepoMapParams(BaseModel):
    focus_paths: list[str] = Field(default_factory=list, description="优先展示的文件或目录")
    mentions: list[str] = Field(default_factory=list, description="Issue 里提到的函数 / 类名，相关文件优先")
    max_tokens: int = Field(default=2000, ge=200, le=8000, description="摘要长度上限（token）")


class RepoMap(BaseTool):
    name = "repo_map"
    Params = RepoMapParams
    refetchable = True

    async def run(self, params: RepoMapParams, ctx: ToolContext) -> ToolResult:
        try:
            paths = [p for p in await collect_files(ctx) if p.endswith(".py")][:MAX_FILES]
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="sandbox")
        files: list[FileSymbols] = []
        for p in paths:
            try:
                data = await ctx.sandbox.read_file(p)
            except SandboxError:
                continue
            if len(data) <= MAX_FILE_BYTES:
                files.append(parse_symbols(p, data.decode("utf-8", "replace")))
        text = build_map(files, focus=params.focus_paths, mentions=set(params.mentions), max_tokens=params.max_tokens)
        if not text:
            return ToolResult(ok=True, content="（没有可解析的 Python 文件）", data={"files": 0})
        return ToolResult(ok=True, content=text, data={"files": len(files), "chars": len(text)})


__all__ = ["RepoMap", "build_map", "pagerank", "parse_symbols"]
