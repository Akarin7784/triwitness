"""厂商无关的请求 / 响应结构（spec 001 §5）。Usage 复用 core（ADR-0001 #5）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from triwitness.core.models import Role, Usage, Vendor

__all__ = ["Caps", "LLMRequest", "LLMResponse", "Message", "ToolCallSpec", "Usage"]


class ToolCallSpec(BaseModel):
    """模型发出的一次工具调用。arguments 保留原始 JSON 字符串（逐字节回传，利于缓存命中）。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    arguments: str = "{}"


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    reasoning_content: str | None = None  # 原样保存，由适配器决定是否回传
    tool_calls: list[ToolCallSpec] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class LLMRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role
    messages: list[Message]
    tools: list[dict[str, Any]] | None = None  # OpenAI function 格式；调用方应按名称排序保证前缀稳定
    tool_choice: Literal["auto", "none", "required"] | dict[str, Any] = "auto"
    thinking: bool = True
    effort: Literal["low", "high", "max"] | None = None
    temperature: float | None = None  # 思考模式下会被丢弃
    max_output_tokens: int | None = None
    response_schema: dict[str, Any] | None = None


class Caps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor: Vendor
    model: str
    supports_thinking: bool
    supports_tools: bool
    context_window: int
    max_output_tokens: int
    reasoning_passback_with_tools: bool  # 带 tools 时必须回传历史 reasoning_content


class LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Message
    usage: Usage
    served_model: str | None
    finish_reason: str | None
    raw: dict[str, Any] = Field(repr=False)  # 原始响应（落盘到产物，不进上下文）
    degraded: list[str] = Field(default_factory=list)
    # 以下由 LLMClient 填写
    model: str = ""
    vendor: Vendor = "deepseek"
    cost_cny: float = 0.0
    peak: bool | None = None
    latency_ms: int = 0
    source: Literal["live", "replay", "fake"] = "live"
    request_key: str | None = None
