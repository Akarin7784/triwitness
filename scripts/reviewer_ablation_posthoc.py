"""W4-14 评审者消融的事后分析。

在 `reviewer_ablation.py score` 的口径之上，补“评审没下结论”的影响、按类别区间、成本与耗时。

用法：
    # 第一次：从 Eva 本机打回来的结果包（解压后的目录，含 ablation/results、ablation/runs、ledger.sqlite）
    # 生成每次运行的账本汇总 ledger_by_run.json（真实花费以账本为准；没下结论的运行最后一次调用不进结果 JSON）
    python scripts/reviewer_ablation_posthoc.py --dir evals/baselines/<date>-reviewer-ablation --bundle <解压目录>
    # 之后：只用入库的 results/ + ledger_by_run.json 复算
    python scripts/reviewer_ablation_posthoc.py --dir evals/baselines/<date>-reviewer-ablation

判定口径同 reviewer_ablation.classify（容差 ±3 行）。“没下结论”= 评审用完 max_turns 仍没调用 submit_review，
编排器里这等于不阻断（放行），所以主口径把它算成：缺陷题漏检、干净题不误报。另给两种敏感性口径：
只看下了结论的运行（valid-only）；把没下结论当阻断（保守口径，干净题记为误报）。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from reviewer_ablation import classify  # noqa: E402

from triwitness.eval.ablation import compare, mde_paired, render_rows, wilson  # noqa: E402

ORDER = ["same", "adversarial", "checklist_t03", "checklist_t10", "consensus_t03", "consensus_t10"]
TOL = 3


def ledger_by_run(bundle: Path) -> dict[str, dict[str, Any]]:
    con = sqlite3.connect(bundle / "ledger.sqlite")
    led = {
        t: {"calls": n, "cost_cny": round(c, 6), "first_ts": a, "last_ts": b, "peak_calls": p}
        for t, n, c, a, b, p in con.execute(
            "select task_id, count(*), sum(cost_cny), min(ts), max(ts), sum(peak) from calls"
            " where category = 'reviewer-ablation' group by task_id"
        )
    }
    out: dict[str, dict[str, Any]] = {}
    for traj in sorted((bundle / "ablation" / "runs").glob("*/trajectory.jsonl")):
        with traj.open(encoding="utf-8") as fh:
            tid = json.loads(fh.readline())["task_id"]
        out[traj.parent.name] = led[tid]
    return out


def _w(k: int, n: int) -> str:
    if not n:
        return "—"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.0%}（{lo:.0%}–{hi:.0%}）"


def load(d: Path) -> dict[str, list[dict[str, Any]]]:
    led = json.loads((d / "ledger_by_run.json").read_text(encoding="utf-8"))
    by: dict[str, list[dict[str, Any]]] = {}
    for p in sorted((d / "results").glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        c = classify(r, TOL)
        r["ok"] = r.get("verdict") is not None
        r["hit"] = bool(c.get("hit"))
        r["block"] = bool(c.get("blocked")) if r["kind"] == "defect" else bool(c.get("fp"))
        r["led"] = led[f"{r['item']}__{r['arm']}__r{r['rep']}"]
        by.setdefault(r["arm"], []).append(r)
    adv = {(r["item"], r["rep"]): r for r in by.get("adversarial", [])}
    for ck in [a for a in list(by) if a.startswith("checklist_")]:
        name = "consensus_" + ck.removeprefix("checklist_")
        for r in by[ck]:
            a = adv[(r["item"], r["rep"])]
            by.setdefault(name, []).append({
                **r, "arm": name, "ok": a["ok"] and r["ok"], "hit": a["hit"] and r["hit"],
                "block": a["block"] and r["block"],
                "cons_block": (a["block"] or not a["ok"]) and (r["block"] or not r["ok"]),
                "led": {"calls": a["led"]["calls"] + r["led"]["calls"],
                        "cost_cny": a["led"]["cost_cny"] + r["led"]["cost_cny"]},
                "elapsed_s": max(a["elapsed_s"], r["elapsed_s"]),  # 两个评审并行跑时的墙钟
            })  # fmt: skip
    for rs in by.values():
        for r in rs:
            r.setdefault("cons_block", r["block"] or not r["ok"])
    return by


def analyse(by: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any], str]:
    arms = [a for a in ORDER if a in by]
    summary: dict[str, Any] = {}
    md = [
        "| 臂 | 检出（位置） | 判阻断（会触发返工） | 误报（blocker） | 误报·保守（没结论也算） | 没下结论 缺陷/干净 "
        "| ¥ 合计（账本） | ¥/次 | 耗时 中位 / P90 / 串行合计 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for arm in arms:
        rs = by[arm]
        d = [r for r in rs if r["kind"] == "defect"]
        c = [r for r in rs if r["kind"] == "clean"]
        dv, cv = [r for r in d if r["ok"]], [r for r in c if r["ok"]]
        el = sorted(float(r["elapsed_s"]) for r in rs)
        cost = sum(float(r["led"]["cost_cny"]) for r in rs)
        s = {
            "n_defect": len(d), "n_clean": len(c),
            "hit": sum(r["hit"] for r in d), "blocked": sum(r["block"] for r in d),
            "fp": sum(r["block"] for r in c), "fp_conservative": sum(r["cons_block"] for r in c),
            "no_verdict_defect": len(d) - len(dv), "no_verdict_clean": len(c) - len(cv),
            "valid_hit": sum(r["hit"] for r in dv), "valid_defect": len(dv),
            "valid_fp": sum(r["block"] for r in cv), "valid_clean": len(cv),
            "calls": sum(int(r["led"]["calls"]) for r in rs), "cost_cny": round(cost, 4),
            "cost_per_review_cny": round(cost / len(rs), 4),
            "elapsed_median_s": round(statistics.median(el), 1),
            "elapsed_p90_s": round(el[max(0, int(0.9 * len(el)) - 1)], 1),
            "elapsed_sum_min": round(sum(el) / 60, 1),
        }  # fmt: skip
        summary[arm] = s
        md.append(
            f"| {arm} | {_w(s['hit'], len(d))} | {_w(s['blocked'], len(d))} | {_w(s['fp'], len(c))} | "
            f"{_w(s['fp_conservative'], len(c))} | {s['no_verdict_defect']} / {s['no_verdict_clean']} | "
            f"{cost:.2f} | {s['cost_per_review_cny']:.3f} | "
            f"{s['elapsed_median_s']:.0f}s / {s['elapsed_p90_s']:.0f}s / {s['elapsed_sum_min']:.0f}min |"
        )
    md += ["", "只看下了结论的运行（valid-only）：", "", "| 臂 | 检出 | 误报 |", "|---|---|---|"]
    for arm in arms:
        s = summary[arm]
        md.append(f"| {arm} | {_w(s['valid_hit'], s['valid_defect'])} | {_w(s['valid_fp'], s['valid_clean'])} |")
    # 按类别（Wilson；每类只有 1–4 题，区间只是提醒样本太小）
    cats = sorted({r["truth"]["category"] for r in by[arms[0]] if r["kind"] == "defect"})
    md += ["", "按缺陷类别的位置检出（Wilson 95%；每类 1–4 题，只作提示）：", "",
           "| 类别 | n | " + " | ".join(arms) + " |", "|---|---|" + "---|" * len(arms)]  # fmt: skip
    per_cat: dict[str, dict[str, list[int]]] = {}
    for cat in cats:
        cells, n = [], 0
        for arm in arms:
            d = [r for r in by[arm] if r["kind"] == "defect" and r["truth"]["category"] == cat]
            n, k = len(d), sum(r["hit"] for r in d)
            per_cat.setdefault(cat, {})[arm] = [k, n]
            lo, hi = wilson(k, n)
            cells.append(f"{k}/{n}（{lo:.0%}–{hi:.0%}）")
        md.append(f"| {cat} | {n} | " + " | ".join(cells) + " |")
    # 保守口径下的配对比较（干净题：没结论也算误报）
    res = {a: {r["item"]: not r["cons_block"] for r in by[a] if r["kind"] == "clean"} for a in arms}
    order = {"adversarial": res.pop("adversarial"), **res}
    md += ["", "保守口径 · 干净补丁放行，对 adversarial 配对（McNemar + Holm + 配对 bootstrap）：", "",
           render_rows(compare(order, "adversarial"), unit="放行")]  # fmt: skip
    n_items = summary[arms[0]]["n_defect"]
    mde1, mde3 = mde_paired(n_items), mde_paired(3 * n_items)
    md += ["", f"每臂 {n_items} 道缺陷题 / {n_items} 道干净题、各 1 次：配对检验在 80% 功效下大约要差 {mde1:.0%} "
           f"才看得出（mde_paired，不一致率按 20% 估）；3 次重复约 {mde3:.0%}。"]  # fmt: skip
    return {"arms": summary, "by_category": per_cat, "tol": TOL}, "\n".join(md) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True, help="基线目录（含 results/）")
    ap.add_argument("--bundle", type=Path, help="解压后的结果包目录（生成 ledger_by_run.json）")
    a = ap.parse_args(argv)
    if a.bundle:
        (a.dir / "ledger_by_run.json").write_text(
            json.dumps(ledger_by_run(a.bundle), ensure_ascii=False, indent=1), encoding="utf-8"
        )
    data, md = analyse(load(a.dir))
    (a.dir / "posthoc.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.dir / "posthoc.md").write_text("# 评审者消融 · 事后分析\n\n" + md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
