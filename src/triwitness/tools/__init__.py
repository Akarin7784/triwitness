"""Agent 工具（spec 003）。"""

from __future__ import annotations

from triwitness.tools.base import BaseTool, GateOutcome, Tool, ToolContext, ToolRegistry, ToolResult
from triwitness.tools.files import EditFile, Grep, ListFiles, ReadFile, WriteFile
from triwitness.tools.shell import Bash, Finish, PowerShell, RunTests


def default_tools(*, shell: str = "bash") -> list[Tool]:
    """标准工具集；shell="powershell" 时以 powershell 替代 bash（工具列表随平台变化仅此一处）。"""
    sh: Tool = PowerShell() if shell == "powershell" else Bash()
    return [ReadFile(), WriteFile(), EditFile(), ListFiles(), Grep(), sh, RunTests(), Finish()]


__all__ = [
    "BaseTool",
    "GateOutcome",
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ToolResult",
    "default_tools",
]
