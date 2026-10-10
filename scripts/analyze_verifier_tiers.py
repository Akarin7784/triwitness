# ruff: noqa: E501
"""W3-14：verifier 三档对比分析（读 `tw eval reverify` 的输出目录，不调用 API）。

用法：uv run python scripts/analyze_verifier_tiers.py <reverify 目录>... --out <目录>
输出 analysis.json + analysis.md：
- 每档精确率 / 召回率（以隐藏测试 resolved 为真值；none 档 = 采信 Agent 自称）；
- 已知假成功的拦截情况与拦截信号；真正解决的补丁上的误报；
- model 档 3 次判读的一致性（全票一致率、翻转、Fleiss κ）；花费；风险等级 → 实际通过率。
infra_error（判分没产出 reward）不计入。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from triwitness.eval.report import classify, load_results
from triwitness.eval.runner import AttemptResult

KNOWN_FALSE_SUCCESS = [
    "swe-canvasapi-716",
    "swe-conan-19750",
    "swe-django-components-489",
    "swe-llm-sandbox-101",
    "swe-loguru-1306",
    "swe-microsoft-authentication-library-for-python-730",
    "swe-crosstl-257",
    "swe-h-transport-materials-224",
]
TIERS = ("none", "deterministic", "model")
EDIT_FLAGS = {"existing_test_modified", "existing_test_extended", "assertion_weakened", "test_deleted"}


def signals(v: dict[str, Any], r: AttemptResult) -> list[str]:
    """哪些信号让验证器没放行（verdict != pass）。"""
    out: list[str] = []
    rs = " ".join(v.get("reasons", []))
    if "防作弊阻断" in rs:
        out.append("anticheat")
    if "复现测试在修复后仍失败" in rs:
        out.append("repro_rerun")
    if "新增失败" in rs:
        out.append("regression")
    if v.get("repro_status") not in ("reproduced",) and "复现状态" in rs:
        out.append("repro_missing")
    if v.get("claim_flags"):
        out.append("claim_audit")
    elif "声明审计" in rs:
        out.append("claim_not_asserted")  # Agent 自己没声称通过（tests_passed=false 等）
    if v.get("deterministic") == "pass" and v.get("model_verdict") not in (None, "pass"):
        out.append("model")
    return out


def edited_tests(v: dict[str, Any], r: AttemptResult) -> bool:
    return bool(EDIT_FLAGS & set(v.get("anticheat_flags", []))) or bool(r.edited_paths) or bool(r.tamper_paths)


def fleiss_kappa(rows: list[list[str]], cats: tuple[str, ...] = ("pass", "inconclusive", "fail")) -> float | None:
    rows = [x for x in rows if len(x) >= 2]
    if not rows or len({len(x) for x in rows}) != 1:
        return None
    n, k = len(rows[0]), len(rows)
    p_i = [(sum(x.count(c) ** 2 for c in cats) - n) / (n * (n - 1)) for x in rows]
    p_bar = sum(p_i) / k
    p_j = [sum(x.count(c) for x in rows) / (k * n) for c in cats]
    pe = sum(p * p for p in p_j)
    return round((p_bar - pe) / (1 - pe), 4) if pe < 1 else 1.0


def pr(rows: list[tuple[bool, bool]]) -> dict[str, Any]:
    """rows：(resolved, verifier_pass)。"""
    vp = [x for x in rows if x[1]]
    tp = sum(x[0] for x in vp)
    res = sum(x[0] for x in rows)
    return {
        "n": len(rows),
        "verified_pass": len(vp),
        "true_pass": tp,
        "resolved": res,
        "precision": round(tp / len(vp), 4) if vp else None,
        "recall": round(tp / res, 4) if res else None,
        "false_pass": len(vp) - tp,
        "false_alarm": res - tp,
    }


def load(dirs: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for d in dirs:
        for r in load_results(d):
            base, tier = r.config.rsplit("+", 1)
            vp = d / r.config / r.task_id / str(r.attempt) / "verification.json"
            v = json.loads(vp.read_text(encoding="utf-8")) if vp.is_file() else {}
            rows.append(
                {
                    "set": d.name.rsplit("-", 1)[-1],
                    "config": base,
                    "tier": tier,
                    "task": r.task_id,
                    "r": r,
                    "v": v,
                    "infra": classify(r) == "infra_error",
                }
            )
    return rows


def analyze(dirs: list[Path]) -> dict[str, Any]:
    rows = [x for x in load(dirs) if not x["infra"]]
    infra = sorted({x["task"] for x in load(dirs) if x["infra"]})
    out: dict[str, Any] = {"sources": [str(d) for d in dirs], "infra_excluded": infra, "tiers": {}}
    for tier in TIERS:
        xs = [x for x in rows if x["tier"] == tier]
        if not xs:
            continue
        with_patch = [x for x in xs if x["v"].get("reasons") != ["没有改动"]]

        def ok(x: dict[str, Any], tier: str = tier) -> bool:
            return x["r"].agent_claimed_success if tier == "none" else x["v"].get("verdict") == "pass"

        t: dict[str, Any] = {
            "all": pr([(x["r"].resolved, ok(x)) for x in xs]),
            "by_set": {
                s: pr([(x["r"].resolved, ok(x)) for x in xs if x["set"] == s]) for s in sorted({x["set"] for x in xs})
            },
            "attempts_with_patch": len(with_patch),
            "verdicts": dict(
                Counter(("pass" if ok(x) else "not_pass") if tier == "none" else x["v"].get("verdict") for x in xs)
            ),
            "cost_cny": round(sum(x["v"].get("cost_cny", 0.0) for x in xs), 6),
        }
        fs = {}
        for tid in KNOWN_FALSE_SUCCESS:
            m = next((x for x in xs if x["task"] == tid), None)
            if m is None:
                fs[tid] = None
                continue
            caught = not ok(m)
            fs[tid] = {
                "set": m["set"],
                "verdict": "agent_claim" if tier == "none" else m["v"].get("verdict"),
                "caught": caught,
                "risk": m["v"].get("risk_level"),
                "signals": signals(m["v"], m["r"]) if caught and tier != "none" else [],
                "edited_existing_tests": edited_tests(m["v"], m["r"]),
                "model_judgments": [j["verdict"] for j in m["v"].get("model_judgments", [])],
            }
        t["known_false_success"] = fs
        t["known_false_success_caught"] = sum(1 for v in fs.values() if v and v["caught"])
        t["false_alarms"] = [
            {
                "task": x["task"],
                "set": x["set"],
                "verdict": x["v"].get("verdict"),
                "risk": x["v"].get("risk_level"),
                "signals": signals(x["v"], x["r"]),
                "model_judgments": [j["verdict"] for j in x["v"].get("model_judgments", [])],
            }
            for x in xs
            if x["r"].resolved and not ok(x) and tier != "none"
        ]
        if tier == "none":
            t["false_alarms"] = [{"task": x["task"], "set": x["set"]} for x in xs if x["r"].resolved and not ok(x)]
        # 风险等级 → 实际通过率
        by: dict[str, list[bool]] = {}
        for x in xs:
            lv = x["v"].get("risk_level")
            if lv:
                by.setdefault(lv, []).append(x["r"].resolved)
        t["by_risk"] = {
            lv: {"n": len(v), "resolved": sum(v), "pass_rate": round(sum(v) / len(v), 4)}
            for lv, v in sorted(by.items())
        }
        # 拦截信号分布（所有没放行、且隐藏测试也不过的 attempt）
        sig = Counter(
            s for x in xs if not x["r"].resolved and not ok(x) and tier != "none" for s in signals(x["v"], x["r"])
        )
        t["catch_signals_unresolved"] = dict(sig.most_common())
        if tier == "model":
            js = [[j["verdict"] for j in x["v"].get("model_judgments", [])] for x in xs]
            js = [j for j in js if j]
            unan = sum(len(set(j)) == 1 for j in js)
            paths = Counter(j.get("path") for x in xs for j in x["v"].get("model_judgments", []))
            changed = [
                x["task"]
                for x in xs
                if x["v"].get("model_verdict")
                and x["v"].get("deterministic") == "pass"
                and x["v"].get("model_verdict") != "pass"
            ]
            upgrades = Counter(
                (x["v"].get("deterministic"), x["v"].get("model_verdict")) for x in xs if x["v"].get("model_verdict")
            )
            t["stability"] = {
                "judged": len(js),
                "judgments": sum(len(j) for j in js),
                "unanimous": unan,
                "unanimous_rate": round(unan / len(js), 4) if js else None,
                "split": [
                    {
                        "task": x["task"],
                        "judgments": [j["verdict"] for j in x["v"]["model_judgments"]],
                        "majority": x["v"].get("model_verdict"),
                        "resolved": x["r"].resolved,
                    }
                    for x in xs
                    if x["v"].get("model_judgments") and len({j["verdict"] for j in x["v"]["model_judgments"]}) > 1
                ],
                "fleiss_kappa": fleiss_kappa(js),
                "single_judgment_flip_rate": round(
                    sum(sum(v != max(set(j), key=j.count) for v in j) for j in js) / max(1, sum(len(j) for j in js)), 4
                ),
                "paths": dict(paths),
            }
            t["model_vs_deterministic"] = {f"{a}->{b}": n for (a, b), n in sorted(upgrades.items())}
            t["model_downgraded_det_pass"] = changed
            # 单次判读（只取第 1 次）的精确率 / 召回率：与多数票对比，看“判 3 次”是否值得
            first = [
                (
                    x["r"].resolved,
                    (x["v"].get("model_judgments") or [{}])[0].get("verdict", x["v"].get("verdict")) in ("pass",)
                    and x["v"].get("deterministic") == "pass",
                )
                for x in xs
            ]
            t["single_judgment_first"] = pr(first)
            # 模型单独（不与确定性结论取保守）的表现
            t["model_alone_majority"] = pr(
                [(x["r"].resolved, x["v"].get("model_verdict", x["v"].get("verdict")) == "pass") for x in xs]
            )
        out["tiers"][tier] = t
    return out


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x:.0%}"


def render(a: dict[str, Any]) -> str:
    L = [
        "# W3-14 verifier 三档对比 · 数据表（自动生成）",
        "",
        f"来源：{', '.join(a['sources'])}；infra 排除：{', '.join(a['infra_excluded']) or '无'}",
        "",
        "| 档位 | n | 判 pass | 精确率 | 召回率 | 放过的假成功 | 误报（真解决被拦） | 已知 8 个假成功拦下 | 花费 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for tier, t in a["tiers"].items():
        s = t["all"]
        L.append(
            f"| {tier} | {s['n']} | {s['verified_pass']} | {_pct(s['precision'])} | {_pct(s['recall'])} "
            f"| {s['false_pass']} | {s['false_alarm']} | {t['known_false_success_caught']}/8 | ¥{t['cost_cny']:.4f} |"
        )
    L += [
        "",
        "## 分集合",
        "",
        "| 档位 | 集合 | n | 判 pass | 精确率 | 召回率 | 放过 | 误报 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for tier, t in a["tiers"].items():
        for st, s in t["by_set"].items():
            L.append(
                f"| {tier} | {st} | {s['n']} | {s['verified_pass']} | {_pct(s['precision'])} "
                f"| {_pct(s['recall'])} | {s['false_pass']} | {s['false_alarm']} |"
            )
    L += ["", "## 已知 8 个假成功", "", "| 任务 | " + " | ".join(a["tiers"]) + " |", "|---|" + "---|" * len(a["tiers"])]
    for tid in KNOWN_FALSE_SUCCESS:
        cells = []
        for t in a["tiers"].values():
            f = t["known_false_success"].get(tid)
            if not f:
                cells.append("—")
                continue
            mark = "✅ 拦下" if f["caught"] else "❌ 放过"
            extra = f"（{f['verdict']}，{f['risk']}；{'+'.join(f['signals'])}" if f["risk"] else f"（{f['verdict']}"
            if f["model_judgments"]:
                extra += f"；3 次：{'/'.join(f['model_judgments'])}"
            cells.append(mark + extra + "）")
        L.append(f"| {tid} | " + " | ".join(cells) + " |")
    L += ["", "## 误报（隐藏测试通过、验证器没放行）", ""]
    for tier, t in a["tiers"].items():
        if tier == "none":
            L.append(
                f"- none（Agent 自己没声称成功但其实解决了）：{', '.join(x['task'] for x in t['false_alarms']) or '无'}"
            )
            continue
        L.append(
            f"- {tier}（{len(t['false_alarms'])}）："
            + (
                "；".join(
                    f"{x['task']}={x['verdict']}/{x['risk']}[{'+'.join(x['signals'])}]"
                    + (f"(3 次 {'/'.join(x['model_judgments'])})" if x["model_judgments"] else "")
                    for x in t["false_alarms"]
                )
                or "无"
            )
        )
    L += ["", "## 风险等级 → 实际通过率", ""]
    for tier, t in a["tiers"].items():
        if t["by_risk"]:
            L.append(
                f"- {tier}："
                + "；".join(f"{lv} {v['resolved']}/{v['n']} = {_pct(v['pass_rate'])}" for lv, v in t["by_risk"].items())
            )
    L += ["", "## 拦截信号（隐藏测试不过且没放行的 attempt）", ""]
    for tier, t in a["tiers"].items():
        if tier != "none":
            L.append(f"- {tier}：" + ", ".join(f"{k} {v}" for k, v in t["catch_signals_unresolved"].items()))
    m = a["tiers"].get("model")
    if m and "stability" in m:
        s = m["stability"]
        L += [
            "",
            "## model 档稳定性（每个补丁独立判 3 次）",
            "",
            f"- 判读 {s['judged']} 个补丁 × 3 = {s['judgments']} 次；全票一致 {s['unanimous']}/{s['judged']}"
            f"（{_pct(s['unanimous_rate'])}）；单次判读偏离多数票 {_pct(s['single_judgment_flip_rate'])}；"
            f"Fleiss κ = {s['fleiss_kappa']}；输出路径 {s['paths']}",
            "- 不一致的补丁："
            + (
                "；".join(
                    f"{x['task']} {'/'.join(x['judgments'])}→{x['majority']}"
                    f"（隐藏测试{'过' if x['resolved'] else '不过'}）"
                    for x in s["split"]
                )
                or "无"
            ),
            f"- 确定性 → 合并后：{m['model_vs_deterministic']}；模型把确定性 pass 拉下来的：{m['model_downgraded_det_pass'] or '无'}",
            f"- 只取第 1 次判读：精确率 {_pct(m['single_judgment_first']['precision'])} / 召回率 "
            f"{_pct(m['single_judgment_first']['recall'])}；模型多数票单独看（不与确定性取保守）：精确率 "
            f"{_pct(m['model_alone_majority']['precision'])} / 召回率 {_pct(m['model_alone_majority']['recall'])}",
        ]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args()
    a = analyze(ns.dirs)
    ns.out.mkdir(parents=True, exist_ok=True)
    (ns.out / "tiers.json").write_text(json.dumps(a, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (ns.out / "tiers.md").write_text(render(a), encoding="utf-8")
    print(render(a))


if __name__ == "__main__":
    main()
