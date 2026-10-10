"""成本看板 `tw budget`（W1-26）：已花 / 信封 / 剩余、燃烧速度与耗尽日期预测、缓存命中率、高峰占比；
`--md` 导出给每周预算检查。

`tw budget sync` 调 DeepSeek GET /user/balance 与本地账本对账（不是模型调用、不花钱，但会用到 key：只放在请求头里，
从不打印、不写盘）。按角色拆分要等 W3 账本加 role 列。
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from triwitness.core.errors import ConfigError
from triwitness.cost.ledger import GlobalLedger
from triwitness.llm.pricing import to_shanghai

BALANCE_URL = "https://api.deepseek.com/user/balance"


@dataclass
class EnvelopeRow:
    category: str
    spent: float
    cap: float | None

    @property
    def remaining(self) -> float | None:
        return None if self.cap is None else round(self.cap - self.spent, 6)


@dataclass
class BudgetView:
    now: datetime
    total_cny: float
    spent: float
    calls: int
    peak_calls: int
    cache_hit_rate: float | None
    warn: bool
    kill_switch: bool
    first_call: datetime | None
    envelopes: list[EnvelopeRow] = field(default_factory=list)
    by_week: dict[str, float] = field(default_factory=dict)
    by_model: dict[str, float] = field(default_factory=dict)

    @property
    def remaining(self) -> float:
        return round(self.total_cny - self.spent, 6)

    @property
    def burn_per_day(self) -> float | None:
        if not self.first_call or self.spent <= 0:
            return None
        days = max((self.now - self.first_call).total_seconds() / 86400, 1.0)
        return self.spent / days

    @property
    def exhaustion(self) -> datetime | None:
        b = self.burn_per_day
        return None if not b else self.now + timedelta(days=self.remaining / b)


def budget_view(ledger: GlobalLedger, *, now: datetime | None = None) -> BudgetView:
    now = now or datetime.now(UTC)
    s = ledger.summary()
    with sqlite3.connect(ledger.path) as db:
        first = db.execute("SELECT MIN(ts) FROM calls").fetchone()[0]
    by_cat = ledger.breakdown("category")
    cats = sorted(set(by_cat) | set(ledger.envelopes))
    return BudgetView(
        now=now,
        total_cny=ledger.total_cny,
        spent=s.total_cny,
        calls=s.calls,
        peak_calls=s.peak_calls,
        cache_hit_rate=s.cache_hit_rate if s.input_tokens else None,
        warn=ledger.warn,
        kill_switch=ledger.kill_switch_engaged(),
        first_call=datetime.fromisoformat(first) if first else None,
        envelopes=[EnvelopeRow(c, round(by_cat.get(c, 0.0), 6), ledger.envelopes.get(c)) for c in cats],
        by_week=dict(sorted(ledger.breakdown("week").items())),
        by_model=ledger.breakdown("model"),
    )


def _y(x: float | None) -> str:
    return "—" if x is None else f"¥{x:.4f}"


def render_budget_markdown(v: BudgetView) -> str:
    state = "🛑 熔断开启" if v.kill_switch else ("⚠ 超过告警线" if v.warn else "正常")
    hit = "—" if v.cache_hit_rate is None else f"{v.cache_hit_rate:.0%}"
    burn = "—" if v.burn_per_day is None else f"¥{v.burn_per_day:.4f}/天"
    exh = "—" if v.exhaustion is None else f"{to_shanghai(v.exhaustion):%Y-%m-%d}"
    lines = [
        f"## 预算 · {to_shanghai(v.now):%Y-%m-%d %H:%M}（北京时间）",
        "",
        f"已花 **{_y(v.spent)}** / 总额 ¥{v.total_cny:g}｜剩余 {_y(v.remaining)}｜{v.calls} 次调用"
        f"（高峰 {v.peak_calls}）｜缓存命中 {hit}｜燃烧 {burn}｜按此速度耗尽 {exh}｜状态 {state}",
        "",
        "| 类别 | 已花 | 信封 | 剩余 |",
        "|---|---|---|---|",
        *[f"| {e.category} | {_y(e.spent)} | {_y(e.cap)} | {_y(e.remaining)} |" for e in v.envelopes],
    ]
    if v.by_week:
        lines += ["", "| 周 | 已花 |", "|---|---|", *[f"| {k} | {_y(x)} |" for k, x in v.by_week.items()]]
    if v.by_model:
        lines += ["", "| 模型 | 已花 |", "|---|---|", *[f"| {k} | {_y(x)} |" for k, x in v.by_model.items()]]
    return "\n".join(lines) + "\n"


@dataclass
class BalanceCheck:
    currency: str
    total_balance: float
    granted: float
    topped_up: float
    ledger_spent: float


async def fetch_balance(
    client: httpx.AsyncClient | None = None, *, key_env: str = "DEEPSEEK_API_KEY"
) -> dict[str, Any]:
    key = os.environ.get(key_env)
    if not key:
        raise ConfigError(f"缺少环境变量 {key_env}")
    c = client or httpx.AsyncClient(timeout=30)
    try:
        r = await c.get(BALANCE_URL, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
        r.raise_for_status()
        return r.json()
    finally:
        if client is None:
            await c.aclose()


def parse_balance(data: dict[str, Any], ledger_spent: float) -> BalanceCheck:
    infos = data.get("balance_infos") or []
    info = next((i for i in infos if i.get("currency") == "CNY"), infos[0] if infos else {})
    return BalanceCheck(
        currency=str(info.get("currency", "CNY")),
        total_balance=float(info.get("total_balance", 0) or 0),
        granted=float(info.get("granted_balance", 0) or 0),
        topped_up=float(info.get("topped_up_balance", 0) or 0),
        ledger_spent=ledger_spent,
    )


__all__ = ["BalanceCheck", "BudgetView", "budget_view", "fetch_balance", "parse_balance", "render_budget_markdown"]
