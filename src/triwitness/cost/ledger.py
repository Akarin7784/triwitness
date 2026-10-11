"""本机用量日志（W1-12；0.3.2 起只记录不拦截）：SQLite，默认 ~/.triwitness/ledger.sqlite。

- 只记录真实花费（live / record 模式下真正联网的调用；本地缓存命中不记）。
- 0.3.2（Eva 19:14）：去掉预算控制——没有 ¥100 总额、类别信封、STOP / TW_KILL_SWITCH 熔断；
  类别只用于统计（chat / dogfood / reviewer / …）。花多少由用户自己把控（DeepSeek 余额是天然上限）。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from triwitness.config import tw_home
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


@dataclass(frozen=True)
class LedgerSummary:
    total_cny: float
    calls: int
    peak_calls: int
    input_tokens: int
    cache_hit_tokens: int
    output_tokens: int

    @property
    def cache_hit_rate(self) -> float:
        return self.cache_hit_tokens / self.input_tokens if self.input_tokens else 0.0


class GlobalLedger:
    """本机用量日志（0.3.2 起只记录、不拦截：没有总额 / 类别信封 / 熔断，见 ADR-0002 修订）。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or tw_home() / "ledger.sqlite"
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
            sql = f"SELECT {', '.join(cols)} FROM calls ORDER BY ts DESC, id DESC LIMIT ?"
            rows = db.execute(sql, (limit,)).fetchall()
        return [dict(zip(cols, r, strict=True)) for r in rows]

    def summary(self) -> LedgerSummary:
        with self._db() as db:
            row = db.execute(
                "SELECT COALESCE(SUM(cost_cny),0), COUNT(*), COALESCE(SUM(peak),0), COALESCE(SUM(input_tokens),0),"
                " COALESCE(SUM(cache_hit_tokens),0), COALESCE(SUM(output_tokens),0) FROM calls"
            ).fetchone()
        return LedgerSummary(float(row[0]), int(row[1]), int(row[2]), int(row[3]), int(row[4]), int(row[5]))

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
