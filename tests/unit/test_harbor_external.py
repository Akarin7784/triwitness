"""W5-13 Harbor 外部对照脚本：参数、高峰、报告（不起容器、不调用模型）。"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("harbor_external", ROOT / "scripts" / "harbor_external.py")
assert _spec and _spec.loader
he = importlib.util.module_from_spec(_spec)
sys.modules["harbor_external"] = he
_spec.loader.exec_module(he)


def test_subset_is_small_and_unique() -> None:
    assert 1 <= len(he.TASKS) <= 10 and len(set(he.TASKS)) == len(he.TASKS)
    assert len(he.TB2_SHA) == 40


def test_harbor_args_pins_version_and_agent(tmp_path: Path) -> None:
    a = he.harbor_args(tmp_path / "tb2", tmp_path / "jobs", concurrency=2, attempts=1, tasks=["fix-git"],
                       thinking=False)  # fmt: skip
    assert a[:5] == ["uv", "run", "--with", he.HARBOR, "harbor"]
    assert he.AGENT in a and "thinking=false" in a
    assert a[a.index("-i") + 1] == "fix-git" and a.count("-i") == 1


@pytest.mark.parametrize(
    ("stamp", "peak"),
    [("2026-10-12T10:00:00+08:00", True), ("2026-10-12T12:30:00+08:00", False),
     ("2026-10-12T17:59:00+08:00", True), ("2026-10-11T10:00:00+08:00", False)],
)  # fmt: skip
def test_peak(stamp: str, peak: bool) -> None:
    assert he.is_peak(datetime.fromisoformat(stamp)) is peak


def test_run_refuses_without_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    rc = he.cmd_run(tmp_path, tmp_path / "o", concurrency=1, attempts=1, tasks=["fix-git"], thinking=False,
                    allow_peak=True, dry_run=True)  # fmt: skip
    assert rc == 2


def test_report_counts_rewards_and_cost(tmp_path: Path) -> None:
    job = tmp_path / "jobs" / "2026-10-12__01-00-00"
    for name, reward, cost in (("fix-git__a", 1.0, 0.05), ("cobol-modernization__b", 0.0, 0.1)):
        d = job / name
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps({
            "task_name": name.split("__")[0], "verifier_result": {"rewards": {"reward": reward}},
            "agent_result": {"metadata": {"triwitness_status": "done", "cost_cny": cost, "steps": 7,
                                          "cache_hit_rate": 0.8}},
        }), encoding="utf-8")  # fmt: skip
    (job / "result.json").write_text("{}", encoding="utf-8")  # job 级汇总，不算试次
    rep = he.cmd_report(tmp_path / "jobs")
    text = rep.read_text(encoding="utf-8")
    assert "解决 1/2" in text and "¥0.15" in text
    s = json.loads((tmp_path / "jobs" / "summary.json").read_text(encoding="utf-8"))
    assert s["solved"] == 1 and s["n"] == 2


def test_repeats_plan_skips_done_resumes_partial(tmp_path: Path) -> None:
    out = tmp_path / "r2"
    (out / "rep0").mkdir(parents=True)
    (out / "rep0" / "config.json").write_text("{}", encoding="utf-8")
    done = {"n_total_trials": 10, "n_completed_trials": 10, "n_running_trials": 0, "n_pending_trials": 0}
    (out / "rep0" / "result.json").write_text(json.dumps({"stats": done}), encoding="utf-8")
    (out / "rep1").mkdir()
    (out / "rep1" / "config.json").write_text("{}", encoding="utf-8")
    part = {"n_total_trials": 10, "n_completed_trials": 4, "n_pending_trials": 6}
    (out / "rep1" / "result.json").write_text(json.dumps({"stats": part}), encoding="utf-8")
    assert he.repeat_plan(out, 3) == [("rep0", "done"), ("rep1", "partial"), ("rep2", "missing")]


def test_repeats_dry_run_builds_resume_and_named_jobs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "r2"
    (out / "rep0").mkdir(parents=True)
    (out / "rep0" / "config.json").write_text("{}", encoding="utf-8")
    rc = he.cmd_run(tmp_path, out, concurrency=2, attempts=1, tasks=he.TASKS, thinking=False, allow_peak=True,
                    dry_run=True, repeats=2)  # fmt: skip
    text = capsys.readouterr().out
    assert rc == 0
    assert "harbor jobs resume -p" in text and str(out / "rep0") in text
    assert "--job-name rep1" in text and "-k 1" in text


def test_report_per_task_counts_with_repeats(tmp_path: Path) -> None:
    for rep, reward in (("rep0", 1.0), ("rep1", 0.0), ("rep2", 1.0)):
        d = tmp_path / rep / f"fix-git__{rep}"
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps({"task_name": "terminal-bench/fix-git",
                                                   "verifier_result": {"rewards": {"reward": reward}},
                                                   "agent_result": {"metadata": {"cost_cny": 0.03}}}))  # fmt: skip
    he.cmd_report(tmp_path)
    rep = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "| terminal-bench/fix-git | 2/3 |" in rep
    assert {r["job"] for r in json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))["rows"]} == {
        "rep0",
        "rep1",
        "rep2",
    }
