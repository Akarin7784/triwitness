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
