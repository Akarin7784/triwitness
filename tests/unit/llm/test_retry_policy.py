"""spec 010 §7：API 重试默认 10 次指数退避；持久模式下 429 / 503 一直重试（CC 报告 §4）。"""

from __future__ import annotations

import httpx
import pytest

from triwitness.core.errors import LLMUnavailable
from triwitness.llm.http import HttpTransport, RetryPolicy


def transport(statuses: list[int], policy: RetryPolicy) -> tuple[HttpTransport, dict[str, int], list[float]]:
    hits = {"n": 0}
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        i = hits["n"]
        hits["n"] += 1
        code = statuses[i] if i < len(statuses) else 200
        return httpx.Response(code, json={"ok": True} if code == 200 else {"error": "x"})

    async def sleep(s: float) -> None:
        slept.append(s)

    t = HttpTransport("https://x", "TW_TEST_KEY", sleep=sleep, policy=policy,
                      client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))  # fmt: skip
    return t, hits, slept


@pytest.fixture(autouse=True)
def key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TW_TEST_KEY", "tw-placeholder-test")


def test_policy_defaults_from_models_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TW_LLM_PERSISTENT_RETRY", raising=False)
    p = RetryPolicy.load()
    assert (p.attempts, p.base_s, p.max_s, p.persistent) == (10, 1.0, 32.0, False)
    monkeypatch.setenv("TW_LLM_PERSISTENT_RETRY", "1")
    assert RetryPolicy.load().persistent is True


async def test_exponential_backoff_capped() -> None:
    t, hits, slept = transport([503] * 20, RetryPolicy())
    with pytest.raises(LLMUnavailable, match="重试 10 次"):
        await t.post("/c", {})
    assert hits["n"] == 11 and len(slept) == 10
    assert slept[0] < 1.3 and slept[1] >= 2.0 and max(slept) <= 32 * 1.25
    assert all(slept[i] <= slept[i + 1] * 1.25 + 1e-9 for i in range(4))


async def test_recovers_after_some_failures() -> None:
    t, hits, _ = transport([429, 502, 504], RetryPolicy())
    assert await t.post("/c", {}) == {"ok": True}
    assert hits["n"] == 4


async def test_persistent_mode_keeps_retrying_overload() -> None:
    t, hits, slept = transport([429] * 25, RetryPolicy(persistent=True))
    assert await t.post("/c", {}) == {"ok": True}
    assert hits["n"] == 26 and max(slept) <= 60 * 1.25


async def test_persistent_mode_does_not_apply_to_500() -> None:
    t, hits, _ = transport([500] * 30, RetryPolicy(persistent=True))
    with pytest.raises(LLMUnavailable):
        await t.post("/c", {})
    assert hits["n"] == 11


async def test_persistent_total_wait_cap() -> None:
    t, _, slept = transport([429] * 1000, RetryPolicy(persistent=True, persistent_total_s=100.0))
    with pytest.raises(LLMUnavailable):
        await t.post("/c", {})
    assert sum(slept) >= 100.0 and sum(slept) < 100.0 + 60 * 1.25
