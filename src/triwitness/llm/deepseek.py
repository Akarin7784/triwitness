"""DeepSeekAdapter（spec 001 §6；OpenAI 兼容 Chat Completions）。

已用真实调用核对（2026-10-10，见 tests/fixtures/llm/deepseek/）：
- 思考开关 `thinking: {type: enabled|disabled}`，强度 `reasoning_effort: low|high|max`；
- 带 tools 时，历史中每条 assistant 消息的 reasoning_content 必须回传，否则 400；
- 用量字段：prompt_tokens = prompt_cache_hit_tokens + prompt_cache_miss_tokens，
  completion_tokens_details.reasoning_tokens 为推理 token（已含在 completion_tokens 里）。
"""

from __future__ import annotations

import logging
from typing import Any

from triwitness.core.models import Vendor
from triwitness.llm.types import Caps, LLMRequest, LLMResponse, Message, ToolCallSpec, Usage

log = logging.getLogger(__name__)

BASE_URL = "https://api.deepseek.com"
FLASH_FAMILY = ("deepseek-flash", "deepseek-v4.1-flash", "deepseek-v4-flash", "DeepSeek-V4.1-Flash")
_THINKING_DROP = ("temperature", "presence_penalty", "frequency_penalty")


class DeepSeekAdapter:
    vendor: Vendor = "deepseek"

    def capabilities(self, model: str) -> Caps:
        return Caps(
            vendor="deepseek",
            model=model,
            supports_thinking=True,
            supports_tools=True,
            context_window=1_048_576,
            max_output_tokens=393_216,
            reasoning_passback_with_tools=True,
        )

    # ------------------------------------------------------------ 请求

    def prepare_history(self, msgs: list[Message], has_tools: bool) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in msgs:
            d: dict[str, Any] = {"role": m.role, "content": m.content if m.content is not None else ""}
            if m.role == "assistant":
                if has_tools:
                    # spec 001 AC2：带 tools 时每条 assistant 都带 reasoning_content（没有就给空串）
                    d["reasoning_content"] = m.reasoning_content or ""
                if m.tool_calls:
                    d["tool_calls"] = [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": c.arguments},
                        }
                        for c in m.tool_calls
                    ]
            if m.role == "tool":
                d["tool_call_id"] = m.tool_call_id
            if m.name and m.role != "tool":
                d["name"] = m.name
            out.append(d)
        return out

    def build_request(self, model: str, req: LLMRequest) -> dict[str, Any]:
        has_tools = bool(req.tools)
        payload: dict[str, Any] = {
            "model": model,
            "messages": self.prepare_history(req.messages, has_tools),
            "thinking": {"type": "enabled" if req.thinking else "disabled"},
            "stream": False,
        }
        if req.thinking and req.effort:
            payload["reasoning_effort"] = req.effort
        if has_tools:
            payload["tools"] = req.tools
            payload["tool_choice"] = req.tool_choice
        if req.max_output_tokens:
            payload["max_tokens"] = req.max_output_tokens
        if req.temperature is not None:
            if req.thinking:
                log.debug("DeepSeek 思考模式不支持 temperature，已丢弃")
            else:
                payload["temperature"] = req.temperature
        for k in _THINKING_DROP:
            if req.thinking:
                payload.pop(k, None)
        return payload

    # ------------------------------------------------------------ 响应

    def normalize_usage(self, raw_usage: dict[str, Any]) -> Usage:
        prompt = int(raw_usage.get("prompt_tokens", 0))
        hit = raw_usage.get("prompt_cache_hit_tokens")
        miss = raw_usage.get("prompt_cache_miss_tokens")
        if hit is None and miss is None:
            hit = int((raw_usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0))
            miss = prompt - hit
        hit = int(hit or 0)
        miss = int(miss if miss is not None else prompt - hit)
        details = raw_usage.get("completion_tokens_details") or {}
        reasoning = details.get("reasoning_tokens")
        return Usage(
            input_tokens=hit + miss,
            cache_hit_tokens=hit,
            cache_miss_tokens=miss,
            output_tokens=int(raw_usage.get("completion_tokens", 0)),
            reasoning_tokens=int(reasoning) if reasoning is not None else None,
        )

    def parse_response(self, raw: dict[str, Any]) -> LLMResponse:
        choice = (raw.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        calls = [
            ToolCallSpec(
                id=c["id"],
                name=c["function"]["name"],
                arguments=c["function"].get("arguments") or "{}",
            )
            for c in (msg.get("tool_calls") or [])
        ]
        served = raw.get("model")
        degraded: list[str] = []
        if served and not any(f.lower() in served.lower() for f in FLASH_FAMILY):
            log.warning("served_model 漂移：%s 不属于 Flash 族", served)
            degraded.append(f"served_model_drift:{served}")
        return LLMResponse(
            message=Message(
                role="assistant",
                content=msg.get("content"),
                reasoning_content=msg.get("reasoning_content"),
                tool_calls=calls or None,
            ),
            usage=self.normalize_usage(raw.get("usage") or {}),
            served_model=served,
            finish_reason=choice.get("finish_reason"),
            raw=raw,
            degraded=degraded,
            vendor="deepseek",
        )
