"""直连厂商 OpenAI 兼容端点的 HTTP 传输。密钥只在发请求时从环境变量读取，不记录、不返回。"""

from __future__ import annotations

import asyncio
import os
import random
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from triwitness.core.errors import ConfigError, LLMUnavailable
from triwitness.llm.stream import ChunkAssembler, Sink, parse_sse_lines, stream_payload

RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpTransport:
    def __init__(
        self,
        base_url: str,
        key_env: str,
        *,
        timeout_s: float = 300.0,
        retries: int = 2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.key_env = key_env
        self.timeout_s = timeout_s
        self.retries = retries
        self.sleep = sleep
        self._client = client

    def _headers(self) -> dict[str, str]:
        key = os.environ.get(self.key_env)
        if not key:
            raise ConfigError(f"缺少环境变量 {self.key_env}")
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._client or httpx.AsyncClient(timeout=self.timeout_s)
        try:
            last: str = ""
            for attempt in range(self.retries + 1):
                try:
                    r = await client.post(f"{self.base_url}{path}", json=payload, headers=self._headers())
                except httpx.TransportError as e:  # 超时 / 连接错误
                    last = type(e).__name__
                else:
                    if r.status_code < 400:
                        return r.json()
                    if r.status_code not in RETRY_STATUS:
                        # 不回显请求头；响应体是厂商错误说明，可以截断后给出
                        raise LLMUnavailable(f"HTTP {r.status_code}: {r.text[:300]}")
                    last = f"HTTP {r.status_code}"
                if attempt < self.retries:
                    await self.sleep((1, 4)[min(attempt, 1)] * (1 + random.random() * 0.25))
            raise LLMUnavailable(f"重试 {self.retries} 次后仍失败：{last}")
        finally:
            if self._client is None:
                await client.aclose()

    async def post_stream(self, path: str, payload: dict[str, Any], sink: Sink) -> dict[str, Any]:
        """流式请求（SSE）：增量交给 sink，返回拼好的非流式形状响应。

        只有在还没收到任何分块时才重试（已经推给界面的增量不能重放）。
        """
        client = self._client or httpx.AsyncClient(timeout=self.timeout_s)
        body = stream_payload(payload)
        try:
            last: str = ""
            for attempt in range(self.retries + 1):
                acc = ChunkAssembler()
                got = False
                try:
                    async with client.stream("POST", f"{self.base_url}{path}", json=body, headers=self._headers()) as r:
                        if r.status_code >= 400:
                            text = (await r.aread()).decode("utf-8", "replace")
                            if r.status_code not in RETRY_STATUS:
                                raise LLMUnavailable(f"HTTP {r.status_code}: {text[:300]}")
                            last = f"HTTP {r.status_code}"
                        else:
                            async for line in r.aiter_lines():
                                for chunk in parse_sse_lines([line]):
                                    got = True
                                    for kind, text in acc.feed(chunk):
                                        sink(kind, text)
                            return acc.result()
                except httpx.TransportError as e:
                    if got:
                        raise LLMUnavailable(f"流式响应中断：{type(e).__name__}") from e
                    last = type(e).__name__
                if attempt < self.retries:
                    await self.sleep((1, 4)[min(attempt, 1)] * (1 + random.random() * 0.25))
            raise LLMUnavailable(f"重试 {self.retries} 次后仍失败：{last}")
        finally:
            if self._client is None:
                await client.aclose()
