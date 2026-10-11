"""直连厂商 OpenAI 兼容端点的 HTTP 传输。密钥只在发请求时从环境变量读取，不记录、不返回。"""

from __future__ import annotations

import asyncio
import os
import random
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from triwitness.core.errors import ConfigError, ContextOverflow, LLMUnavailable
from triwitness.llm.stream import ChunkAssembler, Sink, parse_sse_lines, stream_payload

RETRY_STATUS = {429, 500, 502, 503, 504}
OVERLOAD_STATUS = {429, 503}  # 持久重试只对限流 / 过载生效（CC 报告 §4）


@dataclass(frozen=True)
class RetryPolicy:
    """API 重试（spec 010 §7；configs/models.yaml `retry`）。CC 报告：官方默认重试 10 次、指数退避；
    无人值守时可以对限流 / 过载一直重试。"""

    attempts: int = 10  # 首次之外的重试次数
    base_s: float = 1.0
    max_s: float = 32.0
    persistent: bool = False  # 429 / 503 一直重试（单次上限 persistent_max_s，总等待上限 persistent_total_s）
    persistent_max_s: float = 60.0
    persistent_total_s: float = 6 * 3600.0

    def delay(self, attempt: int, *, persistent: bool = False) -> float:
        cap = self.persistent_max_s if persistent else self.max_s
        return min(cap, self.base_s * (2**attempt)) * (1 + random.random() * 0.25)

    @classmethod
    def load(cls) -> RetryPolicy:
        from triwitness.config import load_config

        try:
            raw = dict(load_config("models.yaml").get("retry") or {})
        except Exception:
            raw = {}
        env = os.environ.get("TW_LLM_PERSISTENT_RETRY", "").strip().lower()
        if env:
            raw["persistent"] = env in ("1", "true", "yes", "on")
        known = {k: raw[k] for k in ("attempts", "base_s", "max_s", "persistent", "persistent_max_s",
                                      "persistent_total_s") if k in raw}  # fmt: skip
        return cls(**known)


# 上下文超限的 400（DeepSeek / OpenAI 兼容端点的常见措辞）
_OVERFLOW_RE = re.compile(
    r"maximum context length|context length|context window|context_length_exceeded|too many tokens"
    r"|prompt is too long|input is too long|exceeds? the (?:model'?s )?(?:maximum|max)",
    re.IGNORECASE,
)


def http_error(status: int, text: str) -> Exception:
    """不可重试的 HTTP 错误：上下文超限单独成类（AgentLoop 压缩后重试），其余是 LLMUnavailable。"""
    msg = f"HTTP {status}: {text[:300]}"
    if status in (400, 413) and _OVERFLOW_RE.search(text):
        return ContextOverflow(msg)
    return LLMUnavailable(msg)


class HttpTransport:
    def __init__(
        self,
        base_url: str,
        key_env: str,
        *,
        timeout_s: float = 300.0,
        retries: int | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        client: httpx.AsyncClient | None = None,
        policy: RetryPolicy | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.key_env = key_env
        self.timeout_s = timeout_s
        self.policy = policy or RetryPolicy.load()
        self.retries = self.policy.attempts if retries is None else retries
        self.sleep = sleep
        self._client = client

    def _headers(self) -> dict[str, str]:
        key = os.environ.get(self.key_env)
        if not key:
            raise ConfigError(f"缺少环境变量 {self.key_env}")
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    async def _backoff(self, attempt: int, status: int | None, waited: list[float]) -> bool:
        """睡一次退避；返回 False = 不再重试。

        普通错误最多 self.retries 次；持久模式下 429 / 503 一直重试到总等待上限。
        """
        persistent = self.policy.persistent and status in OVERLOAD_STATUS
        if attempt >= self.retries and not persistent:
            return False
        if persistent and waited[0] >= self.policy.persistent_total_s:
            return False
        d = self.policy.delay(min(attempt, 16), persistent=persistent)
        waited[0] += d
        await self.sleep(d)
        return True

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._client or httpx.AsyncClient(timeout=self.timeout_s)
        try:
            last: str = ""
            attempt, waited = 0, [0.0]
            while True:
                status: int | None = None
                try:
                    r = await client.post(f"{self.base_url}{path}", json=payload, headers=self._headers())
                except httpx.TransportError as e:  # 超时 / 连接错误
                    last = type(e).__name__
                else:
                    if r.status_code < 400:
                        return r.json()
                    if r.status_code not in RETRY_STATUS:
                        # 不回显请求头；响应体是厂商错误说明，可以截断后给出
                        raise http_error(r.status_code, r.text)
                    last, status = f"HTTP {r.status_code}", r.status_code
                if not await self._backoff(attempt, status, waited):
                    break
                attempt += 1
            raise LLMUnavailable(f"重试 {attempt} 次后仍失败：{last}")
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
            attempt, waited = 0, [0.0]
            while True:
                status: int | None = None
                acc = ChunkAssembler()
                got = False
                try:
                    async with client.stream("POST", f"{self.base_url}{path}", json=body, headers=self._headers()) as r:
                        if r.status_code >= 400:
                            text = (await r.aread()).decode("utf-8", "replace")
                            if r.status_code not in RETRY_STATUS:
                                raise http_error(r.status_code, text)
                            last, status = f"HTTP {r.status_code}", r.status_code
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
                if not await self._backoff(attempt, status, waited):
                    break
                attempt += 1
            raise LLMUnavailable(f"重试 {attempt} 次后仍失败：{last}")
        finally:
            if self._client is None:
                await client.aclose()
