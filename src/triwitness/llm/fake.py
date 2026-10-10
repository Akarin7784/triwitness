"""FakeAdapter：按脚本返回响应，证明 ModelAdapter 协议可插拔（单测 / AgentLoop TDD 用）。"""

from __future__ import annotations

from typing import Any

from triwitness.core.models import Vendor
from triwitness.llm.types import Caps, LLMRequest, LLMResponse, Message, Usage


class FakeAdapter:
    vendor: Vendor = "deepseek"  # 伪装成单厂商；协议层不关心

    def __init__(self, script: list[Message], usage: Usage | None = None) -> None:
        self.script = list(script)
        self.usage = usage or Usage(input_tokens=100, cache_hit_tokens=90, cache_miss_tokens=10, output_tokens=20)
        self.requests: list[dict[str, Any]] = []

    def capabilities(self, model: str) -> Caps:
        return Caps(
            vendor="deepseek",
            model=model,
            supports_thinking=True,
            supports_tools=True,
            context_window=1_000_000,
            max_output_tokens=8192,
            reasoning_passback_with_tools=False,
        )

    def prepare_history(self, msgs: list[Message], has_tools: bool) -> list[dict[str, Any]]:
        return [m.model_dump(exclude_none=True) for m in msgs]

    def build_request(self, model: str, req: LLMRequest) -> dict[str, Any]:
        return {"model": model, "messages": self.prepare_history(req.messages, bool(req.tools))}

    def normalize_usage(self, raw_usage: dict[str, Any]) -> Usage:
        return Usage.model_validate(raw_usage)

    def parse_response(self, raw: dict[str, Any]) -> LLMResponse:
        return LLMResponse(
            message=Message.model_validate(raw["message"]),
            usage=self.normalize_usage(raw["usage"]),
            served_model=raw.get("model"),
            finish_reason="stop",
            raw=raw,
            source="fake",
        )

    def next_raw(self, payload: dict[str, Any]) -> dict[str, Any]:
        """FakeTransport 调用：记录请求，弹出下一条脚本消息。"""
        self.requests.append(payload)
        if not self.script:
            raise RuntimeError("FakeAdapter 脚本已用完")
        msg = self.script.pop(0)
        return {"model": payload["model"], "message": msg.model_dump(), "usage": self.usage.model_dump()}
