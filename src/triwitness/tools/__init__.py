"""Agent 工具（spec 003）。"""

from __future__ import annotations

from triwitness.tools.base import BaseTool, GateOutcome, Tool, ToolContext, ToolRegistry, ToolResult
from triwitness.tools.files import EditFile, Grep, ListFiles, ReadFile, WriteFile
from triwitness.tools.repo_map import RepoMap
from triwitness.tools.shell import Bash, Finish, PowerShell, RunTests
from triwitness.tools.workspace import Git, Notes

ALL_TOOLS: dict[str, type[Tool]] = {
    t.name: t for t in (ReadFile, WriteFile, EditFile, ListFiles, Grep, Bash, RunTests, Finish, Notes, Git, RepoMap)
}  # type: ignore[misc]
W1_TOOLS = ["bash", "edit_file", "finish", "grep", "list_files", "read_file", "run_tests", "write_file"]


def default_tools(*, shell: str = "bash", names: list[str] | None = None) -> list[Tool]:
    """按 harness 配置的工具名建工具集（W2-15）；names=None 时为 W1 的 8 个核心工具。
    shell="powershell" 时以 powershell 替代 bash（工具列表随平台变化仅此一处）；finish 总是包含。"""
    wanted = list(dict.fromkeys([*(names or W1_TOOLS), "finish"]))
    unknown = [n for n in wanted if n not in ALL_TOOLS]
    if unknown:
        raise ValueError(f"未知工具：{', '.join(unknown)}；可用：{', '.join(sorted(ALL_TOOLS))}")
    out: list[Tool] = []
    for n in wanted:
        if n == "bash" and shell == "powershell":
            out.append(PowerShell())
        else:
            out.append(ALL_TOOLS[n]())
    return out


__all__ = [
    "ALL_TOOLS",
    "BaseTool",
    "GateOutcome",
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ToolResult",
    "default_tools",
]
