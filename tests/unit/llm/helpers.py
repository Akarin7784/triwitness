from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from triwitness.llm.client import LLMClient
from triwitness.llm.deepseek import DeepSeekAdapter
from triwitness.llm.replay import Mode, RecordReplayTransport, ReplayStore

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "llm" / "deepseek"
SAT_OFFPEAK = datetime(2026, 10, 10, 3, 0, tzinfo=UTC)  # 北京时间周六 11:00
WED_PEAK = datetime(2026, 10, 14, 2, 0, tzinfo=UTC)  # 北京时间周三 10:00


class ExplodingTransport:
    """任何网络调用都算失败。"""

    calls = 0

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        ExplodingTransport.calls += 1
        raise AssertionError("不应发生网络调用")


class CannedTransport:
    """假的“真实”传输：返回固定响应并计数。"""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls = 0

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        return self.response


def replay_client(**kw: Any) -> LLMClient:
    store = ReplayStore("deepseek", [FIXTURES])
    rr = RecordReplayTransport(store, ExplodingTransport(), mode="replay")
    return LLMClient(DeepSeekAdapter(), rr, now=lambda: SAT_OFFPEAK, **kw)


def client_with(
    inner: Any, mode: Mode, tmp: Path, *, now: datetime = SAT_OFFPEAK, **kw: Any
) -> tuple[LLMClient, RecordReplayTransport]:
    store = ReplayStore("deepseek", [tmp / "cache"], write_dir=tmp / "cache")
    rr = RecordReplayTransport(store, inner, mode=mode)
    return LLMClient(DeepSeekAdapter(), rr, now=lambda: now, **kw), rr
