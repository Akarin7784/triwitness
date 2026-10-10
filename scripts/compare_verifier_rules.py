# ruff: noqa: E501
"""W3-14 后续：同一批 W2-25 补丁，旧确定性档（W3-14）vs 新规则确定性档，逐 attempt 对比。

用法：uv run python scripts/compare_verifier_rules.py --old evals/baselines/2026-10-10-w3-verifier/test ... \
      --new evals/results/2026-10-10-w3-rules-test ... --out evals/baselines/2026-10-10-w3-rules
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

INFRA = {"swe-ultraplot-696", "swe-xcp_d-1433"}


def load(dirs: list[Path]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        for v in sorted(d.glob("*+deterministic/*/*/verification.json")):
            r = json.loads((v.parent / "result.json").read_text(encoding="utf-8"))
            if r["task_id"] in INFRA:
                continue
            out[r["task_id"]] = {
                "v": json.loads(v.read_text(encoding="utf-8")),
                "r": r,
                "set": d.name.rsplit("-", 1)[-1],
            }
    return out


def blind(v: dict[str, Any]) -> bool:
    runs = [t for t in v.get("test_runs", []) if t["scope"] in ("full", "related")]
    return bool(runs) and all(t["passed"] == 0 for t in runs)


def metrics(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tp = sum(1 for x in rows.values() if x["v"]["verdict"] == "pass" and x["r"]["resolved"])
    vp = sum(1 for x in rows.values() if x["v"]["verdict"] == "pass")
    res = sum(1 for x in rows.values() if x["r"]["resolved"])
    fs = [k for k, x in rows.items() if x["r"].get("false_success")]
    return {
        "n": len(rows),
        "verified_pass": vp,
        "true_pass": tp,
        "resolved": res,
        "precision": round(tp / vp, 4) if vp else None,
        "recall": round(tp / res, 4) if res else None,
        "false_pass": vp - tp,
        "false_alarm": res - tp,
        "known_false_success": len(fs),
        "false_success_caught": sum(1 for k in fs if rows[k]["v"]["verdict"] != "pass"),
        "false_success_missed": sorted(k for k in fs if rows[k]["v"]["verdict"] == "pass"),
        "blind_regression": sorted(k for k, x in rows.items() if blind(x["v"])),
        "related_scope": sorted(
            k for k, x in rows.items() if any(t["scope"] == "related" for t in x["v"].get("test_runs", []))
        ),
        "skip_flagged": sorted(
            k
            for k, x in rows.items()
            if any("skip_or_xfail_added" in str(f) for f in x["v"].get("anticheat_flags", []))
        ),
        "by_risk": {
            lv: f"{sum(1 for x in rows.values() if x['v']['risk_level'] == lv and x['r']['resolved'])}/{sum(1 for x in rows.values() if x['v']['risk_level'] == lv)}"
            for lv in ("L0", "L1", "L2", "L3")
        },
        "verdicts": dict(Counter(x["v"]["verdict"] for x in rows.values())),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", nargs="+", type=Path, required=True)
    ap.add_argument("--new", nargs="+", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    old, new = load(a.old), load(a.new)
    common = sorted(set(old) & set(new))
    old, new = {k: old[k] for k in common}, {k: new[k] for k in common}
    changes = [
        {
            "task": k,
            "set": new[k]["set"],
            "resolved": new[k]["r"]["resolved"],
            "false_success": bool(new[k]["r"].get("false_success")),
            "old": f"{old[k]['v']['verdict']}/{old[k]['v']['risk_level']}",
            "new": f"{new[k]['v']['verdict']}/{new[k]['v']['risk_level']}",
            "new_reasons": new[k]["v"].get("reasons", [])[:3],
        }
        for k in common
        if (old[k]["v"]["verdict"], old[k]["v"]["risk_level"]) != (new[k]["v"]["verdict"], new[k]["v"]["risk_level"])
    ]
    res = {"old": metrics(old), "new": metrics(new), "changes": changes}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "compare.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    o, n = res["old"], res["new"]

    def pct(x: float | None) -> str:
        return "—" if x is None else f"{x:.0%}"

    lines = [
        f"# 确定性档：W3-14（旧规则）vs W3-14 后续（新规则），同一批 {n['n']} 个 attempt（去 2 infra）\n",
        "| 指标 | 旧 | 新 |",
        "|---|---|---|",
        f"| 判 pass | {o['verified_pass']} | {n['verified_pass']} |",
        f"| 精确率 | {pct(o['precision'])} | {pct(n['precision'])} |",
        f"| 召回率 | {pct(o['recall'])} | {pct(n['recall'])} |",
        f"| 放过的假成功 | {o['false_pass']} | {n['false_pass']} |",
        f"| 误报（真解决却没判 pass） | {o['false_alarm']} | {n['false_alarm']} |",
        f"| 已知假成功拦下 | {o['false_success_caught']}/{o['known_false_success']} | {n['false_success_caught']}/{n['known_false_success']} |",
        f"| 回归盲区（全量/相关 0 通过） | {len(o['blind_regression'])} | {len(n['blind_regression'])} |",
        f"| 回退到相关测试 | {len(o['related_scope'])} | {len(n['related_scope'])} |",
        f"| skip/xfail 标记 | {len(o['skip_flagged'])} | {len(n['skip_flagged'])} |",
        f"| 风险 L0/L1/L2/L3 → 实际解决 | {' · '.join(o['by_risk'].values())} | {' · '.join(n['by_risk'].values())} |",
        "",
        f"放过的假成功：旧 {', '.join(o['false_success_missed']) or '无'}；新 {', '.join(n['false_success_missed']) or '无'}",
        "",
        "## 结论变化的 attempt",
        "",
        "| 任务 | 集 | 真值 | 旧 | 新 | 新理由（前 3 条） |",
        "|---|---|---|---|---|---|",
    ]
    for c in changes:
        truth = "假成功" if c["false_success"] else ("解决" if c["resolved"] else "未解决")
        lines.append(
            f"| {c['task']} | {c['set']} | {truth} | {c['old']} | {c['new']} | {'；'.join(c['new_reasons'])[:160]} |"
        )
    (a.out / "compare.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
