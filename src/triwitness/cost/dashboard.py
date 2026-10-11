"""用量看板 `tw usage`（原 `tw budget`，W1-26；0.3.2 起只统计、不控制）：已花、按类别 / 周 / 模型、缓存命中率、
高峰价调用数；`--md` 导出。

`tw budget sync` 调 DeepSeek GET /user/balance 与本地账本对账（不是模型调用、不花钱，但会用到 key：只放在请求头里，
从不打印、不写盘）。按角色拆分要等 W3 账本加 role 列。
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from triwitness.core.errors import ConfigError
from triwitness.cost.ledger import GlobalLedger
from triwitness.llm.pricing import to_shanghai

BALANCE_URL = "https://api.deepseek.com/user/balance"


@dataclass
class UsageView:
    """用量总览（0.3.2：只统计，不再有总额 / 信封 / 剩余 / 熔断）。"""

    now: datetime
    spent: float
    calls: int
    peak_calls: int
    cache_hit_rate: float | None
    first_call: datetime | None
    by_category: dict[str, float] = field(default_factory=dict)
    by_week: dict[str, float] = field(default_factory=dict)
    by_model: dict[str, float] = field(default_factory=dict)


def usage_view(ledger: GlobalLedger, *, now: datetime | None = None) -> UsageView:
    now = now or datetime.now(UTC)
    s = ledger.summary()
    with sqlite3.connect(ledger.path) as db:
        first = db.execute("SELECT MIN(ts) FROM calls").fetchone()[0]
    return UsageView(
        now=now,
        spent=s.total_cny,
        calls=s.calls,
        peak_calls=s.peak_calls,
        cache_hit_rate=s.cache_hit_rate if s.input_tokens else None,
        first_call=datetime.fromisoformat(first) if first else None,
        by_category=dict(sorted(ledger.breakdown("category").items())),
        by_week=dict(sorted(ledger.breakdown("week").items())),
        by_model=ledger.breakdown("model"),
    )


def usage_json(v: UsageView, ledger: GlobalLedger, *, recent: int = 30) -> dict[str, Any]:
    """桌面端用量页的数据（`tw usage --json`）：总览 + 按类别 / 周 / 模型 + 最近调用。时间一律北京时间。"""
    rows = []
    for r in ledger.recent(recent):
        ts = datetime.fromisoformat(str(r["ts"]))
        rows.append({**r, "ts": to_shanghai(ts).strftime("%m-%d %H:%M"), "peak": bool(r["peak"])})
    return {
        "now": to_shanghai(v.now).isoformat(timespec="seconds"),
        "spent": round(v.spent, 6),
        "calls": v.calls,
        "peak_calls": v.peak_calls,
        "cache_hit_rate": v.cache_hit_rate,
        "first_call": None if v.first_call is None else f"{to_shanghai(v.first_call):%Y-%m-%d}",
        "by_category": v.by_category,
        "by_week": v.by_week,
        "by_model": v.by_model,
        "recent": rows,
    }


def _y(x: float | None) -> str:
    return "—" if x is None else f"¥{x:.4f}"


def render_usage_markdown(v: UsageView) -> str:
    hit = "—" if v.cache_hit_rate is None else f"{v.cache_hit_rate:.0%}"
    lines = [
        f"## 用量 · {to_shanghai(v.now):%Y-%m-%d %H:%M}（北京时间）",
        "",
        f"已花 **{_y(v.spent)}**｜{v.calls} 次调用（高峰价 {v.peak_calls}）｜缓存命中 {hit}",
    ]
    if v.by_category:
        lines += ["", "| 类别 | 已花 |", "|---|---|", *[f"| {k} | {_y(x)} |" for k, x in v.by_category.items()]]
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


def reconcile(snapshots: Path, cur: BalanceCheck, now: datetime) -> str:
    """与上一次 sync 的快照对比：余额下降 vs 账本增量；然后追加本次快照（JSONL，只含金额与时间）。"""
    prev: dict[str, Any] | None = None
    if snapshots.exists():
        lines = [ln for ln in snapshots.read_text(encoding="utf-8").splitlines() if ln.strip()]
        prev = json.loads(lines[-1]) if lines else None
    snapshots.parent.mkdir(parents=True, exist_ok=True)
    with snapshots.open("a", encoding="utf-8") as f:
        rec = {"ts": now.isoformat(timespec="seconds"), "balance": cur.total_balance, "ledger_spent": cur.ledger_spent}
        f.write(json.dumps(rec) + "\n")
    if prev is None:
        return "首次对账：已记下基线，下次 sync 起比较余额变化与账本增量"
    drop = float(prev["balance"]) - cur.total_balance
    led = cur.ledger_spent - float(prev["ledger_spent"])
    gap = drop - led
    verdict = "一致" if abs(gap) <= max(0.01, 0.05 * led) else "不符：检查账本外调用或充值"
    return f"自 {prev['ts']}：余额下降 ¥{drop:.4f}｜账本增加 ¥{led:.4f}｜差 ¥{gap:+.4f}（{verdict}）"


__all__ = [
    "BalanceCheck",
    "UsageView",
    "fetch_balance",
    "parse_balance",
    "reconcile",
    "render_usage_markdown",
    "usage_json",
    "usage_view",
]
