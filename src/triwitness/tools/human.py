"""ask_human：向人提问（04 §3.4 / §3.7，W4-10）。

工具本身只校验参数并转给编排器放在 `ctx.state["ask_human"]` 的回调；回调决定怎么问：
- blocking=true：发 approval_requested（tool=AskHuman）等人回答；没有审批通道 → NeedsHuman（任务暂停，可续跑）；
- blocking=false：只记下问题、不等待，模型按最佳判断继续并在 finish 里写明假设；
- 评测模式禁止人工介入：不问，直接让模型按最佳判断继续（写审计事件）。
没有回调（单独用 AgentLoop / 旧 harness）时返回说明，不报错。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

from triwitness.tools.base import BaseTool, ToolContext, ToolResult

AskHandler = Callable[[str, bool, list[str], str], Awaitable[str]]
STATE_KEY = "ask_human"
QUESTIONS_KEY = "human_questions"
NO_CHANNEL = "这次运行没有可以提问的人。按你的最佳判断继续，并在 finish 的 open_risks 里写明假设。"


class AskHumanParams(BaseModel):
    question: str = Field(min_length=1, max_length=2000, description="要问的问题：一句话说清楚需要人决定什么")
    blocking: bool = Field(
        default=True, description="true = 等人回答再继续；false = 记下问题、按你的最佳判断继续（在 finish 写明假设）"
    )
    options: list[str] = Field(default_factory=list, max_length=6, description="可选：候选答案（每个 ≤ 200 字）")
    context: str = Field(default="", max_length=2000, description="可选：为什么需要问、已经查到了什么")


class AskHuman(BaseTool):
    name = "ask_human"
    Params = AskHumanParams
    side_effects = "external"  # 会打扰人：不和其他工具并发

    async def run(self, params: AskHumanParams, ctx: ToolContext) -> ToolResult:
        options = [o.strip()[:200] for o in params.options if o.strip()]
        asked: list[dict[str, Any]] = ctx.state.setdefault(QUESTIONS_KEY, [])
        asked.append({"question": params.question, "blocking": params.blocking, "options": options})
        handler: AskHandler | None = ctx.state.get(STATE_KEY)
        if handler is None:
            return ToolResult(ok=False, content=NO_CHANNEL, error_code="no_channel")
        answer = await handler(params.question, params.blocking, options, params.context)
        asked[-1]["answer"] = answer
        return ToolResult(ok=True, content=answer, data={"blocking": params.blocking, "answered": params.blocking})


__all__ = ["QUESTIONS_KEY", "STATE_KEY", "AskHandler", "AskHuman", "AskHumanParams"]
