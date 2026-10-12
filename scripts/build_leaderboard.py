"""从已入库的 evals/baselines 生成 site/data.json（静态 Leaderboard 数据，¥0）。

用法：uv run python scripts/build_leaderboard.py
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evals" / "baselines"


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def final_rows() -> list[dict]:
    d = BASE / "2026-10-12-final-w8"
    analysis = json.loads((d / "analysis.json").read_text(encoding="utf-8"))
    names = {"baseline": "单 Executor（long-context-1m）", "orchestrated": "完整流水线（orchestrated-1m）"}
    rows = []
    for arm, label in names.items():
        r = json.loads((d / arm / "report.json").read_text(encoding="utf-8"))["rows"][0]
        a = analysis["arms"][arm]
        k, n = r["solved"], r["graded"]
        rows.append(
            {
                "suite": "test（35）",
                "config": label,
                "model": "deepseek-flash（非思考）",
                "snapshot": "deepseek-flash",
                "solved": k,
                "graded": n,
                "resolved": round(k / n, 4),
                "ci": wilson(k, n),
                "cost_per_task": r["avg_cost_per_task"],
                "cost_per_task_idle": a["off_peak_per_task"],
                "cost_per_solved_idle": a["off_peak_per_resolved"],
                "cache_hit": r["cache_hit_rate"],
                "false_success": r["false_success"],
                "false_success_rate": round(r["false_success"] / n, 4),
                "avg_steps": r["avg_steps"],
                "date": "2026-10-12",
                "source": "evals/baselines/2026-10-12-final-w8/",
            }
        )
    return rows


def ofat_rows() -> list[dict]:
    d = BASE / "2026-10-12-ofat-w5"
    agg: dict[str, list[dict]] = defaultdict(list)
    with (d / "runs.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            agg[row["config"]].append(row)
    rows = []
    for cfg, rs in agg.items():
        if cfg == "w2-reference":
            continue
        n = len(rs)
        k = sum(r["resolved"] == "True" for r in rs)
        cost = sum(float(r["result_cny"] or 0) for r in rs)
        fs = sum(r["false_success"] == "True" for r in rs)
        rows.append(
            {
                "suite": "dev（15）",
                "config": cfg.replace("w5-round1--", "OFAT: ").replace("w5-round1", "OFAT 基线"),
                "model": "deepseek-flash",
                "snapshot": "deepseek-flash",
                "solved": k,
                "graded": n,
                "resolved": round(k / n, 4),
                "ci": wilson(k, n),
                "cost_per_task": round(cost / n, 4),
                "cost_per_task_idle": None,
                "cost_per_solved_idle": None,
                "cost_per_solved": round(cost / k, 4) if k else None,
                "cache_hit": None,
                "false_success": fs,
                "false_success_rate": round(fs / n, 4),
                "avg_steps": round(sum(int(r["steps"] or 0) for r in rs) / n, 1),
                "date": "2026-10-12",
                "source": "evals/baselines/2026-10-12-ofat-w5/",
            }
        )
    return rows


def main() -> None:
    final = json.loads((BASE / "2026-10-12-final-w8" / "summary.json").read_text(encoding="utf-8"))
    data = {
        "generated_from": "evals/baselines（scripts/build_leaderboard.py）",
        "pricing": "configs/pricing.yaml verified_at 2026-10-10",
        "paired_final": final.get("paired"),
        "rows": final_rows() + ofat_rows(),
        "vendors_reserved": ["Anthropic", "OpenAI", "Qwen"],
    }
    out = ROOT / "site" / "data.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"写入 {out}（{len(data['rows'])} 行）")


if __name__ == "__main__":
    main()
