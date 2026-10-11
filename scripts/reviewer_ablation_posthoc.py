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
import random
import sqlite3
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from reviewer_ablation import classify  # noqa: E402

from triwitness.eval.ablation import compare, holm, mcnemar, mde_paired, render_rows, wilson  # noqa: E402

ORDER = ["same", "adversarial", "checklist_t03", "checklist_t10", "consensus_t03", "consensus_t10"]
TOL = 3


def ledger_by_run(bundle: Path, existing: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """每次运行的账本汇总。task_id 优先取结果 JSON（第二轮起写入），其次取轨迹第一行；都没有就沿用已入库的记录
    （第二轮结果包只带没结论那几次的轨迹，第一轮的对账已在 ledger_by_run.json 里）。"""
    con = sqlite3.connect(bundle / "ledger.sqlite")
    led = {
        t: {"calls": n, "cost_cny": round(c, 6), "first_ts": a, "last_ts": b, "peak_calls": p}
        for t, n, c, a, b, p in con.execute(
            "select task_id, count(*), sum(cost_cny), min(ts), max(ts), sum(peak) from calls"
            " where category = 'reviewer-ablation' group by task_id"
        )
    }
    out: dict[str, dict[str, Any]] = dict(existing or {})
    for p in sorted((bundle / "ablation" / "results").glob("*.json")):
        tid = json.loads(p.read_text(encoding="utf-8")).get("task_id")
        traj = bundle / "ablation" / "runs" / p.stem / "trajectory.jsonl"
        if tid is None and traj.is_file():
            with traj.open(encoding="utf-8") as fh:
                tid = json.loads(fh.readline())["task_id"]
        if tid is not None and tid in led:
            out[p.stem] = led[tid]
        elif p.stem not in out:
            raise SystemExit(f"{p.stem}：结果里没有 task_id、也没有轨迹和已入库记录，无法对账")
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
        r["last_call"] = bool(r.get("verdict_on_last_call"))
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
    res = {a: {f"{r['item']}#r{r['rep']}": not r["cons_block"] for r in by[a] if r["kind"] == "clean"} for a in arms}
    order = {"adversarial": res.pop("adversarial"), **res}
    md += ["", "保守口径 · 干净补丁放行，对 adversarial 配对（McNemar + Holm + 配对 bootstrap）：", "",
           render_rows(compare(order, "adversarial"), unit="放行")]  # fmt: skip
    n_items = len({r["item"] for r in by[arms[0]] if r["kind"] == "defect"})
    mde1, mde3 = mde_paired(n_items), mde_paired(3 * n_items)
    md += ["", f"每臂 {n_items} 道缺陷题 / {n_items} 道干净题：只跑 1 次的臂，配对检验在 80% 功效下大约要差 {mde1:.0%} "
           f"才看得出（mde_paired，不一致率按 20% 估）；3 次重复（当独立样本算）约 {mde3:.0%}。"]  # fmt: skip
    data: dict[str, Any] = {"arms": summary, "by_category": per_cat, "tol": TOL}
    reps_md, reps_data = _repeats(by)
    if reps_md:
        md += reps_md
        data["repeats"] = reps_data
    return data, "\n".join(md) + "\n"


def _cluster_diff(a: dict[str, list[bool]], b: dict[str, list[bool]], n: int = 10_000) -> tuple[float, float, float]:
    """按题聚类的配对 bootstrap：重抽“题”（同题的几次重复一起进出），统计 b − a 的比例差。"""
    items = sorted(set(a) & set(b))
    rng = random.Random(0)

    def diff(sample: list[str]) -> float:
        xa = [v for it in sample for v in a[it]]
        xb = [v for it in sample for v in b[it]]
        return sum(xb) / len(xb) - sum(xa) / len(xa)

    stats = sorted(diff([rng.choice(items) for _ in items]) for _ in range(n))
    return diff(items), stats[int(0.025 * n)], stats[int(0.975 * n) - 1]


def _repeats(by: dict[str, list[dict[str, Any]]]) -> tuple[list[str], dict[str, Any]]:
    """有重复（rep ≥ 1）的臂：逐次稳定性、按题聚类的差值区间，以及按第一轮口径（最后一次调用里的提交算没结论）复算。"""
    arms = [a for a in ("adversarial", "checklist_t10") if a in by and len({r["rep"] for r in by[a]}) > 1]
    if not arms:
        return [], {}
    md = ["", "## 重复（按次与按题聚类）", "", "| 臂 | 次 | 检出 | 误报 | 没下结论 | 最后一次调用才提交 |",
          "|---|---|---|---|---|---|"]  # fmt: skip
    data: dict[str, Any] = {"per_rep": {}}
    for arm in arms:
        for rep in sorted({r["rep"] for r in by[arm]}):
            rs = [r for r in by[arm] if r["rep"] == rep]
            d = [r for r in rs if r["kind"] == "defect"]
            c = [r for r in rs if r["kind"] == "clean"]
            row = {"hit": sum(r["hit"] for r in d), "n_defect": len(d), "fp": sum(r["block"] for r in c),
                   "n_clean": len(c), "no_verdict": sum(not r["ok"] for r in rs),
                   "last_call": sum(r["last_call"] for r in rs)}  # fmt: skip
            data["per_rep"][f"{arm}#r{rep}"] = row
            md.append(f"| {arm} | r{rep} | {_w(row['hit'], len(d))} | {_w(row['fp'], len(c))} | "
                      f"{row['no_verdict']} | {row['last_call']} |")  # fmt: skip
    if len(arms) == 2:

        def per_item(arm: str, kind: str, key: str, legacy: bool = False) -> dict[str, list[bool]]:
            out: dict[str, list[bool]] = {}
            for r in by[arm]:
                if r["kind"] != kind:
                    continue
                v = bool(r[key]) and not (legacy and r["last_call"])  # 第一轮口径：最后一次才提交 = 没结论
                out.setdefault(r["item"], []).append(v if kind == "defect" else not v)
            return out

        md += ["", "checklist_t10 − adversarial（按题聚类 bootstrap 95%，越高越好）：", "",
               "| 指标 | 口径 | 差值 | 区间 |", "|---|---|---|---|"]  # fmt: skip
        for kind, key, title in (("defect", "hit", "检出"), ("clean", "block", "干净放行")):
            for legacy in (False, True):
                d0, lo, hi = _cluster_diff(per_item("adversarial", kind, key, legacy),
                                           per_item("checklist_t10", kind, key, legacy))  # fmt: skip
                tag = "第一轮口径" if legacy else "当前"
                data[f"diff_{key}{'_legacy' if legacy else ''}"] = [round(d0, 4), round(lo, 4), round(hi, 4)]
                md.append(f"| {title} | {tag} | {d0:+.0%} | {lo:+.0%}～{hi:+.0%} |")
        # 只看 r1+ 的当前口径（r0 的记账缺口让“最后一次才提交”记成了没结论，两种口径在 r0 上无法区分）
        later = {r["rep"] for r in by["adversarial"]} - {0}
        if later:
            sub = {a: [r for r in by[a] if r["rep"] in later] for a in arms}
            for kind, key, title in (("defect", "hit", "检出"), ("clean", "block", "干净放行")):
                pa = _per_item(sub["adversarial"], kind, key)
                pb = _per_item(sub["checklist_t10"], kind, key)
                d0, lo, hi = _cluster_diff(pa, pb)
                data[f"diff_{key}_later"] = [round(d0, 4), round(lo, 4), round(hi, 4)]
                tag = f"只看 r{min(later)}–r{max(later)}（当前口径）"
                md.append(f"| {title} | {tag} | {d0:+.0%} | {lo:+.0%}～{hi:+.0%} |")
        md.append("\n区间不含 0 才算有差异；同一题的几次重复不独立，所以按题重抽。")
        md += _inconclusive(by, arms, data)
        md += _majority(by, data)
        md += _discordant(by, data)
    return md, data


def _per_item(rs: list[dict[str, Any]], kind: str, key: str) -> dict[str, list[bool]]:
    out: dict[str, list[bool]] = {}
    for r in rs:
        if r["kind"] == kind:
            v = bool(r[key])
            out.setdefault(r["item"], []).append(v if kind == "defect" else not v)
    return out


def _inconclusive(by: dict[str, list[dict[str, Any]]], arms: list[str], data: dict[str, Any]) -> list[str]:
    """没下结论率（第一轮口径：最后一次调用才提交也算没结论，三次重复可比）。"""
    md = ["", "没下结论率（第一轮口径，所有重复合并；Wilson 95%）：", "", "| 臂 | 缺陷题 | 干净题 | 合计 |",
          "|---|---|---|---|"]  # fmt: skip
    rate: dict[str, Any] = {}
    for arm in arms:
        rs = by[arm]
        nv = {k: [r for r in rs if r["kind"] == k] for k in ("defect", "clean")}
        cnt = {k: sum((not r["ok"]) or r["last_call"] for r in v) for k, v in nv.items()}
        tot = cnt["defect"] + cnt["clean"]
        rate[arm] = {"defect": [cnt["defect"], len(nv["defect"])], "clean": [cnt["clean"], len(nv["clean"])],
                     "all": [tot, len(rs)]}  # fmt: skip
        md.append(f"| {arm} | {_w(cnt['defect'], len(nv['defect']))} | {_w(cnt['clean'], len(nv['clean']))} | "
                  f"{_w(tot, len(rs))} |")  # fmt: skip
    ia = _per_item_flag(by["adversarial"])
    ib = _per_item_flag(by["checklist_t10"])
    d0, lo, hi = _cluster_diff(ia, ib)
    rate["diff_checklist_minus_adversarial"] = [round(d0, 4), round(lo, 4), round(hi, 4)]
    md.append(
        f"\nchecklist_t10 − adversarial 没下结论率：{d0:+.0%}（按题聚类 bootstrap {lo:+.0%}～{hi:+.0%}，越低越好）。"
    )
    data["inconclusive"] = rate
    return md


def _per_item_flag(rs: list[dict[str, Any]]) -> dict[str, list[bool]]:
    out: dict[str, list[bool]] = {}
    for r in rs:
        out.setdefault(r["item"], []).append((not r["ok"]) or r["last_call"])
    return out


def _majority(by: dict[str, list[dict[str, Any]]], data: dict[str, Any]) -> list[str]:
    """按题多数（过半重复成立）后做 McNemar，三个指标一起 Holm；
    另给逐次合并（item#rep 配对，不独立，只作参考）。"""
    arms = ("adversarial", "checklist_t10")
    metrics = (("defect", "hit", "检出"), ("clean", "block", "干净放行"), ("clean", "cons_block", "干净放行·保守"))
    rows: list[tuple[str, str, Any, int, int]] = []
    for kind, key, title in metrics:
        maj, pool = [], []
        for arm in arms:
            per = _per_item(by[arm], kind, key)
            maj.append({it: sum(v) * 2 > len(v) for it, v in per.items()})
            pool.append({f"{r['item']}#r{r['rep']}": (bool(r[key]) if kind == "defect" else not r[key])
                         for r in by[arm] if r["kind"] == kind})  # fmt: skip
        for tag, (a, b) in (("按题多数", maj), ("逐次合并", pool)):
            common = sorted(set(a) & set(b))
            t = mcnemar([a[k] for k in common], [b[k] for k in common])
            rows.append((title, tag, t, sum(a[k] for k in common), sum(b[k] for k in common)))
    md = ["", "checklist_t10 对 adversarial 的 McNemar（b = 只有 adversarial 成立，c = 只有 checklist_t10 成立；"
          "Holm 在同一配对方式的 3 个指标内校正）：", "",
          "| 指标 | 配对方式 | adversarial | checklist_t10 | b/c | p（精确） | p（Holm） |",
          "|---|---|---|---|---|---|---|"]  # fmt: skip
    out: dict[str, Any] = {}
    for tag in ("按题多数", "逐次合并"):
        sel = [r for r in rows if r[1] == tag]
        for (title, _, t, ka, kb), ph in zip(sel, holm([r[2].p_exact for r in sel]), strict=True):
            out[f"{tag}/{title}"] = {"adversarial": [ka, t.n], "checklist_t10": [kb, t.n], "b": t.b, "c": t.c,
                                    "p": t.p_exact, "p_holm": ph}  # fmt: skip
            md.append(f"| {title} | {tag} | {ka}/{t.n} | {kb}/{t.n} | {t.b}/{t.c} | {t.p_exact:.3f} | {ph:.3f} |")
    md.append("\n逐次合并把同一题的 3 次当成独立样本，p 值偏乐观，只作参考；以按题多数和按题聚类区间为准。")
    data["mcnemar"] = out
    return md


def _discordant(by: dict[str, list[dict[str, Any]]], data: dict[str, Any]) -> list[str]:
    """逐题对比：两臂在 3 次里成立次数不同的题。"""
    rows: list[tuple[str, str, str, str]] = []
    out: dict[str, Any] = {}
    for kind, key, title in (("defect", "hit", "检出"), ("clean", "block", "放行")):
        pa = _per_item(by["adversarial"], kind, key)
        pb = _per_item(by["checklist_t10"], kind, key)
        for it in sorted(set(pa) & set(pb)):
            ka, kb = sum(pa[it]), sum(pb[it])
            if ka != kb:
                rows.append((it, title, f"{ka}/{len(pa[it])}", f"{kb}/{len(pb[it])}"))
                out[it] = {"metric": key, "adversarial": [ka, len(pa[it])],
                                       "checklist_t10": [kb, len(pb[it])]}  # fmt: skip
    md = ["", f"逐题对比（两臂成立次数不同的 {len(rows)} 题；其余各题两臂一致）：", "",
          "| 题 | 指标 | adversarial | checklist_t10 |", "|---|---|---|---|"]  # fmt: skip
    md += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    data["discordant_items"] = out
    return md


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True, help="基线目录（含 results/）")
    ap.add_argument("--bundle", type=Path, help="解压后的结果包目录（生成 ledger_by_run.json）")
    a = ap.parse_args(argv)
    if a.bundle:
        led_path = a.dir / "ledger_by_run.json"
        existing = json.loads(led_path.read_text(encoding="utf-8")) if led_path.is_file() else None
        led_path.write_text(json.dumps(ledger_by_run(a.bundle, existing), ensure_ascii=False, indent=1),
                            encoding="utf-8")  # fmt: skip
    data, md = analyse(load(a.dir))
    (a.dir / "posthoc.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.dir / "posthoc.md").write_text("# 评审者消融 · 事后分析\n\n" + md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
