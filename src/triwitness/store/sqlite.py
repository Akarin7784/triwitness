"""SQLite 任务库（spec 010 §9，W4-15）：任务表 + 事件表，本地默认 `TW_HOME/tw.db`。

- `TaskStore.observe(event)` 订阅 TrajectoryRecorder：每条事件写 events；task_started / state_change /
  task_finished 同步更新 tasks 行。trajectory.jsonl 仍是权威记录；写库失败只记日志，不影响任务。
- 进程重启后 `list_tasks()` 能列出任务与最新状态；`state_changes()` 供状态机重放（core/state_machine.replay）。
- 服务模式的 Postgres 只留接口（`TaskStoreProtocol`），本版不实现。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from triwitness.config import tw_home
from triwitness.core.events import TrajectoryEvent

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  task_id    TEXT PRIMARY KEY,
  run_id     TEXT NOT NULL,
  title      TEXT,
  repo       TEXT,
  harness    TEXT,
  mode       TEXT,
  state      TEXT NOT NULL DEFAULT 'received',
  status     TEXT,
  cost_cny   REAL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  run_id  TEXT NOT NULL,
  seq     INTEGER NOT NULL,
  task_id TEXT NOT NULL,
  ts      TEXT NOT NULL,
  kind    TEXT NOT NULL,
  role    TEXT,
  payload TEXT NOT NULL,
  PRIMARY KEY (run_id, seq)
);
CREATE INDEX IF NOT EXISTS events_task ON events(task_id, run_id, seq);
CREATE INDEX IF NOT EXISTS tasks_updated ON tasks(updated_at);
"""


def default_db_path() -> Path:
    return tw_home() / "tw.db"


@dataclass(frozen=True)
class TaskRow:
    task_id: str
    run_id: str
    title: str | None
    repo: str | None
    harness: str | None
    mode: str | None
    state: str
    status: str | None
    cost_cny: float | None
    created_at: str
    updated_at: str
    events: int = 0

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class TaskStoreProtocol(Protocol):
    def observe(self, ev: TrajectoryEvent) -> None: ...
    def list_tasks(self, limit: int = 50) -> list[TaskRow]: ...


class TaskStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.executescript(SCHEMA)
        self.closed = False

    def close(self) -> None:
        with self._lock:
            self.closed = True
            self._db.close()

    def __enter__(self) -> TaskStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ---------------------------------------------------------------- 写
    def observe(self, ev: TrajectoryEvent) -> None:
        """TrajectoryRecorder 订阅回调：异常只记日志（任务不能因为写库失败而中断）。
        关闭后到达的事件（对话轮在 run_local 之后补发的 turn_finished 等）直接忽略。"""
        if self.closed:
            return
        try:
            self._write(ev)
        except sqlite3.Error as e:  # pragma: no cover - 磁盘满 / 锁超时
            log.warning("写任务库失败（%s）：%s", self.path, e)

    def _write(self, ev: TrajectoryEvent) -> None:
        ts = ev.ts.isoformat()
        p = ev.payload
        with self._lock:
            self._db.execute("BEGIN")
            try:
                self._db.execute(
                    "INSERT OR REPLACE INTO events(run_id, seq, task_id, ts, kind, role, payload)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (ev.run_id, ev.seq, ev.task_id, ts, ev.kind, ev.role, json.dumps(p, ensure_ascii=False)),
                )
                if ev.kind == "task_started":
                    self._db.execute(
                        "INSERT INTO tasks(task_id, run_id, title, repo, harness, mode, state, created_at, updated_at)"
                        " VALUES (?,?,?,?,?,?,'received',?,?)"
                        " ON CONFLICT(task_id) DO UPDATE SET run_id=excluded.run_id,"
                        " title=excluded.title, repo=excluded.repo, harness=excluded.harness, mode=excluded.mode,"
                        " updated_at=excluded.updated_at",
                        (ev.task_id, ev.run_id, p.get("issue_title"), p.get("repo"), p.get("harness"), p.get("mode"),
                         ts, ts),
                    )  # fmt: skip
                elif ev.kind == "state_change":
                    self._ensure(ev, ts)
                    self._db.execute("UPDATE tasks SET state=?, updated_at=? WHERE task_id=?",
                                     (p.get("to"), ts, ev.task_id))  # fmt: skip
                elif ev.kind == "task_finished":
                    self._ensure(ev, ts)
                    cost = (p.get("cost_report") or {}).get("total_cny")
                    self._db.execute("UPDATE tasks SET status=?, cost_cny=?, updated_at=? WHERE task_id=?",
                                     (p.get("status"), cost, ts, ev.task_id))  # fmt: skip
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def _ensure(self, ev: TrajectoryEvent, ts: str) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO tasks(task_id, run_id, state, created_at, updated_at) VALUES (?,?,'received',?,?)",
            (ev.task_id, ev.run_id, ts, ts),
        )

    # ---------------------------------------------------------------- 读
    def list_tasks(self, limit: int = 50) -> list[TaskRow]:
        with self._lock:
            rows = self._db.execute(
                "SELECT t.task_id, t.run_id, t.title, t.repo, t.harness, t.mode, t.state, t.status, t.cost_cny,"
                " t.created_at, t.updated_at, (SELECT COUNT(*) FROM events e WHERE e.task_id = t.task_id)"
                " FROM tasks t ORDER BY t.updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [TaskRow(*r) for r in rows]

    def get(self, task_id: str) -> TaskRow | None:
        return next((r for r in self.list_tasks(10_000) if r.task_id == task_id), None)

    def events(self, task_id: str, kind: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT run_id, seq, ts, kind, role, payload FROM events WHERE task_id=?"
        args: tuple[Any, ...] = (task_id,)
        if kind is not None:
            q += " AND kind=?"
            args += (kind,)
        with self._lock:
            rows = self._db.execute(q + " ORDER BY ts, run_id, seq", args).fetchall()
        return [{"run_id": r[0], "seq": r[1], "ts": r[2], "kind": r[3], "role": r[4], "payload": json.loads(r[5])}
                for r in rows]  # fmt: skip

    def state_changes(self, task_id: str) -> list[tuple[str, str]]:
        """(from, to) 序列：交给 TaskStateMachine.replay 重建 / 校验状态。"""
        return [(e["payload"]["from"], e["payload"]["to"]) for e in self.events(task_id, "state_change")]


__all__ = ["SCHEMA", "TaskRow", "TaskStore", "TaskStoreProtocol", "default_db_path"]
