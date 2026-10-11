"""全局预算账本与熔断（W1-12）：SQLite，默认 ~/.triwitness/ledger.sqlite。

- 只记录真实花费（live / record 模式下真正发生的调用）。
- 调用前 `precheck(estimate, category)`：已花 + 预估 > 总额 或 > 类别信封 → 拒绝；
  存在 STOP 文件（~/.triwitness/STOP）或 TW_KILL_SWITCH=1 → 拒绝。
- 余额是天然硬上限；本账本是“¥100 计划总额”的软件侧硬停。
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from triwitness.config import load_config, tw_home
from triwitness.core.errors import BudgetExceeded
from triwitness.core.models import Usage

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  category TEXT NOT NULL,
  task_id TEXT,
  model TEXT NOT NULL,
  served_model TEXT,
  peak INTEGER NOT NULL,
  input_tokens INTEGER NOT NULL,
  cache_hit_tokens INTEGER NOT NULL,
  cache_miss_tokens INTEGER NOT NULL,
  output_tokens INTEGER NOT NULL,
  cost_cny REAL NOT NULL,
  pricing_version TEXT NOT NULL
);
"""


class KillSwitchEngaged(BudgetExceeded):
    """STOP 文件或 TW_KILL_SWITCH 生效。"""


@dataclass(frozen=True)
class LedgerSummary:
    total_cny: float
    cap_cny: float
    calls: int
    peak_calls: int
    input_tokens: int
    cache_hit_tokens: int
    output_tokens: int

    @property
    def remaining_cny(self) -> float:
        return self.cap_cny - self.total_cny

    @property
    def cache_hit_rate(self) -> float:
        return self.cache_hit_tokens / self.input_tokens if self.input_tokens else 0.0


class GlobalLedger:
    def __init__(
        self,
        path: Path | None = None,
        *,
        total_cny: float | None = None,
        envelopes: dict[str, float] | None = None,
        warn_ratio: float | None = None,
        stop_file: Path | None = None,
    ) -> None:
        cfg = load_config("budget.yaml")
        self.path = path or tw_home() / "ledger.sqlite"
        self.total_cny = float(total_cny if total_cny is not None else cfg["total_cny"])
        self.envelopes = {k: float(v) for k, v in (envelopes or cfg.get("envelopes_cny", {})).items()}
        self.warn_ratio = float(warn_ratio if warn_ratio is not None else cfg.get("warn_ratio", 0.8))
        self.stop_file = stop_file or tw_home() / "STOP"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript(_SCHEMA)

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    # ------------------------------------------------------------ 查询

    def spent(self, category: str | None = None) -> float:
        q, args = "SELECT COALESCE(SUM(cost_cny), 0) FROM calls", ()
        if category:
            q, args = q + " WHERE category = ?", (category,)
        with self._db() as db:
            return float(db.execute(q, args).fetchone()[0])

    def recent(self, limit: int = 30) -> list[dict[str, object]]:
        """最近的调用（新 → 旧），给桌面端预算页（`tw budget --json`）。"""
        cols = ("ts", "category", "task_id", "model", "peak", "input_tokens", "cache_hit_tokens",
                "cache_miss_tokens", "output_tokens", "cost_cny")  # fmt: skip
        with self._db() as db:
            rows = db.execute(f"SELECT {', '.join(cols)} FROM calls ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(zip(cols, r, strict=True)) for r in rows]

    def summary(self) -> LedgerSummary:
        with self._db() as db:
            row = db.execute(
                "SELECT COALESCE(SUM(cost_cny),0), COUNT(*), COALESCE(SUM(peak),0), COALESCE(SUM(input_tokens),0),"
                " COALESCE(SUM(cache_hit_tokens),0), COALESCE(SUM(output_tokens),0) FROM calls"
            ).fetchone()
        return LedgerSummary(
            float(row[0]), self.total_cny, int(row[1]), int(row[2]), int(row[3]), int(row[4]), int(row[5])
        )

    def breakdown(self, by: str) -> dict[str, float]:
        """按 category / model / week（北京时间 ISO 周，如 2026-W41）/ peak 汇总花费。"""
        from datetime import datetime as _dt
        from zoneinfo import ZoneInfo

        if by not in ("category", "model", "week", "peak"):
            raise ValueError("by 只能是 category / model / week / peak")
        out: dict[str, float] = {}
        with self._db() as db:
            rows = db.execute("SELECT ts, category, model, peak, cost_cny FROM calls").fetchall()
        for ts, category, model, peak, cost in rows:
            if by == "week":
                y, w, _ = _dt.fromisoformat(ts).astimezone(ZoneInfo("Asia/Shanghai")).isocalendar()
                key = f"{y}-W{w:02d}"
            else:
                key = {"category": category, "model": model, "peak": "peak" if peak else "off_peak"}[by]
            out[key] = round(out.get(key, 0.0) + float(cost), 8)
        return out

    # ------------------------------------------------------------ 熔断

    def kill_switch_engaged(self) -> bool:
        return self.stop_file.exists() or os.environ.get("TW_KILL_SWITCH", "").strip() not in (
            "",
            "0",
            "false",
        )

    def precheck(self, estimate_cny: float, category: str) -> None:
        if self.kill_switch_engaged():
            raise KillSwitchEngaged("熔断已开启（STOP 文件或 TW_KILL_SWITCH）", limit="kill_switch", used=0, cap=0)
        total = self.spent()
        if total + estimate_cny > self.total_cny:
            raise BudgetExceeded(
                f"全局预算不足：已花 ¥{total:.4f} + 预估 ¥{estimate_cny:.4f} > ¥{self.total_cny:g}",
                limit="total_cny",
                used=total,
                cap=self.total_cny,
            )
        if category in self.envelopes:
            cat = self.spent(category)
            cap = self.envelopes[category]
            if cat + estimate_cny > cap:
                raise BudgetExceeded(
                    f"类别信封 {category} 不足：已花 ¥{cat:.4f} + 预估 ¥{estimate_cny:.4f} > ¥{cap:g}",
                    limit=f"envelope:{category}",
                    used=cat,
                    cap=cap,
                )

    def record(
        self,
        *,
        category: str,
        model: str,
        usage: Usage,
        cost_cny: float,
        peak: bool,
        pricing_version: str,
        served_model: str | None = None,
        task_id: str | None = None,
        at: datetime | None = None,
    ) -> None:
        with self._db() as db:
            db.execute(
                "INSERT INTO calls (ts, category, task_id, model, served_model, peak, input_tokens, cache_hit_tokens,"
                " cache_miss_tokens, output_tokens, cost_cny, pricing_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    (at or datetime.now(UTC)).isoformat(),
                    category,
                    task_id,
                    model,
                    served_model,
                    int(peak),
                    usage.input_tokens,
                    usage.cache_hit_tokens,
                    usage.cache_miss_tokens,
                    usage.output_tokens,
                    cost_cny,
                    pricing_version,
                ),
            )

    @property
    def warn(self) -> bool:
        return self.spent() >= self.warn_ratio * self.total_cny
