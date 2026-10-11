"""W4-15：`tw tasks` 从 SQLite 列出任务；`tw run --harness` 读 configs/harness/<名>.yaml。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from triwitness.cli.main import _harness, app
from triwitness.core.events import StateChangePayload, TaskStartedPayload
from triwitness.store.sqlite import TaskStore
from triwitness.telemetry.trajectory import TrajectoryRecorder


def test_tw_tasks_lists_from_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TW_HOME", str(tmp_path))
    r = CliRunner().invoke(app, ["tasks"])
    assert r.exit_code == 0 and "还没有任务" in r.output
    with TaskStore(tmp_path / "tw.db") as store:
        rec = TrajectoryRecorder("t_cli", "r_cli")
        rec.subscribe(store.observe)
        rec.emit(TaskStartedPayload(issue_title="修 add", repo="calc", config_hash="c", harness="orchestrated-1m"))
        rec.emit(StateChangePayload.model_validate({"from": "received", "to": "preparing"}))
    r = CliRunner().invoke(app, ["tasks", "--json"])
    assert r.exit_code == 0, r.output
    (row,) = json.loads(r.output)
    assert (row["task_id"], row["state"], row["harness"]) == ("t_cli", "preparing", "orchestrated-1m")
    r = CliRunner().invoke(app, ["tasks"])
    assert "t_cli" in r.output and "preparing" in r.output


def test_harness_option() -> None:
    assert _harness(None) is None
    h = _harness("orchestrated-1m")
    assert h is not None and h.orchestration.planner.enabled and h.orchestration.reviewer.enabled
    assert h.orchestration.plan_approval.min_risk == "L2"
    with pytest.raises(typer.BadParameter):
        _harness("does-not-exist")
