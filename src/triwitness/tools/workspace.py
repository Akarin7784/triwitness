"""notes 与 git 工具（04 §3.4，W2-07）。

- notes：读写 `.tw/NOTES.md`（工作区外、不进 diff），跨上下文窗口的外部记忆；压缩后由 ContextManager 重新注入。
- git：只读。diff / status 走 Sandbox.diff（所有后端都有，镜像里不需要 git）；log / show 在沙箱里执行 git，
  没有 git 时返回可操作的提示。提交与推送由编排器做，不给 Agent。
"""

from __future__ import annotations

import re
import shlex
from typing import Literal

from pydantic import BaseModel, Field

from triwitness.core.errors import SandboxError
from triwitness.tools.base import BaseTool, ToolContext, ToolResult

NOTES_FILE = "NOTES.md"
NOTES_MAX_CHARS = 20_000


def notes_path(ctx: ToolContext) -> str:
    return f"{ctx.tw_dir.rstrip('/')}/{NOTES_FILE}"


async def read_notes(ctx: ToolContext) -> str:
    try:
        return (await ctx.sandbox.read_file(notes_path(ctx))).decode("utf-8", "replace")
    except SandboxError:
        return ""


async def write_notes(ctx: ToolContext, text: str) -> None:
    await ctx.sandbox.write_file(notes_path(ctx), text.encode("utf-8"))


def replace_section(doc: str, section: str, text: str) -> str:
    """把 `## section` 这一节的正文换成 text；没有这一节就追加到末尾。"""
    title = f"## {section.strip().lstrip('#').strip()}"
    lines = doc.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip() == title), None)
    block = [title, *text.rstrip().splitlines()]
    if start is None:
        return (doc.rstrip() + "\n\n" if doc.strip() else "") + "\n".join(block) + "\n"
    end = next((j for j in range(start + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
    out = [*lines[:start], *block, *([""] if end < len(lines) else []), *lines[end:]]
    return "\n".join(out).rstrip() + "\n"


class NotesParams(BaseModel):
    op: Literal["read", "append", "replace_section"] = Field(
        description="read 读全文；append 追加；replace_section 改写一节"
    )
    section: str | None = Field(default=None, description="replace_section 的二级标题，如 计划 / 失败尝试")
    text: str | None = Field(default=None, description="append / replace_section 的内容（Markdown）")


class Notes(BaseTool):
    name = "notes"
    Params = NotesParams
    refetchable = True  # 可随时 read 重新取回

    async def run(self, params: NotesParams, ctx: ToolContext) -> ToolResult:
        doc = await read_notes(ctx)
        if params.op == "read":
            return ToolResult(ok=True, content=doc or "（NOTES.md 还是空的）", data={"chars": len(doc)})
        if not params.text:
            return ToolResult(ok=False, content=f"op={params.op} 需要 text", error_code="bad_args")
        if params.op == "append":
            new = (doc.rstrip() + "\n\n" if doc.strip() else "") + params.text.rstrip() + "\n"
        else:
            if not params.section:
                return ToolResult(ok=False, content="replace_section 需要 section（二级标题）", error_code="bad_args")
            new = replace_section(doc, params.section, params.text)
        if len(new) > NOTES_MAX_CHARS:
            msg = f"NOTES.md 会超过 {NOTES_MAX_CHARS} 字符；用 replace_section 精简旧内容"
            return ToolResult(ok=False, content=msg, error_code="too_long")
        try:
            await write_notes(ctx, new)
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="sandbox")
        return ToolResult(ok=True, content=f"已更新 NOTES.md（{len(new)} 字符）", data={"chars": len(new)})


# ---------------------------------------------------------------- git（只读）
_REV = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/~^@{}-]{0,99}$")
_DIFF_HEAD = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.M)


class GitParams(BaseModel):
    op: Literal["diff", "status", "log", "show"] = Field(
        description="diff / status：相对任务开始时的改动；log / show：仓库历史"
    )
    path: str | None = Field(default=None, description="只看这个文件或目录")
    rev: str | None = Field(default=None, description="show 的提交，如 HEAD~1")
    n: int = Field(default=10, ge=1, le=50, description="log 条数")


def _split(diff: str) -> list[tuple[str, str]]:
    starts = [m.start() for m in _DIFF_HEAD.finditer(diff)]
    out = []
    for i, st in enumerate(starts):
        chunk = diff[st : starts[i + 1] if i + 1 < len(starts) else len(diff)]
        m = _DIFF_HEAD.match(chunk)
        assert m is not None
        out.append((m.group(2), chunk))
    return out


def _under(path: str, prefix: str | None) -> bool:
    if not prefix or prefix in (".", "./"):
        return True
    p = prefix.strip("/").removeprefix("./")
    return path == p or path.startswith(p + "/")


class Git(BaseTool):
    name = "git"
    Params = GitParams
    refetchable = True

    async def run(self, params: GitParams, ctx: ToolContext) -> ToolResult:
        if params.op in ("diff", "status"):
            try:
                diff = await ctx.sandbox.diff("base")
            except (SandboxError, NotImplementedError) as e:
                return ToolResult(ok=False, content=f"取 diff 失败：{e}", error_code="sandbox")
            files = [(p, c) for p, c in _split(diff) if _under(p, params.path)]
            if params.op == "diff":
                body = "".join(c for _, c in files)
                return ToolResult(ok=True, content=body or "（没有改动）", data={"files": len(files)})
            rows = []
            for p, c in files:
                head = c.split("\n@@", 1)[0]
                kind = "A" if "\nnew file mode" in head or "--- /dev/null" in head else (
                    "D" if "\ndeleted file mode" in head or "+++ /dev/null" in head else "M")  # fmt: skip
                rows.append(f"{kind} {p}")
            return ToolResult(ok=True, content="\n".join(rows) or "（没有改动）", data={"files": len(rows)})
        if params.path and params.path.startswith("-"):
            return ToolResult(ok=False, content="path 不能以 - 开头", error_code="bad_args")
        if params.op == "log":
            cmd = f"git --no-pager log --oneline --no-decorate -n {params.n}"
            if params.path:
                cmd += f" -- {shlex.quote(params.path)}"
        else:
            rev = params.rev or "HEAD"
            if not _REV.match(rev):
                msg = f"rev 不合法：{rev}（例：HEAD、HEAD~1、提交哈希）"
                return ToolResult(ok=False, content=msg, error_code="bad_args")
            cmd = f"git --no-pager show --stat --patch --no-color {shlex.quote(rev)}"
            if params.path:
                cmd += f" -- {shlex.quote(params.path)}"
        try:
            r = await ctx.sandbox.exec(cmd, timeout_s=30)
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="sandbox")
        if r.exit_code != 0:
            err = (r.stderr or r.stdout).strip()
            if r.exit_code == 127 or "not a git repository" in err or "command not found" in err:
                return ToolResult(ok=False, content="这个沙箱里没有 git 历史；看改动请用 op=diff 或 op=status",
                                  error_code="no_git", exit_code=r.exit_code)  # fmt: skip
            return ToolResult(ok=False, content=err[:2000] or f"git 退出码 {r.exit_code}", error_code="git",
                              exit_code=r.exit_code)  # fmt: skip
        return ToolResult(ok=True, content=r.stdout or "（空）", exit_code=0)


__all__ = ["Git", "Notes", "notes_path", "read_notes", "replace_section", "write_notes"]
