"""角色 Loop 的公共部分：只读工具子集、独立预算守卫、终止工具结果的兜底解析。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from triwitness.core.models import Budget, Role
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.harness.config import HarnessConfig
from triwitness.harness.loop import AgentLoop, LoopOutcome, RouterLike, build_system_prompt
from triwitness.prompts import load_prompt
from triwitness.roles.contracts import SubmitTool, extract_json, parse_model
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ALL_TOOLS, ToolRegistry
from triwitness.tools.base import Gate, Tool

READ_ONLY_TOOLS = ("git", "grep", "list_files", "read_file", "repo_map")


def read_only_registry(submit: SubmitTool[Any], *, gate: Gate | None = None) -> ToolRegistry:
    tools: list[Tool] = [ALL_TOOLS[n]() for n in READ_ONLY_TOOLS]  # type: ignore[call-arg]
    tools.append(submit)  # type: ignore[arg-type]
    return ToolRegistry(tools, gate=gate)


def role_loop(
    *,
    role: Role,
    prompt: str,
    router: RouterLike,
    registry: ToolRegistry,
    rec: TrajectoryRecorder,
    cfg: HarnessConfig,
    budget: Budget,
    max_turns: int,
    mode: Literal["background", "eval"],
    category: str,
    agents_md: str | None,
    intro: str,
    effort: Literal["low", "high", "max"] | None = None,
    executor_vendor: str | None = None,
) -> AgentLoop:
    """角色自己的 AgentLoop：独立上下文、独立回合上限（预算守卫只限制本角色；成本照常经账本记到任务上）。"""
    role_prompt = load_prompt(prompt).text
    guard = TaskBudgetGuard(budget=budget.model_copy(update={"max_turns": max_turns}))
    return AgentLoop(router, registry, budget=guard.budget, emitter=rec, role=role, config=cfg, mode=mode,
                     guard=guard, category=category, task_intro=intro, effort=effort,
                     executor_vendor=executor_vendor,
                     system_prompt=build_system_prompt(role_prompt, agents_md=agents_md, tool_names=registry.names,
                                                       agents_md_max_chars=8000 if agents_md else 0))  # fmt: skip


def executor_vendor(router: Any) -> str | None:
    """Executor 路由的厂商（真实 Router 才有 route_for）；FakeRouter 等返回 None。"""
    route_for = getattr(router, "route_for", None)
    if route_for is None:
        return None
    try:
        from triwitness.llm.router import vendor_of

        return vendor_of(route_for("executor").model)
    except Exception:  # 没配 executor 路由：不加约束（Router 自己会在调用时报错）
        return None


def submission_or_fallback(
    loop: AgentLoop, outcome: LoopOutcome, model: type[BaseModel], check: Any = None
) -> tuple[Any | None, str]:
    """终止工具的提交；没有（卡住 / 上限）就从最后一条 assistant 文本里抽 JSON 再校验一次（spec 010 §5）。"""
    if outcome.submission is not None:
        v, err = parse_model(model, outcome.submission, check)
        return v, "tool_call" if v is not None else err
    last = next((m for m in reversed(loop.messages) if m.role == "assistant" and m.content), None)
    obj = extract_json(last.content if last else None)
    if obj is None:
        return None, f"没有提交（{outcome.status}：{outcome.reason or ''}）"
    v, err = parse_model(model, obj, check)
    return v, "content_json" if v is not None else err


def last_model(rec: TrajectoryRecorder, role: str) -> str:
    """该角色最近一次模型调用的模型 ID（Plan.model / 证据包 review_model 用）。"""
    for ev in reversed(rec.events):
        if ev.kind == "model_call" and ev.role == role:
            return str(ev.payload.get("model") or "?")
    return "?"


__all__ = [
    "READ_ONLY_TOOLS",
    "executor_vendor",
    "last_model",
    "read_only_registry",
    "role_loop",
    "submission_or_fallback",
]
