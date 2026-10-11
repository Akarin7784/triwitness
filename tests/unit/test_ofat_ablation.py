"""W5-09/10/11 OFAT 消融脚本：生成配置、高峰暂停、报告（不调用模型）。"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ofat_ablation", ROOT / "scripts" / "ofat_ablation.py")
assert _spec and _spec.loader
oa = importlib.util.module_from_spec(_spec)
sys.modules["ofat_ablation"] = oa
_spec.loader.exec_module(oa)

SPEC = ROOT / "evals" / "ablations" / "w5-round1.yaml"


def test_plan_generates_loadable_flash_only_configs(tmp_path: Path) -> None:
    from triwitness.eval.runner import RunConfig
    from triwitness.harness.config import HarnessConfig

    plan = oa.cmd_plan(SPEC, tmp_path, 1)
    names = [p["name"] for p in plan]
    assert names[0] == "w5-round1" and len(names) == len(set(names)) == 10
    assert "w5-round1--planner-enabled" in names and "w5-round1--thinking-high" in names
    for p in sorted((tmp_path / "configs").glob("*.yaml")):
        cfg = RunConfig.load(p)
        assert cfg.executor["model"] == "deepseek-flash" and cfg.category == oa.CATEGORY
        HarnessConfig.load(cfg.harness.removeprefix("configs/"))  # type: ignore[union-attr]
    est = json.loads((tmp_path / "plan.json").read_text())["estimate_cny"]
    assert 8 < est < 15


def test_peak_guard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert oa.is_peak(datetime(2026, 10, 12, 10, 0, tzinfo=oa.BJ))  # 周一 10:00
    assert not oa.is_peak(datetime(2026, 10, 12, 12, 30, tzinfo=oa.BJ))
    assert not oa.is_peak(datetime(2026, 10, 11, 10, 0, tzinfo=oa.BJ))  # 周日
    monkeypatch.setattr(oa, "is_peak", lambda now=None: True)
    calls: list[object] = []
    monkeypatch.setattr(oa.subprocess, "run", lambda *a, **k: calls.append(a))
    rc = oa.cmd_run(SPEC, tmp_path, concurrency=3, attempts=1, only=None, tasks=None, allow_peak=False, dry_run=False)
    assert rc == oa.PEAK_EXIT and calls == []


def _write(run: Path, cfg: str, outcomes: dict[str, bool]) -> None:
    for t, ok in outcomes.items():
        d = run / cfg / t / "1"
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps({"task_id": t, "attempt": 1, "resolved": ok, "cost_cny": 0.05}))


def test_report_pairs_against_rerun_baseline(tmp_path: Path) -> None:
    tasks = [f"t{i}" for i in range(20)]
    _write(tmp_path / "results" / "w5-round1", "w5-round1", {t: i < 10 for i, t in enumerate(tasks)})
    _write(tmp_path / "results" / "w5-round1--planner-enabled", "w5-round1--planner-enabled",
           {t: True for t in tasks})  # fmt: skip
    rep = oa.cmd_report(SPEC, tmp_path).read_text(encoding="utf-8")
    row = next(ln for ln in rep.splitlines() if ln.startswith("| w5-round1--planner-enabled"))
    assert "20/20" in row and "0/10" in row and "更好" in row
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["costs"]["w5-round1"] == 1.0 and summary["total_cny"] == 2.0
    assert "W2 基线" in rep  # 次要对照


def test_bundle_includes_ledger(tmp_path: Path) -> None:
    out = tmp_path / "ofat"
    _write(out / "results" / "b", "b", {"t": True})
    ledger = tmp_path / "ledger.sqlite"
    ledger.write_bytes(b"x")
    dest = oa.cmd_bundle(out, ledger)
    import zipfile

    names = zipfile.ZipFile(dest).namelist()
    assert "ledger.sqlite" in names and any(n.endswith("result.json") for n in names)
