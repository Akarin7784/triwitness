"""W8-05 tw eval reproduce：解析旧 run、找任务、逐题对比（不调用模型、不起 Docker）。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from triwitness.core.errors import ConfigError
from triwitness.eval.reproduce import SERVER_WARNING, compare, find_task_dirs, load_plan, resolve_run, write_comparison

SAMPLE = Path("evals/results/2026-10-10T13-10-16")


def _run(root: Path, name: str, solved: dict[str, bool], model: str = "deepseek-flash") -> Path:
    d = root / name
    cfg = {"name": "cfg", "agent": "llm", "executor": {"model": "deepseek-flash", "thinking": False}, "attempts": 1}
    d.mkdir(parents=True)
    (d / "run.json").write_text(json.dumps({"live": True, "configs": [cfg], "tasks": list(solved)}), encoding="utf-8")
    for tid, ok in solved.items():
        a = d / "cfg" / tid / "1"
        a.mkdir(parents=True)
        (a / "result.json").write_text(json.dumps({"task_id": tid, "config": "cfg", "attempt": 1, "resolved": ok,
                                                   "cost_cny": 0.01}), encoding="utf-8")  # fmt: skip
        ev = {"kind": "model_call", "payload": {"model": "deepseek-flash", "served_model": model}}
        (a / "trajectory.jsonl").write_text(json.dumps(ev) + "\n", encoding="utf-8")
    return d


def test_resolve_and_plan(tmp_path: Path) -> None:
    src = _run(tmp_path, "old", {"t1": True, "t2": False})
    assert resolve_run(src) == src
    assert resolve_run("old", results_root=tmp_path) == src
    with pytest.raises(ConfigError):
        resolve_run("nope", results_root=tmp_path)
    plan = load_plan(src)
    assert plan.task_ids == ["t1", "t2"] and plan.attempts == 1 and plan.live
    assert plan.models == {"deepseek-flash": 2}


def test_plan_rejects_non_flash(tmp_path: Path) -> None:
    src = _run(tmp_path, "old", {"t1": True})
    meta = json.loads((src / "run.json").read_text(encoding="utf-8"))
    meta["configs"][0]["executor"]["model"] = "deepseek-v4-pro"
    (src / "run.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_plan(src)


def test_compare_and_snapshot_change(tmp_path: Path) -> None:
    a = _run(tmp_path, "old", {"t1": True, "t2": False, "t3": True})
    b = _run(tmp_path, "new", {"t1": True, "t2": True}, model="deepseek-flash-2026-11")
    meta = json.loads((b / "run.json").read_text(encoding="utf-8"))
    meta["tasks"] = ["t1", "t2", "t3"]  # t3 计划了但没出结果（infra）
    (b / "run.json").write_text(json.dumps(meta), encoding="utf-8")
    cmp = write_comparison(a, b)
    assert cmp["compared"] == 2 and cmp["agreement"] == 0.5
    assert cmp["missing_in_reproduction"] == ["cfg/t3/1"]
    assert cmp["model_snapshot_changed"] is True
    md = (b / "reproduce.md").read_text(encoding="utf-8")
    assert SERVER_WARNING in md and "快照名变了" in md
    assert compare(a, a)["agreement"] == 1.0


def test_find_task_dirs() -> None:
    found, missing = find_task_dirs(["csv-blank-line", "no-such-task"])
    assert [p.name for p in found] == ["csv-blank-line"] and missing == ["no-such-task"]


@pytest.mark.skipif(not (SAMPLE / "run.json").is_file(), reason="缺少样例结果")
def test_cli_plan_only(tmp_path: Path) -> None:
    from triwitness.cli.main import app

    shutil.copytree(SAMPLE, tmp_path / "old")
    r = CliRunner().invoke(app, ["eval", "reproduce", str(tmp_path / "old"), "--plan"])
    assert r.exit_code == 0, r.output
    assert "模型服务端可能已更新" in r.output and "baseline-deepseek" in r.output and "3 次" in r.output


def test_missing_only_counts_planned_tasks(tmp_path: Path) -> None:
    a = _run(tmp_path, "old", {"t1": True, "t2": False, "t3": True})
    b = _run(tmp_path, "new", {"t1": True})
    meta = json.loads((b / "run.json").read_text(encoding="utf-8"))
    meta["tasks"] = ["t1"]  # --task t1 子集复现
    (b / "run.json").write_text(json.dumps(meta), encoding="utf-8")
    assert compare(a, b)["missing_in_reproduction"] == []
