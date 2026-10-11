"""`tw budget` 看板（W1-26）：信封、燃烧速度、耗尽日期、Markdown；余额对账用假 HTTP（不联网）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from triwitness.core.models import Usage
from triwitness.cost.dashboard import (
    BALANCE_URL,
    budget_json,
    budget_view,
    fetch_balance,
    parse_balance,
    render_budget_markdown,
)
from triwitness.cost.ledger import GlobalLedger

T0 = datetime(2026, 10, 10, 13, 0, tzinfo=UTC)


def ledger(tmp_path: Path) -> GlobalLedger:
    return GlobalLedger(tmp_path / "l.sqlite", total_cny=100, envelopes={"dev": 6, "baseline": 10},
                        stop_file=tmp_path / "STOP")  # fmt: skip


def rec(led: GlobalLedger, cat: str, cost: float, at: datetime, *, peak: bool = False) -> None:
    led.record(category=cat, model="deepseek-flash", usage=Usage(input_tokens=1000, cache_hit_tokens=900,
               cache_miss_tokens=100, output_tokens=50), cost_cny=cost, peak=peak, pricing_version="v",
               at=at)  # fmt: skip


def test_view_and_markdown(tmp_path: Path) -> None:
    led = ledger(tmp_path)
    rec(led, "dev", 0.5, T0)
    rec(led, "baseline", 1.5, T0 + timedelta(days=1), peak=True)
    v = budget_view(led, now=T0 + timedelta(days=4))
    assert v.spent == pytest.approx(2.0) and v.remaining == pytest.approx(98.0)
    assert v.calls == 2 and v.peak_calls == 1 and v.cache_hit_rate == pytest.approx(0.9)
    assert v.burn_per_day == pytest.approx(0.5)
    assert v.exhaustion is not None and (v.exhaustion - v.now).days == 196
    rows = {e.category: e for e in v.envelopes}
    assert rows["dev"].remaining == pytest.approx(5.5) and rows["baseline"].spent == pytest.approx(1.5)
    md = render_budget_markdown(v)
    assert "已花 **¥2.0000**" in md and "| dev | ¥0.5000 | ¥6.0000 | ¥5.5000 |" in md
    assert "2026-W41" in md and "deepseek-flash" in md and "高峰 1" in md and "状态 正常" in md


def test_budget_json_for_desktop(tmp_path: Path) -> None:
    """桌面端预算页：真实账本 → JSON（北京时间、最近调用新→旧、空账本也能出）。"""
    import json

    led = ledger(tmp_path)
    assert budget_json(budget_view(led, now=T0), led)["recent"] == []
    rec(led, "dev", 0.5, T0)
    rec(led, "baseline", 1.5, T0 + timedelta(days=1), peak=True)
    d = budget_json(budget_view(led, now=T0 + timedelta(days=4)), led)
    json.dumps(d)  # 可序列化
    assert d["spent"] == pytest.approx(2.0) and d["calls"] == 2 and d["peak_calls"] == 1
    assert [r["category"] for r in d["recent"]] == ["baseline", "dev"]
    assert d["recent"][0]["ts"] == "10-11 21:00" and d["recent"][0]["peak"] is True
    assert d["recent"][1]["cache_hit_tokens"] == 900 and d["now"].endswith("+08:00")
    assert {e["category"] for e in d["envelopes"]} >= {"dev", "baseline"}


def test_empty_ledger_and_kill_switch(tmp_path: Path) -> None:
    led = ledger(tmp_path)
    (tmp_path / "STOP").touch()
    v = budget_view(led, now=T0)
    assert v.spent == 0 and v.burn_per_day is None and v.exhaustion is None and v.cache_hit_rate is None
    assert "熔断开启" in render_budget_markdown(v)


async def test_balance_sync_with_fake_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-real")
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["Authorization"]
        return httpx.Response(
            200,
            json={
                "is_available": True,
                "balance_infos": [
                    {
                        "currency": "CNY",
                        "total_balance": "52.10",
                        "granted_balance": "0.00",
                        "topped_up_balance": "52.10",
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        data = await fetch_balance(c)
    b = parse_balance(data, 0.0054)
    assert seen["url"] == BALANCE_URL and seen["auth"] == "Bearer sk-test-not-real"
    assert b.total_balance == pytest.approx(52.10) and b.topped_up == pytest.approx(52.10) and b.currency == "CNY"


async def test_balance_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from triwitness.core.errors import ConfigError

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ConfigError):
        await fetch_balance(httpx.AsyncClient())


def test_reconcile_snapshots(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from triwitness.cost.dashboard import BalanceCheck, reconcile

    snap = tmp_path / "s" / "balance_snapshots.jsonl"
    t = datetime(2026, 10, 10, 5, tzinfo=UTC)
    first = reconcile(snap, BalanceCheck("CNY", 59.27, 0, 59.27, 0.35), t)
    assert "基线" in first
    ok = reconcile(snap, BalanceCheck("CNY", 58.27, 0, 58.27, 1.35), t)
    assert "一致" in ok and "¥1.0000" in ok
    bad = reconcile(snap, BalanceCheck("CNY", 56.27, 0, 56.27, 1.45), t)
    assert "不符" in bad
    assert len(snap.read_text(encoding="utf-8").splitlines()) == 3
    assert "sk-" not in snap.read_text(encoding="utf-8")
