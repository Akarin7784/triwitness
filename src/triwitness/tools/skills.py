"""load_skill 工具（spec 013 §5.3，04 §3.4）：渐进加载已合入的 Skill 正文（上下文里平时只有 name + description）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from triwitness.tools.base import BaseTool, ToolContext, ToolResult

if TYPE_CHECKING:
    from triwitness.memory.context import MemoryContext


class LoadSkillParams(BaseModel):
    name: str = Field(min_length=1, max_length=64, description="技能名（见系统提示里的“可用技能”）")


class LoadSkill(BaseTool):
    name = "load_skill"
    Params = LoadSkillParams
    refetchable = True  # 可随时重新读取：上下文清理时可以换成占位符

    def __init__(self, memory: MemoryContext) -> None:
        self.memory = memory

    async def run(self, params: LoadSkillParams, ctx: ToolContext) -> ToolResult:
        from triwitness.memory.skills import SkillError

        try:
            sk = self.memory.load(params.name)
        except SkillError as e:
            return ToolResult(ok=False, content=str(e), error_code="not_found")
        head = f"# 技能 {sk.name}（v{sk.version}）\n{sk.description}\n\n"
        return ToolResult(ok=True, content=head + sk.body, data={"skill": sk.name, "version": sk.version})
