import json

import pytest

from triwitness.llm import cases
from triwitness.llm.deepseek import DeepSeekAdapter
from triwitness.llm.types import LLMRequest, Message, ToolCallSpec

from .helpers import FIXTURES

A = DeepSeekAdapter()


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_ac2_reasoning_passed_back_on_every_assistant_with_tools() -> None:
    msgs = [
        Message(role="user", content="q"),
        Message(role="assistant", content="", reasoning_content="r1", tool_calls=[ToolCallSpec(id="c1", name="f")]),
        Message(role="tool", tool_call_id="c1", content="ok"),
        Message(role="assistant", content="done"),  # 没有推理内容的一轮也要带字段
        Message(role="user", content="q2"),
    ]
    payload = A.build_request("deepseek-flash", LLMRequest(role="executor", messages=msgs, tools=[cases.WEATHER_TOOL]))
    assistants = [m for m in payload["messages"] if m["role"] == "assistant"]
    assert len(assistants) == 2 and all("reasoning_content" in m for m in assistants)
    assert assistants[0]["reasoning_content"] == "r1"
    assert payload["messages"][2]["tool_call_id"] == "c1"


def test_reasoning_omitted_without_tools() -> None:
    msgs = [Message(role="assistant", content="a", reasoning_content="r")]
    payload = A.build_request("deepseek-flash", LLMRequest(role="executor", messages=msgs))
    assert "reasoning_content" not in payload["messages"][0]
    assert "tools" not in payload and "tool_choice" not in payload


def test_thinking_mode_drops_temperature_and_sets_effort() -> None:
    req = LLMRequest(role="executor", messages=[], thinking=True, effort="max", temperature=0.2)
    p = A.build_request("deepseek-flash", req)
    assert p["thinking"] == {"type": "enabled"} and p["reasoning_effort"] == "max" and "temperature" not in p


def test_non_thinking_keeps_temperature_no_effort() -> None:
    req = LLMRequest(role="executor", messages=[], thinking=False, effort="high", temperature=0.2)
    p = A.build_request("deepseek-flash", req)
    assert p["thinking"] == {"type": "disabled"} and p["temperature"] == 0.2 and "reasoning_effort" not in p


@pytest.mark.parametrize(
    "name",
    [
        "text_nonthinking",
        "tool_single_nonthinking",
        "tool_multiturn_thinking_1",
        "tool_multiturn_thinking_2",
        "cache_prefix_1",
        "cache_prefix_2",
    ],
)
def test_usage_normalization_from_recordings(name: str) -> None:
    raw = _fixture(name)["response"]
    u = A.normalize_usage(raw["usage"])
    assert u.input_tokens == raw["usage"]["prompt_tokens"]
    assert u.cache_hit_tokens == raw["usage"]["prompt_cache_hit_tokens"]
    assert u.cache_miss_tokens == raw["usage"]["prompt_cache_miss_tokens"]
    assert u.output_tokens == raw["usage"]["completion_tokens"]


def test_usage_fallback_to_openai_cached_tokens() -> None:
    u = A.normalize_usage(
        {"prompt_tokens": 100, "completion_tokens": 5, "prompt_tokens_details": {"cached_tokens": 64}}
    )
    assert (u.cache_hit_tokens, u.cache_miss_tokens) == (64, 36)


def test_parse_tool_call_and_reasoning() -> None:
    r = A.parse_response(_fixture("tool_multiturn_thinking_1")["response"])
    assert r.message.tool_calls and r.message.tool_calls[0].name == "get_weather"
    assert r.message.reasoning_content
    assert json.loads(r.message.tool_calls[0].arguments)["city"] == "广州"
    assert r.usage.reasoning_tokens and r.usage.reasoning_tokens > 0
    assert r.degraded == []


def test_served_model_drift_flagged() -> None:
    raw = _fixture("text_nonthinking")["response"] | {"model": "deepseek-v4-pro"}
    assert A.parse_response(raw).degraded == ["served_model_drift:deepseek-v4-pro"]
