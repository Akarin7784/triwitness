"""W5-09/10/11：OFAT（一次一个因素）消融的生成、运行、报告与打包。

    uv run python scripts/ofat_ablation.py plan   evals/ablations/w5-round1.yaml --out out/ofat
    uv run python scripts/ofat_ablation.py run    evals/ablations/w5-round1.yaml --out out/ofat --concurrency 3
    uv run python scripts/ofat_ablation.py report evals/ablations/w5-round1.yaml --out out/ofat
    uv run python scripts/ofat_ablation.py bundle --out out/ofat

- `plan`：用 `triwitness.eval.ablation.ofat` 从基线 RunConfig + 因素表生成每个配置的 YAML，打印预估花费与可检出差异；
- `run`：逐个配置调用 `tw eval run --live`（只用 deepseek-flash，全部记账本）；结果目录可续跑；
  北京时间工作日 9–12、14–18 不开新配置（退出码 3，高峰后重跑同一命令续上）；
- `report`：与本轮基线配对比较（McNemar 精确检验 + Holm 校正 + bootstrap 置信区间），W2 基线作次要对照；
- `bundle`：结果 + 账本打成一个 zip 发回分析。

重评测不在 box 上跑：Windows 一键脚本见 scripts/windows/run-ofat-ablation.ps1。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from triwitness.eval.ablation import compare, estimate_cost, mde_paired, ofat, render_rows

ROOT = Path(__file__).resolve().parents[1]
BJ = timezone(timedelta(hours=8))
CATEGORY = "ofat-ablation"
PEAK_EXIT = 3


def is_peak(now: datetime | None = None) -> bool:
    """北京时间工作日 9–12、14–18 为高峰（Eva 要求避开）。"""
    t = (now or datetime.now(BJ)).astimezone(BJ)
    return t.weekday() < 5 and (9 <= t.hour < 12 or 14 <= t.hour < 18)


def load_spec(path: Path) -> dict[str, Any]:
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    for k in ("name", "suite", "base", "factors"):
        if k not in spec:
            raise SystemExit(f"{path}：缺少 {k}")
    return spec


def suite_tasks(suite: str) -> list[str]:
    data = yaml.safe_load((ROOT / "evals" / "suites" / f"{suite}.yaml").read_text(encoding="utf-8"))
    return [t["id"] for t in data["tasks"]]


def build_plan(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    """返回 [{name, factor, level, cost_factor, config}]；config 是可直接给 `tw eval run --config` 的 RunConfig。"""
    base = yaml.safe_load((ROOT / spec["base"]).read_text(encoding="utf-8"))
    base.pop("name", None)
    factors: dict[str, dict[str, dict[str, Any]]] = {}
    cost_factor: dict[tuple[str, str], float] = {}
    for f, levels in spec["factors"].items():
        factors[f] = {}
        for lv, over in levels.items():
            over = dict(over)
            cost_factor[(f, lv)] = float(over.pop("cost_factor", 1.0))
            factors[f][lv] = over
    out = []
    for c in ofat(base, factors, prefix=spec["name"]):
        cfg = dict(c.config, category=CATEGORY)
        if (cfg.get("executor") or {}).get("model", "deepseek-flash") != "deepseek-flash":
            raise SystemExit(f"{c.name}：只允许 deepseek-flash")
        cf = cost_factor.get((c.factor, c.level or ""), 1.0) if c.factor else 1.0
        out.append({"name": c.name, "factor": c.factor, "level": c.level, "cost_factor": cf, "config": cfg})
    return out


def write_configs(plan: list[dict[str, Any]], out: Path) -> list[Path]:
    d = out / "configs"
    d.mkdir(parents=True, exist_ok=True)
    paths = []
    for p in plan:
        path = d / f"{p['name']}.yaml"
        path.write_text(yaml.safe_dump(p["config"], allow_unicode=True, sort_keys=False), encoding="utf-8")
        paths.append(path)
    return paths


def estimate(spec: Mapping[str, Any], plan: list[dict[str, Any]], tasks: int, attempts: int) -> float:
    per = float(spec.get("per_task_cny", 0.06))
    return round(sum(estimate_cost(1, tasks, attempts=attempts, per_task_cny=per * p["cost_factor"]) for p in plan), 2)


def cmd_plan(spec_path: Path, out: Path, attempts: int) -> list[dict[str, Any]]:
    spec = load_spec(spec_path)
    plan = build_plan(spec)
    paths = write_configs(plan, out)
    n = len(suite_tasks(spec["suite"]))
    total = estimate(spec, plan, n, attempts)
    print(f"{spec['name']}：{len(plan)} 个配置 × {n} 题 × {attempts} 次（套件 {spec['suite']}）")
    for p, path in zip(plan, paths, strict=True):
        tag = f"{p['factor']}={p['level']}" if p["factor"] else "基线"
        print(f"  {p['name']:44} {tag:22} ×{p['cost_factor']:.1f}  {path.relative_to(out)}")
    print(f"预估 ¥{total:.2f}（单价 ¥{spec.get('per_task_cny', 0.06)}/题 × 档位系数；以账本实扣为准）")
    print(f"配对可检出差异（80% 功效，约 20% 不一致对）：n={n * attempts} → ≈{mde_paired(n * attempts):.0%}")
    (out / "plan.json").write_text(
        json.dumps({"spec": spec, "configs": plan, "estimate_cny": total, "attempts": attempts},
                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")  # fmt: skip
    return plan


def tw_cmd(*args: str) -> list[str]:
    return [sys.executable, "-c", "import sys; sys.argv[0] = 'tw'; from triwitness.cli.main import app; app()", *args]


def cmd_run(spec_path: Path, out: Path, *, concurrency: int, attempts: int, only: list[str] | None,
            tasks: list[str] | None, allow_peak: bool, dry_run: bool) -> int:  # fmt: skip
    plan = cmd_plan(spec_path, out, attempts)
    spec = load_spec(spec_path)
    log = out / "run.log"
    rc = 0
    for p in plan:
        if only and p["name"] not in only and (p["factor"] or "base") not in only:
            continue
        if is_peak() and not allow_peak:
            print(f"北京时间 {datetime.now(BJ):%H:%M} 是工作日高峰，暂停；高峰后重跑同一命令续上（已完成的不重跑）")
            return PEAK_EXIT
        cfg_path, res_dir = out / "configs" / f"{p['name']}.yaml", out / "results" / p["name"]
        args = ["eval", "run", "--live", "--suite", spec["suite"], "--config", str(cfg_path),
                "--concurrency", str(concurrency), "--attempts", str(attempts), "--out", str(res_dir)]  # fmt: skip
        for t in tasks or []:
            args += ["--task", t]
        print(f"\n==> {p['name']}：tw {' '.join(args)}", flush=True)
        if dry_run:
            continue
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"\n==> {datetime.now(BJ):%F %T} {p['name']}\n")
            fh.flush()
            r = subprocess.run(tw_cmd(*args), stdout=fh, stderr=subprocess.STDOUT, check=False)
        print(f"    退出码 {r.returncode}（日志 {log}）")
        rc = rc or r.returncode
    return rc


def load_results(run_dir: Path) -> tuple[dict[str, bool], float]:
    """{任务#尝试: 是否解决}, 实际花费。多次尝试按 (任务, 尝试) 配对。

    Agent 侧错误（如单任务预算用尽）照常计入；基础设施错误不写 result.json（runner 记在 errors.json，续跑时重做）。"""
    res: dict[str, bool] = {}
    cost = 0.0
    for f in sorted(run_dir.rglob("result.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        res[f"{d['task_id']}#{d.get('attempt', 1)}"] = bool(d.get("resolved"))
        cost += float(d.get("cost_cny") or 0)
    return res, round(cost, 4)


def cmd_report(spec_path: Path, out: Path) -> Path:
    spec = load_spec(spec_path)
    plan = build_plan(spec)
    results: dict[str, dict[str, bool]] = {}
    costs: dict[str, float] = {}
    for p in plan:
        d = out / "results" / p["name"]
        if d.is_dir():
            results[p["name"]], costs[p["name"]] = load_results(d)
    base = plan[0]["name"]
    if base not in results or not results[base]:
        raise SystemExit(f"还没有基线结果（{out / 'results' / base}）")
    lines = [f"# OFAT 消融 {spec['name']}（套件 {spec['suite']}）", "",
             f"生成：{datetime.now(BJ):%F %H:%M} 北京时间；基线 = 本轮重跑的 `{base}`。", "",
             "判定：Holm 校正后 p < 0.05 且配对差的 bootstrap 95% 区间不含 0 才算“更好 / 更差”；否则“无显著差异”。", "",
             render_rows(compare(results, base, costs=costs)), ""]  # fmt: skip
    ref = spec.get("reference")
    if ref and (ROOT / ref).is_dir():
        ref_res, ref_cost = load_results(ROOT / ref)
        both = {"w2-reference": ref_res, base: results[base]}
        ref_costs = {"w2-reference": ref_cost, base: costs[base]}
        lines += ["## 次要对照：W2 基线（代码已漂移，仅供参考）", "",
                  render_rows(compare(both, "w2-reference", costs=ref_costs)), ""]  # fmt: skip
    total = round(sum(costs.values()), 4)
    lines += [f"本轮 result.json 合计 ¥{total:.4f}（账本见 bundle 里的 ledger.sqlite，类别 {CATEGORY}）。", ""]
    rep = out / "report.md"
    rep.write_text("\n".join(lines), encoding="utf-8")
    (out / "summary.json").write_text(
        json.dumps({"results": results, "costs": costs, "total_cny": total}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")  # fmt: skip
    print(rep.read_text(encoding="utf-8"))
    return rep


def cmd_bundle(out: Path, ledger: Path | None) -> Path:
    stamp = datetime.now(BJ).strftime("%Y%m%d-%H%M")
    dest = out.parent / f"ofat-ablation-{stamp}.zip"
    ledger = ledger or Path(os.environ.get("TW_HOME", Path.home() / ".triwitness")) / "ledger.sqlite"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in ("results", "configs"):
            for p in sorted((out / sub).rglob("*")) if (out / sub).is_dir() else []:
                if p.is_file() and "/.tw/" not in p.as_posix():
                    z.write(p, f"ofat/{p.relative_to(out).as_posix()}")
        for name in ("plan.json", "report.md", "summary.json", "run.log", "env.json"):
            if (out / name).is_file():
                z.write(out / name, f"ofat/{name}")
        if ledger.is_file():
            z.write(ledger, "ledger.sqlite")
    print(f"已打包：{dest}（{dest.stat().st_size / 1e6:.1f} MB）")
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run", "report", "bundle"):
        p = sub.add_parser(name)
        if name != "bundle":
            p.add_argument("spec", type=Path)
        p.add_argument("--out", type=Path, default=ROOT / "out" / "ofat")
        if name in ("plan", "run"):
            p.add_argument("--attempts", type=int, default=1, help="每题重复次数（>1 时按 (题, 次) 配对）")
        if name == "run":
            p.add_argument("--concurrency", type=int, default=3)
            p.add_argument("--only", help="逗号分隔：配置名或因素名（base 表示基线）")
            p.add_argument("--task", action="append", help="只跑这些任务（冒烟用），可多次")
            p.add_argument("--allow-peak", action="store_true")
            p.add_argument("--dry-run", action="store_true", help="只打印要执行的命令")
        if name == "bundle":
            p.add_argument("--ledger", type=Path, default=None)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "plan":
        cmd_plan(a.spec, a.out, a.attempts)
    elif a.cmd == "run":
        only = [s.strip() for s in a.only.split(",")] if a.only else None
        return cmd_run(a.spec, a.out, concurrency=a.concurrency, attempts=a.attempts, only=only, tasks=a.task,
                       allow_peak=a.allow_peak, dry_run=a.dry_run)  # fmt: skip
    elif a.cmd == "report":
        cmd_report(a.spec, a.out)
    else:
        cmd_bundle(a.out, a.ledger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
