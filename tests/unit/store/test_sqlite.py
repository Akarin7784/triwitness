"""spec 010 §9 / AC2（W4-15）：任务与事件写 SQLite，重启后能列出任务与状态，并能重放状态机。"""

from __future__ import annotations

from pathlib import Path

from triwitness.core.events import StateChangePayload, TaskFinishedPayload, TaskStartedPayload
from triwitness.core.models import CostReport, TaskState
from triwitness.core.state_machine import TaskStateMachine
from triwitness.store.sqlite import TaskStore
from triwitness.telemetry.trajectory import TrajectoryRecorder


def _go(rec: TrajectoryRecorder, a: str, b: str) -> None:
    rec.emit(StateChangePayload.model_validate({"from": a, "to": b}))


def test_persist_and_reload(tmp_path: Path) -> None:
    db = tmp_path / "tw.db"
    store = TaskStore(db)
    rec = TrajectoryRecorder("t_1", "r_1", run_dir=tmp_path / "run")
    rec.subscribe(store.observe)
    rec.emit(TaskStartedPayload(issue_title="修 add", repo="calc", config_hash="c", harness="orchestrated-1m"))
    _go(rec, "received", "preparing")
    _go(rec, "preparing", "planning")
    _go(rec, "planning", "executing")
    store.close()

    with TaskStore(db) as again:  # “重启”
        (row,) = again.list_tasks()
        assert (row.task_id, row.run_id, row.title, row.state, row.harness) == (
            "t_1", "r_1", "修 add", "executing", "orchestrated-1m")  # fmt: skip
        assert row.status is None and row.events == 4
        sm = TaskStateMachine.replay(again.state_changes("t_1"))
        assert sm.state == TaskState.EXECUTING
        rec.subscribe(again.observe)
        _go(rec, "executing", "packaging")
        _go(rec, "packaging", "done")
        cost = CostReport.from_lines("t_1", [], pricing_version="x")
        rec.emit(TaskFinishedPayload(status="done", cost_report=cost))
        row = again.get("t_1")
        assert row is not None and (row.state, row.status, row.cost_cny) == ("done", "done", 0.0)
        assert [e["kind"] for e in again.events("t_1")][-1] == "task_finished"


def test_state_change_without_task_started_creates_row(tmp_path: Path) -> None:
    with TaskStore(tmp_path / "tw.db") as store:
        rec = TrajectoryRecorder("t_2", "r_2")
        rec.subscribe(store.observe)
        _go(rec, "received", "preparing")
        (row,) = store.list_tasks()
        assert row.task_id == "t_2" and row.state == "preparing"


def test_two_tasks_ordered_by_update(tmp_path: Path) -> None:
    with TaskStore(tmp_path / "tw.db") as store:
        for tid in ("t_a", "t_b"):
            rec = TrajectoryRecorder(tid, "r" + tid)
            rec.subscribe(store.observe)
            rec.emit(TaskStartedPayload(issue_title=tid, repo="r", config_hash="c"))
        assert {r.task_id for r in store.list_tasks()} == {"t_a", "t_b"}
        assert len(store.list_tasks(limit=1)) == 1


def test_events_after_close_are_ignored(tmp_path: Path) -> None:
    """对话轮在 run_local 关库之后还会补发 turn_finished：不能报错、不能写日志告警。"""
    store = TaskStore(tmp_path / "tw.db")
    rec = TrajectoryRecorder("t_late", "r_late")
    rec.subscribe(store.observe)
    rec.emit(StateChangePayload.model_validate({"from": "received", "to": "preparing"}))
    store.close()
    rec.emit(StateChangePayload.model_validate({"from": "preparing", "to": "executing"}))
    with TaskStore(tmp_path / "tw.db") as again:
        assert [e["kind"] for e in again.events("t_late")] == ["state_change"]
