"""流式输出（UI-20）：SSE 解析 / 拼装、HttpTransport.post_stream、回放命中时切片送出、缓存 key 不变。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from triwitness.core.errors import LLMUnavailable
from triwitness.llm import cases
from triwitness.llm.deepseek import DeepSeekAdapter
from triwitness.llm.http import HttpTransport
from triwitness.llm.replay import request_key
from triwitness.llm.router import THINKING_LEVELS, executor_override
from triwitness.llm.stream import assemble_chunks, parse_sse_lines, split_text, stream_payload, streaming

from .helpers import CannedTransport, client_with, replay_client

SSE = Path(__file__).resolve().parents[2] / "fixtures" / "llm" / "deepseek-stream" / "tool_call_thinking.sse"


def _chunks() -> list[dict[str, Any]]:
    return list(parse_sse_lines(SSE.read_text(encoding="utf-8").splitlines()))


def test_sse_assembles_to_non_stream_shape() -> None:
    got: list[tuple[str, str]] = []
    raw = assemble_chunks(_chunks(), lambda k, t: got.append((k, t)))
    assert [k for k, _ in got] == ["reasoning", "reasoning", "content", "content"]
    resp = DeepSeekAdapter().parse_response(raw)
    assert resp.message.reasoning_content == "用户问北京天气，需要调 get_weather。"
    assert resp.message.content == "我查一下。"
    assert resp.message.tool_calls and resp.message.tool_calls[0].name == "get_weather"
    assert json.loads(resp.message.tool_calls[0].arguments) == {"city": "北京"}
    assert resp.finish_reason == "tool_calls" and resp.usage.cache_hit_tokens == 256
    assert resp.usage.reasoning_tokens == 12


def test_parse_ignores_comments_and_stops_at_done() -> None:
    lines = [": hi", "", 'data: {"a":1}', "data: [DONE]", 'data: {"b":2}']
    assert list(parse_sse_lines(lines)) == [{"a": 1}]


def _sse_body() -> bytes:
    return SSE.read_bytes()


async def test_post_stream_feeds_sink_and_sends_stream_flag() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=_sse_body(), headers={"content-type": "text/event-stream"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    t = HttpTransport("https://x", "TW_TEST_KEY", client=client)
    deltas: list[str] = []
    import os

    os.environ["TW_TEST_KEY"] = "k"
    try:
        raw = await t.post_stream("/chat/completions", {"model": "m", "stream": False}, lambda k, s: deltas.append(s))
    finally:
        del os.environ["TW_TEST_KEY"]
    assert seen[0]["stream"] is True and seen[0]["stream_options"] == {"include_usage": True}
    assert "".join(deltas) == "用户问北京天气，需要调 get_weather。我查一下。"
    assert raw["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "get_weather"


async def test_post_stream_does_not_retry_after_partial_output() -> None:
    calls = 0

    class Broken(httpx.AsyncByteStream):
        async def __aiter__(self):  # type: ignore[override]
            yield _sse_body().split(b"\n\n")[1] + b"\n\n"
            raise httpx.ReadError("boom")

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, stream=Broken())

    import os

    os.environ["TW_TEST_KEY"] = "k"

    async def no_sleep(_: float) -> None:
        return None

    t = HttpTransport("https://x", "TW_TEST_KEY", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
                      sleep=no_sleep)  # fmt: skip
    try:
        with pytest.raises(LLMUnavailable, match="中断"):
            await t.post_stream("/c", {}, lambda k, s: None)
    finally:
        del os.environ["TW_TEST_KEY"]
    assert calls == 1


class StreamingCanned(CannedTransport):
    def __init__(self, response: dict[str, Any]) -> None:
        super().__init__(response)
        self.streamed = 0

    async def post_stream(self, path: str, payload: dict[str, Any], sink: Any) -> dict[str, Any]:
        self.streamed += 1
        assert "stream_options" not in payload  # 拼 stream 字段是 HttpTransport 的事；key 按原请求
        return assemble_chunks(_chunks(), sink)


async def test_record_with_sink_streams_and_caches_under_non_stream_key(tmp_path: Path) -> None:
    inner = StreamingCanned({})
    client, rr = client_with(inner, "record", tmp_path)
    got: list[str] = []
    req = cases.text_nonthinking()
    with streaming(lambda k, t: got.append(k)):
        resp = await client.complete(req, cases.MODEL)
    assert inner.streamed == 1 and inner.calls == 0 and got
    payload = DeepSeekAdapter().build_request("deepseek-flash", req)
    assert payload["stream"] is False
    assert rr.store.get(request_key("deepseek", payload)) is not None  # 录下的缓存仍按非流式请求命中
    assert resp.message.content == "我查一下。"


async def test_replay_hit_is_split_into_deltas() -> None:
    c = replay_client()
    got: list[tuple[str, str]] = []
    with streaming(lambda k, t: got.append((k, t))):
        resp = await c.complete(cases.tool_multiturn_thinking_1(), cases.MODEL)
    assert resp.source == "replay"
    text = "".join(t for k, t in got if k == "content")
    reasoning = "".join(t for k, t in got if k == "reasoning")
    assert text == (resp.message.content or "")
    assert reasoning == (resp.message.reasoning_content or "") and reasoning


async def test_no_sink_means_no_deltas_and_plain_post(tmp_path: Path) -> None:
    inner = StreamingCanned(assemble_chunks(_chunks()))
    client, _ = client_with(inner, "record", tmp_path)
    await client.complete(cases.text_nonthinking(), cases.MODEL)
    assert inner.calls == 1 and inner.streamed == 0


def test_split_text_roundtrips() -> None:
    s = "复现成立。改成只数非空行：\n\n```python\nreturn 1\n```"
    assert "".join(split_text(s, 4)) == s
    assert stream_payload({"a": 1}) == {"a": 1, "stream": True, "stream_options": {"include_usage": True}}


def test_thinking_levels_and_model_whitelist() -> None:
    assert executor_override("deepseek-flash", "off") == {"model": "deepseek/deepseek-flash", "thinking": False}
    assert executor_override(None, "medium") == {"thinking": True, "effort": "high"}
    assert THINKING_LEVELS["high"]["effort"] == "max"
    for bad in ("deepseek-v4-pro", "deepseek/deepseek-v4-pro", "qwen/qwen3"):
        with pytest.raises(ValueError):
            executor_override(bad, None)
    with pytest.raises(ValueError):
        executor_override(None, "ultra")
