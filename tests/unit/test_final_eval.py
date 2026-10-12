"""W8-01 终测脚本：计划 / 干跑 / 报告 / 分卷打包（不调用模型、不起 Docker）。"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("final_eval", ROOT / "scripts" / "final_eval.py")
assert _spec and _spec.loader
fe = importlib.util.module_from_spec(_spec)
sys.modules["final_eval"] = fe
_spec.loader.exec_module(fe)

SAMPLE = ROOT / "evals" / "results" / "2026-10-10T13-10-16" / "baseline-deepseek" / "csv-blank-line" / "1"


def test_configs_flash_only_and_loadable() -> None:
    from triwitness.eval.runner import RunConfig
    from triwitness.harness.config import HarnessConfig

    for arm, path in fe.ARMS.items():
        cfg = RunConfig.load(ROOT / path)
        assert cfg.executor["model"] == "deepseek-flash" and cfg.category == "final-eval"
        assert cfg.harness
        HarnessConfig.load(cfg.harness.removeprefix("configs/"))
        assert ("orchestrated" in cfg.harness) == (arm == "orchestrated")


def test_plan_and_estimate_within_guide(tmp_path: Path) -> None:
    plan = fe.cmd_plan(tmp_path, list(fe.ARMS), None)
    assert plan["tasks"] == 35 and plan["suite"] == "test"
    assert plan["estimate_cny_off_peak"]["total"] <= fe.BUDGET_GUIDE_CNY
    assert (tmp_path / "plan.json").is_file()


def test_dry_run_builds_resumable_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert fe.cmd_run(tmp_path, arms=["baseline"], concurrency=2, tasks=["swe-ccflow-24"], dry_run=True) == 0
    out = capsys.readouterr().out
    assert "--allow-test" in out and "--live" in out and str(tmp_path / "results" / "baseline") in out
    assert "--task swe-ccflow-24" in out
    with pytest.raises(SystemExit):
        fe.pick_arms("baseline,nope")


def _fake_arm(out: Path, arm: str, solved: dict[str, bool]) -> None:
    for tid, ok in solved.items():
        d = out / "results" / arm / arm / tid / "1"
        d.mkdir(parents=True)
        r = json.loads((SAMPLE / "result.json").read_text(encoding="utf-8"))
        r.update(task_id=tid, config=arm, resolved=ok, reward=1.0 if ok else 0.0)
        (d / "result.json").write_text(json.dumps(r), encoding="utf-8")
        shutil.copy(SAMPLE / "trajectory.jsonl", d / "trajectory.jsonl")


@pytest.mark.skipif(not SAMPLE.is_dir(), reason="缺少样例轨迹")
def test_report_and_split_bundle(tmp_path: Path) -> None:
    out = tmp_path / "final"
    _fake_arm(out, "baseline", {"a": True, "b": False, "c": False})
    _fake_arm(out, "orchestrated", {"a": True, "b": True, "c": False})
    rep = fe.cmd_report(out, list(fe.ARMS))
    text = rep.read_text(encoding="utf-8")
    assert "baseline" in text and "deepseek-flash" in text and "McNemar" in text
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["arms"]["orchestrated"]["solved"] == 2
    assert summary["paired"] == {"n": 3, "orch_only": 1, "base_only": 0, "mcnemar_p": 1.0}
    assert summary["arms"]["baseline"]["cache_hit_rate"] > 0
    one = fe.cmd_bundle(out, None, 24.0, tmp_path)
    assert len(one) == 1 and zipfile.ZipFile(one[0]).testzip() is None
    (tmp_path / "split").mkdir()
    parts = fe.cmd_bundle(out, None, 0.01, tmp_path / "split")
    assert len(parts) > 1
    names = [n for p in parts for n in zipfile.ZipFile(p).namelist()]
    assert "final/report.md" in zipfile.ZipFile(parts[0]).namelist()
    assert len(names) == len(set(names))  # 每个文件只在一个分卷里


@pytest.mark.skipif(not SAMPLE.is_dir(), reason="缺少样例轨迹")
def test_reproduce_picks_cheapest_solved_and_bundles(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "final"
    _fake_arm(out, "baseline", {"a": False, "b": True, "c": True})
    arm = out / "results" / "baseline"
    for tid, cost in (("a", 0.001), ("b", 0.2), ("c", 0.05)):
        f = arm / "baseline" / tid / "1" / "result.json"
        r = json.loads(f.read_text(encoding="utf-8"))
        r["cost_cny"] = cost
        f.write_text(json.dumps(r), encoding="utf-8")
    assert fe.pick_reproduce_task(arm) == "c"
    assert fe.cmd_reproduce(out, task=None, dry_run=True) == 0  # 没有 run.json → 跳过
    (arm / "run.json").write_text("{}", encoding="utf-8")
    assert fe.cmd_reproduce(out, task=None, dry_run=True) == 0
    o = capsys.readouterr().out
    assert "eval reproduce" in o and "--task c" in o and "--live" in o and str(out / "reproduce") in o
    (out / "reproduce").mkdir()
    (out / "reproduce" / "reproduce.md").write_text("x", encoding="utf-8")
    arcs = [a for _, a in fe.bundle_files(out, None)]
    assert "final/reproduce/reproduce.md" in arcs
