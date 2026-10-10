"""录制 / 冒烟用例（scripts/record_llm_fixture.py 与 tests/unit/llm 共用，保证请求逐字节一致）。

每个用例都很小：全部录一遍约 6 次调用，空闲价下花费远低于 ¥0.01。
"""

from __future__ import annotations

from triwitness.llm.types import LLMRequest, LLMResponse, Message

MODEL = "deepseek-flash"

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询某城市某天的天气。",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["city", "date"],
        },
    },
}

# 稳定前缀：约 2K token 的固定系统提示，用于验证缓存命中（DeepSeek 以 64 token 为单位缓存前缀）
_RULES = "\n".join(
    f"{i:03d}. 规则：回答要简短；不要编造；如需外部信息请调用工具；输出使用中文；不要输出多余解释。"
    for i in range(1, 121)
)
STABLE_SYSTEM = "你是 TriWitness 的测试助手。下面是固定的规则清单（用于缓存命中测试，请忽略其内容重复）：\n" + _RULES


def text_nonthinking() -> LLMRequest:
    return LLMRequest(
        role="executor",
        thinking=False,
        max_output_tokens=16,
        messages=[Message(role="user", content="只回答一个数字：1+1 等于几？")],
    )


def tool_single_nonthinking() -> LLMRequest:
    return LLMRequest(
        role="executor",
        thinking=False,
        max_output_tokens=128,
        tools=[WEATHER_TOOL],
        messages=[
            Message(role="system", content="今天是 2026-10-10。需要天气时必须调用 get_weather。"),
            Message(role="user", content="杭州明天天气怎么样？"),
        ],
    )


def tool_multiturn_thinking_1() -> LLMRequest:
    return LLMRequest(
        role="executor",
        thinking=True,
        effort="low",
        max_output_tokens=1024,
        tools=[WEATHER_TOOL],
        messages=[
            Message(
                role="system", content="今天是 2026-10-10。需要天气时必须调用 get_weather，拿到结果后用一句话回答。"
            ),
            Message(role="user", content="广州明天天气怎么样？"),
        ],
    )


def tool_multiturn_thinking_2(first: LLMResponse) -> LLMRequest:
    req = tool_multiturn_thinking_1()
    calls = first.message.tool_calls or []
    msgs = [*req.messages, first.message]
    msgs += [Message(role="tool", tool_call_id=c.id, content="多云，18~24°C") for c in calls]
    return req.model_copy(update={"messages": msgs})


def cache_prefix(question: str) -> LLMRequest:
    return LLMRequest(
        role="executor",
        thinking=False,
        max_output_tokens=16,
        messages=[Message(role="system", content=STABLE_SYSTEM), Message(role="user", content=question)],
    )


CACHE_Q1 = "只回答一个数字：2+3 等于几？"
CACHE_Q2 = "只回答一个数字：4+5 等于几？"
