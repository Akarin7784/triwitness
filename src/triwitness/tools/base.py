"""Tool 协议与 ToolRegistry（spec 003 §4，ADR-0001 #4，W1-18）。"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

from triwitness.llm.types import ToolCallSpec
from triwitness.sandbox.base import Sandbox

DESCRIPTIONS = Path(__file__).parent / "descriptions"
SideEffects = Literal["none", "workspace", "external"]


@dataclass
class ToolContext:
    sandbox: Sandbox
    task_id: str = "t_test"
    run_id: str = "r_test"
    step_index: int = 0
    test_command: str | None = None  # run_tests 使用的命令（任务配置）
    tw_dir: str = "/workspace/.tw"  # 沙箱内 .tw/ 位置（none 后端为 TW_HOME/runs/<run_id>/.tw）
    state: dict[str, Any] = field(default_factory=dict)  # 工具间共享：last_run_tests 等


class ToolResult(BaseModel):
    ok: bool
    content: str  # 给模型看的文本（已截断）
    data: dict[str, Any] | None = None  # 结构化结果（写入轨迹，不进上下文）
    error_code: str | None = None
    exit_code: int | None = None
    truncated: bool = False


@runtime_checkable
class Tool(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def Params(self) -> type[BaseModel]: ...
    @property
    def side_effects(self) -> SideEffects: ...
    @property
    def refetchable(self) -> bool: ...
    @property
    def terminal(self) -> bool: ...

    async def run(self, params: Any, ctx: ToolContext) -> ToolResult: ...


@lru_cache(maxsize=64)
def load_description(name: str) -> str:
    p = DESCRIPTIONS / f"{name}.md"
    return p.read_text(encoding="utf-8").strip()


class BaseTool:
    """便捷基类：description 从 tools/descriptions/<name>.md 读取。"""

    name: str
    Params: type[BaseModel]
    side_effects: SideEffects = "none"
    refetchable: bool = False
    terminal: bool = False

    @property
    def description(self) -> str:
        return load_description(self.name)

    async def run(self, params: Any, ctx: ToolContext) -> ToolResult:  # pragma: no cover - 子类实现
        raise NotImplementedError


def _type_name(schema: dict[str, Any]) -> str:
    if "type" in schema:
        return str(schema["type"])
    if "anyOf" in schema:
        return " | ".join(_type_name(s) for s in schema["anyOf"])
    if "enum" in schema:
        return "枚举 " + " / ".join(map(str, schema["enum"]))
    return "对象"


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """去掉 pydantic 的 title 噪声，保证稳定、精简。"""
    if isinstance(schema, dict):
        return {k: _clean_schema(v) for k, v in schema.items() if k != "title"}  # type: ignore[misc]
    if isinstance(schema, list):
        return [_clean_schema(x) for x in schema]  # type: ignore[return-value]
    return schema


# 权限闸门：执行前判定。返回 None = 放行；返回 ToolResult = 拒绝（由闸门写事件）
Gate = Callable[[Tool, BaseModel, ToolContext, ToolCallSpec], Awaitable["GateOutcome"]]


@dataclass
class GateOutcome:
    allowed: bool
    result: ToolResult | None = None  # 被拒绝时返回给模型的结果
    permission: Literal["allow", "deny", "ask"] | None = None
    rule: str | None = None


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None, *, gate: Gate | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self.gate = gate
        for t in tools or []:
            self.register(t)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具重名：{tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    @property
    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        """OpenAI function 格式；按名称排序，保证稳定前缀（AC2）。"""
        out = []
        for name in self.names:
            t = self._tools[name]
            params = _clean_schema(t.Params.model_json_schema())
            params.setdefault("properties", {})
            out.append({"type": "function", "function": {"name": name, "description": t.description,
                                                          "parameters": params}})  # fmt: skip
        return out

    def parse(self, tool: Tool, arguments: str) -> BaseModel | ToolResult:
        """参数错误 → ok=False，content 含字段名与期望类型（AC3）。"""
        try:
            raw = json.loads(arguments or "{}")
        except json.JSONDecodeError as e:
            return ToolResult(
                ok=False, content=f"参数不是合法 JSON：{e.msg}（第 {e.pos} 个字符）", error_code="bad_args"
            )
        if not isinstance(raw, dict):
            return ToolResult(ok=False, content="参数必须是 JSON 对象", error_code="bad_args")
        try:
            return tool.Params.model_validate(raw)
        except ValidationError as e:
            props = tool.Params.model_json_schema().get("properties", {})
            lines = []
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"]) or "(整体)"
                top = str(err["loc"][0]) if err["loc"] else ""
                expect = _type_name(props[top]) if top in props else "?"
                lines.append(f"- {loc}：{err['msg']}（期望类型：{expect}）")
            return ToolResult(ok=False, content=f"{tool.name} 参数错误：\n" + "\n".join(lines), error_code="bad_args")

    async def dispatch(self, call: ToolCallSpec, ctx: ToolContext) -> tuple[ToolResult, GateOutcome | None]:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(ok=False, content=f"没有工具 {call.name}；可用：{', '.join(self.names)}",
                              error_code="unknown_tool"), None  # fmt: skip
        parsed = self.parse(tool, call.arguments)
        if isinstance(parsed, ToolResult):
            return parsed, None
        outcome: GateOutcome | None = None
        if self.gate is not None:
            outcome = await self.gate(tool, parsed, ctx, call)
            if not outcome.allowed:
                assert outcome.result is not None
                return outcome.result, outcome
        try:
            return await tool.run(parsed, ctx), outcome
        except Exception as e:  # 工具内部异常不终止循环（spec 003 §5.5）
            return ToolResult(ok=False, content=f"{call.name} 内部错误：{type(e).__name__}: {e}",
                              error_code="internal"), outcome  # fmt: skip
