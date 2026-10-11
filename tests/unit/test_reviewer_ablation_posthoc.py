"""W4-14 事后分析：用入库的 2026-10-12 结果复算，口径与 score 一致（不真调模型）。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "evals" / "baselines" / "2026-10-12-reviewer-ablation"
spec = importlib.util.spec_from_file_location(
    "reviewer_ablation_posthoc", ROOT / "scripts" / "reviewer_ablation_posthoc.py"
)
assert spec and spec.loader
ph = importlib.util.module_from_spec(spec)
sys.modules["reviewer_ablation_posthoc"] = ph
spec.loader.exec_module(ph)


def test_posthoc_matches_score_and_ledger() -> None:
    data, md = ph.analyse(ph.load(BASE))
    arms = data["arms"]
    score = json.loads((BASE / "summary.json").read_text(encoding="utf-8"))
    for arm, s in score.items():  # 主口径与 reviewer_ablation.score 一致
        assert arms[arm]["hit"] == s["hit"], arm
        assert arms[arm]["fp"] == s["fp"], arm
    led = json.loads((BASE / "ledger_by_run.json").read_text(encoding="utf-8"))
    total = sum(arms[a]["cost_cny"] for a in ("same", "adversarial", "checklist_t03", "checklist_t10"))
    assert abs(total - sum(v["cost_cny"] for v in led.values())) < 0.01
    assert all(v["peak_calls"] == 0 for v in led.values())
    # 共识只在两边都阻断时阻断 → 误报不多于任一单臂
    assert arms["consensus_t10"]["fp"] <= min(arms["adversarial"]["fp"], arms["checklist_t10"]["fp"])
    assert "valid-only" in md


def _fake_repeats(tmp: Path) -> Path:
    """用第一轮结果造 r1 / r2（adversarial、checklist_t10），模拟第二轮合并后的目录。"""
    import shutil

    d = tmp / "base"
    (d / "results").mkdir(parents=True)
    for p in (BASE / "results").glob("*__r0.json"):  # 只取第一轮，r1 / r2 用 r0 复制出来
        shutil.copy(p, d / "results" / p.name)
    led = json.loads((BASE / "ledger_by_run.json").read_text(encoding="utf-8"))
    for p in sorted((BASE / "results").glob("*__r0.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if r["arm"] not in ("adversarial", "checklist_t10"):
            continue
        for rep in (1, 2):
            stem = f"{r['item']}__{r['arm']}__r{rep}"
            (d / "results" / f"{stem}.json").write_text(json.dumps({**r, "rep": rep}), encoding="utf-8")
            led[stem] = led[p.stem]
    (d / "ledger_by_run.json").write_text(json.dumps(led), encoding="utf-8")
    return d


def test_posthoc_repeats_section(tmp_path: Path) -> None:
    data, md = ph.analyse(ph.load(_fake_repeats(tmp_path)))
    assert data["arms"]["adversarial"]["n_defect"] == 60 and data["arms"]["same"]["n_defect"] == 20
    assert set(data["repeats"]["per_rep"]) == {f"{a}#r{r}" for a in ("adversarial", "checklist_t10") for r in (0, 1, 2)}
    d0, lo, hi = data["repeats"]["diff_hit"]
    assert lo <= d0 <= hi and abs(d0 - 0.05) < 1e-9  # 三次完全相同 → 差值等于第一轮的 90% − 85%
    assert "按题聚类" in md
    assert data["repeats"]["discordant_items"]  # 第一轮两臂有 3 题不一致，复制后仍然不一致
    assert data["repeats"]["mcnemar"]["按题多数/检出"]["adversarial"][1] == 20


def test_posthoc_round2_merged() -> None:
    """入库的第一轮 + 第二轮（Eva 本机，r1 / r2）合并：两臂各 3 次，账本对得上，结论与 README 一致。"""
    data, md = ph.analyse(ph.load(BASE))
    arms = data["arms"]
    assert arms["adversarial"]["n_defect"] == arms["checklist_t10"]["n_defect"] == 60
    assert arms["adversarial"]["hit"] == arms["checklist_t10"]["hit"] == 49
    led = json.loads((BASE / "ledger_by_run.json").read_text(encoding="utf-8"))
    assert len(led) == 320 and abs(sum(v["cost_cny"] for v in led.values()) - 18.9878) < 1e-3
    rep = data["repeats"]
    assert all(m["p_holm"] >= 0.05 for k, m in rep["mcnemar"].items() if k.startswith("按题多数"))
    _lo, hi = rep["inconclusive"]["diff_checklist_minus_adversarial"][1:]
    assert hi < 0  # checklist_t10 没下结论显著更少
    assert "逐题对比" in md


def test_ledger_by_run_prefers_task_id_and_keeps_existing(tmp_path: Path) -> None:
    import sqlite3

    b = tmp_path / "bundle"
    (b / "ablation" / "results").mkdir(parents=True)
    con = sqlite3.connect(b / "ledger.sqlite")
    con.execute("create table calls (task_id text, cost_cny real, ts text, peak int, category text)")
    con.executemany("insert into calls values (?, ?, ?, 0, 'reviewer-ablation')",
                    [("t_new", 0.01, "2026-10-12T00:00:00"), ("t_new", 0.02, "2026-10-12T00:01:00")])  # fmt: skip
    con.commit()
    con.close()
    (b / "ablation" / "results" / "d01-clean__adversarial__r1.json").write_text('{"task_id": "t_new"}')
    (b / "ablation" / "results" / "d01-clean__adversarial__r0.json").write_text("{}")
    old = {"d01-clean__adversarial__r0": {"calls": 3, "cost_cny": 0.5}}
    out = ph.ledger_by_run(b, old)
    assert out["d01-clean__adversarial__r0"] == old["d01-clean__adversarial__r0"]
    assert out["d01-clean__adversarial__r1"]["calls"] == 2
    assert abs(out["d01-clean__adversarial__r1"]["cost_cny"] - 0.03) < 1e-9
