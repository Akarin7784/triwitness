"""流式输出（UI-20）：把模型回复的推理 / 正文增量送到界面。

- 调用方用 `streaming(sink)` 包住一次 `router.complete(...)`；适配器 / 客户端在这个上下文里把增量交给 sink。
- 真调（DeepSeek）走 `stream=true` 的 SSE，`assemble_chunks` 把分块拼回非流式响应的形状，
  所以回放缓存的 key（按非流式请求计算）和录制内容都不变。
- 回放命中时没有真实分块：`replay_deltas` 把缓存里的完整回复切成片段再送出（¥0）。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Literal

DeltaKind = Literal["reasoning", "content"]
Sink = Callable[[DeltaKind, str], None]

_sink: ContextVar[Sink | None] = ContextVar("tw_stream_sink", default=None)


def current_sink() -> Sink | None:
    return _sink.get()


@contextmanager
def streaming(sink: Sink | None) -> Iterator[None]:
    token = _sink.set(sink)
    try:
        yield
    finally:
        _sink.reset(token)


def stream_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """非流式请求 → 流式请求（只在发送时改，缓存 key 仍按原请求算）。"""
    return {**payload, "stream": True, "stream_options": {"include_usage": True}}


def parse_sse_lines(lines: Iterator[str] | list[str]) -> Iterator[dict[str, Any]]:
    """OpenAI 兼容 SSE：`data: {...}` 一行一个分块，`data: [DONE]` 结束；注释行 / keep-alive 忽略。"""
    for line in lines:
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        if data:
            yield json.loads(data)


class ChunkAssembler:
    """逐块累积；`feed` 返回本块里的增量（供 sink），`result()` 给出非流式形状的完整响应。"""

    def __init__(self) -> None:
        self.content: list[str] = []
        self.reasoning: list[str] = []
        self.calls: dict[int, dict[str, Any]] = {}
        self.finish_reason: str | None = None
        self.usage: dict[str, Any] | None = None
        self.model: str | None = None
        self.id: str | None = None
        self.created: int | None = None

    def feed(self, chunk: dict[str, Any]) -> list[tuple[DeltaKind, str]]:
        out: list[tuple[DeltaKind, str]] = []
        self.model = chunk.get("model") or self.model
        self.id = chunk.get("id") or self.id
        self.created = chunk.get("created") or self.created
        if chunk.get("usage"):
            self.usage = chunk["usage"]
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            r = delta.get("reasoning_content")
            if r:
                self.reasoning.append(r)
                out.append(("reasoning", r))
            c = delta.get("content")
            if c:
                self.content.append(c)
                out.append(("content", c))
            for tc in delta.get("tool_calls") or []:
                slot = self.calls.setdefault(
                    int(tc.get("index", 0)), {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                )
                if tc.get("id"):
                    slot["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    slot["function"]["arguments"] += fn["arguments"]
            if choice.get("finish_reason"):
                self.finish_reason = choice["finish_reason"]
        return out

    def result(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": "".join(self.content) or None}
        if self.reasoning:
            msg["reasoning_content"] = "".join(self.reasoning)
        if self.calls:
            msg["tool_calls"] = [self.calls[i] for i in sorted(self.calls)]
        raw: dict[str, Any] = {
            "object": "chat.completion",
            "model": self.model,
            "choices": [{"index": 0, "message": msg, "finish_reason": self.finish_reason}],
            "usage": self.usage or {},
        }
        if self.id:
            raw["id"] = self.id
        if self.created:
            raw["created"] = self.created
        return raw


def assemble_chunks(chunks: list[dict[str, Any]], sink: Sink | None = None) -> dict[str, Any]:
    acc = ChunkAssembler()
    for ch in chunks:
        for kind, text in acc.feed(ch):
            if sink:
                sink(kind, text)
    return acc.result()


def split_text(text: str, size: int = 12) -> list[str]:
    """回放 / 演示用：按约 size 字切片，尽量断在标点或空白后面。"""
    out: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if len(buf) >= size and (ch in " \n，。、；：！？,.;:!?)」』" or len(buf) >= size * 2):
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


def replay_deltas(reasoning: str | None, content: str | None, sink: Sink) -> None:
    for piece in split_text(reasoning or ""):
        sink("reasoning", piece)
    for piece in split_text(content or ""):
        sink("content", piece)
