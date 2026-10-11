"""对外副作用的幂等键（spec 011 §4，W4-09；04 §3.6）：开 PR、推送、评论等“做了就收不回”的操作先查后做。

- 键 = `<task 或 run id>:<操作名>:<序号>`（`side_effect_key`）；记录在 `TW_HOME/tw.db` 的 `side_effects` 表。
- `SideEffectLog.run(key, do, find=...)`：
  - 已是 done → 直接返回记录的结果，不再执行（重放 / 重试 / 用户连点两次都不会重复）；
  - started / failed（上次执行到一半进程没了、或失败）→ 先调用 `find()` 去外部查一次
    （例如 GitHub 上同分支是否已有 PR），查到就补记 done 并返回；查不到才重新执行；
  - 第一次 → 记 started（预写）→ 执行 → 记 done（或 failed + 错误摘要）。
- 结果只存 JSON 可序列化的摘要（URL、编号），不存令牌；错误摘要先脱敏。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from triwitness.config import tw_home
from triwitness.core.redact import redact_text

SCHEMA = """
CREATE TABLE IF NOT EXISTS side_effects (
  key        TEXT PRIMARY KEY,
  op         TEXT NOT NULL,
  status     TEXT NOT NULL,          -- started / done / failed
  attempts   INTEGER NOT NULL DEFAULT 0,
  result     TEXT,                   -- JSON
  error      TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


def side_effect_key(owner: str, op: str, n: int = 0) -> str:
    """`task_id（或 run_id）+ 操作名 + 序号`（04 §3.6）。"""
    if not owner or not op or ":" in op:
        raise ValueError("幂等键需要 owner 和不含冒号的操作名")
    return f"{owner}:{op}:{n}"


@dataclass(frozen=True)
class SideEffect:
    key: str
    op: str
    status: str
    attempts: int
    result: dict[str, Any] | None
    error: str | None


@dataclass(frozen=True)
class Outcome:
    result: dict[str, Any]
    reused: bool  # True = 没有执行，沿用了记录或外部已存在的结果
    how: str  # executed / recorded / found


class SideEffectLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (tw_home() / "tw.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> SideEffectLog:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get(self, key: str) -> SideEffect | None:
        with self._lock:
            row = self._db.execute("SELECT key, op, status, attempts, result, error FROM side_effects WHERE key=?",
                                   (key,)).fetchone()  # fmt: skip
        if row is None:
            return None
        return SideEffect(row[0], row[1], row[2], int(row[3]), json.loads(row[4]) if row[4] else None, row[5])

    def _set(self, key: str, op: str, status: str, *, result: dict[str, Any] | None = None, error: str | None = None,
             attempt: bool = False) -> None:  # fmt: skip
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO side_effects(key, op, status, attempts, result, error, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET status=excluded.status, "
                "attempts=side_effects.attempts + ?, result=COALESCE(excluded.result, side_effects.result), "
                "error=excluded.error, updated_at=excluded.updated_at",
                (key, op, status, 1 if attempt else 0, json.dumps(result, ensure_ascii=False) if result else None,
                 error, now, now, 1 if attempt else 0),
            )  # fmt: skip

    def run(self, key: str, do: Callable[[], dict[str, Any]], *,
            find: Callable[[], dict[str, Any] | None] | None = None) -> Outcome:  # fmt: skip
        op = key.split(":")[-2] if key.count(":") >= 2 else key
        prev = self.get(key)
        if prev is not None and prev.status == "done" and prev.result is not None:
            return Outcome(prev.result, True, "recorded")
        if prev is not None and find is not None:  # 上次没确认完成：先查后做
            found = find()
            if found is not None:
                self._set(key, op, "done", result=found)
                return Outcome(found, True, "found")
        self._set(key, op, "started", attempt=True)
        try:
            result = do()
        except Exception as e:
            self._set(key, op, "failed", error=redact_text(f"{type(e).__name__}: {e}", max_len=500))
            raise
        self._set(key, op, "done", result=result)
        return Outcome(result, False, "executed")


__all__ = ["Outcome", "SideEffect", "SideEffectLog", "side_effect_key"]
