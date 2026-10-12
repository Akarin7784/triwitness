"""W8-01 终测：test 集（35 题）× {单 Executor 基线, 完整流水线} × 1 次，冻结配置、记录元数据、打包。

    uv run python scripts/final_eval.py plan   --out out/final
    uv run python scripts/final_eval.py run    --out out/final [--arms baseline,orchestrated] [--task ID] [--dry-run]
    uv run python scripts/final_eval.py report --out out/final
    uv run python scripts/final_eval.py bundle --out out/final [--max-mb 24]
    uv run python scripts/final_eval.py reproduce --out out/final [--task ID] [--dry-run]   # W8-05

- 只用 deepseek-flash；评测模式权限全开、不读写记忆；不设金额上限（只报告，防失控上限照常）。高峰照跑（Eva 控预算）。
- `run` 对每个臂调用 `tw eval run --live --suite test --allow-test --out <固定目录>`：已有 result.json 的题跳过，
  中断后重跑同一命令即续跑（基础设施错误不写 result.json，会重做）。
- `report`：每臂 Resolved@1（Wilson 95%）、¥/题、¥/解决、缓存命中率、假成功、平均回合；配对 McNemar；
  模型快照名（轨迹 served_model）、价格表版本（pricing.yaml verified_at + sha256）、代码 commit。
- `reproduce`（W8-05）：从 baseline 臂挑 1 道最便宜的已解决题，`tw eval reproduce <baseline 结果> --task <题> --live`
  重跑并逐题对比（out/reproduce/reproduce.md）；同一题已复现过就跳过（续跑）。
- `bundle`：结果 + 账本打成 zip；超过 --max-mb 时拆成多个**各自可独立解压**的 zip（part01、part02…）。

重评测不在 box 上跑：Windows 一键脚本 scripts/windows/run-final-eval.ps1。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
BJ = timezone(timedelta(hours=8))
SUITE = "test"
CATEGORY = "final-eval"
ARMS: dict[str, str] = {
    "baseline": "configs/runs/final-baseline.yaml",
    "orchestrated": "configs/runs/final-orchestrated.yaml",
}
# 预估单价（¥/题，空闲价）：W5 dev 非思考 ¥0.042、Planner 约 3.4×；test 题更难（W2 test 平均回合 53，dev 约 25）按 ×2.5
PER_TASK_CNY = {"baseline": 0.11, "orchestrated": 0.38}
BUDGET_GUIDE_CNY = 18.0


def suite_tasks() -> list[str]:
    data = yaml.safe_load((ROOT / "evals" / "suites" / f"{SUITE}.yaml").read_text(encoding="utf-8"))
    return [t["id"] for t in data["tasks"]]


def pick_arms(arms: str | None) -> list[str]:
    names = [a.strip() for a in (arms or ",".join(ARMS)).split(",") if a.strip()]
    for a in names:
        if a not in ARMS:
            raise SystemExit(f"未知臂 {a}；可选：{', '.join(ARMS)}")
    return names


def estimate(n_tasks: int, arms: list[str], peak: bool = False) -> dict[str, float]:
    mult = 2.0 if peak else 1.0
    est = {a: round(PER_TASK_CNY[a] * n_tasks * mult, 2) for a in arms}
    est["total"] = round(sum(est.values()), 2)
    return est


def pricing_version() -> dict[str, str]:
    p = ROOT / "configs" / "pricing.yaml"
    raw = p.read_bytes()
    data = yaml.safe_load(raw)
    return {"verified_at": str(data.get("verified_at")), "sha256": hashlib.sha256(raw).hexdigest()[:16]}


def git_sha() -> str:
    f = ROOT / ".git-sha"
    if f.is_file():
        return f.read_text(encoding="utf-8").strip()
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()  # fmt: skip
    except (OSError, subprocess.CalledProcessError):
        return "?"


def cmd_plan(out: Path, arms: list[str], tasks: list[str] | None) -> dict[str, Any]:
    ids = tasks or suite_tasks()
    plan = {
        "suite": SUITE,
        "tasks": len(ids),
        "arms": {a: ARMS[a] for a in arms},
        "configs": {a: yaml.safe_load((ROOT / ARMS[a]).read_text(encoding="utf-8")) for a in arms},
        "estimate_cny_off_peak": estimate(len(ids), arms),
        "estimate_cny_peak": estimate(len(ids), arms, peak=True),
        "budget_guide_cny": BUDGET_GUIDE_CNY,
        "pricing": pricing_version(),
        "git_sha": git_sha(),
        "planned_at": datetime.now(BJ).isoformat(timespec="seconds"),
    }
    for a in arms:
        if (plan["configs"][a].get("executor") or {}).get("model", "deepseek-flash") != "deepseek-flash":
            raise SystemExit(f"{a}：只允许 deepseek-flash")
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    e, ep = plan["estimate_cny_off_peak"], plan["estimate_cny_peak"]
    print(f"W8-01 终测：套件 {SUITE} {len(ids)} 题 × {len(arms)} 臂 × 1 次；commit {plan['git_sha']}")
    for a in arms:
        print(f"  {a:13} {ARMS[a]}  预估 ¥{e[a]:.2f}（高峰 ¥{ep[a]:.2f}）")
    print(
        f"合计预估 ¥{e['total']:.2f}（全程高峰 ¥{ep['total']:.2f}）；指导线 ≤ ¥{BUDGET_GUIDE_CNY:.0f}，只报告不拦截。"
    )
    print(f"价格表 verified_at={plan['pricing']['verified_at']} sha256={plan['pricing']['sha256']}")
    return plan


def tw_cmd(*args: str) -> list[str]:
    return [sys.executable, "-c", "import sys; sys.argv[0] = 'tw'; from triwitness.cli.main import app; app()", *args]


def arm_args(arm: str, out: Path, concurrency: int, tasks: list[str] | None) -> list[str]:
    args = ["eval", "run", "--live", "--suite", SUITE, "--allow-test", "--config", str(ROOT / ARMS[arm]),
            "--concurrency", str(concurrency), "--attempts", "1", "--out", str(out / "results" / arm)]  # fmt: skip
    for t in tasks or []:
        args += ["--task", t]
    return args


def cmd_run(out: Path, *, arms: list[str], concurrency: int, tasks: list[str] | None, dry_run: bool) -> int:
    cmd_plan(out, arms, tasks)
    log = out / "run.log"
    rc = 0
    for arm in arms:
        args = arm_args(arm, out, concurrency, tasks)
        done = len(list((out / "results" / arm).rglob("result.json"))) if (out / "results" / arm).is_dir() else 0
        print(f"\n==> {arm}（已完成 {done} 题，续跑跳过）：tw {' '.join(args)}", flush=True)
        if dry_run:
            continue
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"\n==> {datetime.now(BJ):%F %T} {arm}\n")
            fh.flush()
            r = subprocess.run(tw_cmd(*args), stdout=fh, stderr=subprocess.STDOUT, check=False)
        print(f"    退出码 {r.returncode}（日志 {log}）", flush=True)
        rc = rc or r.returncode
    return rc


def pick_reproduce_task(arm_dir: Path) -> str | None:
    """baseline 臂里花费最低的已解决题（没有已解决的就取花费最低的题）。"""
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(arm_dir.rglob("result.json"))]
    if not rows:
        return None
    rows.sort(key=lambda r: (not r.get("resolved"), float(r.get("cost_cny") or 0), r["task_id"]))
    return str(rows[0]["task_id"])


def cmd_reproduce(out: Path, *, task: str | None, dry_run: bool) -> int:
    src = out / "results" / "baseline"
    if not (src / "run.json").is_file():
        print(f"没有 baseline 臂结果（{src}），跳过复现")
        return 0
    tid = task or pick_reproduce_task(src)
    if not tid:
        print("baseline 臂还没有 result.json，跳过复现")
        return 0
    dest = out / "reproduce"
    args = ["eval", "reproduce", str(src), "--task", tid, "--live", "--concurrency", "1", "--out", str(dest)]
    print(f"\n==> W8-05 复现 1 题 {tid}：tw {' '.join(args)}", flush=True)
    if dry_run:
        return 0
    with (out / "run.log").open("a", encoding="utf-8") as fh:
        fh.write(f"\n==> {datetime.now(BJ):%F %T} reproduce {tid}\n")
        fh.flush()
        r = subprocess.run(tw_cmd(*args), stdout=fh, stderr=subprocess.STDOUT, check=False)
    rep = dest / "reproduce.md"
    print(rep.read_text(encoding="utf-8") if rep.is_file() else f"复现退出码 {r.returncode}，见 run.log", flush=True)
    return r.returncode


# ---------------------------------------------------------------- report


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def mcnemar_exact(b: int, c: int) -> float:
    from math import comb

    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(k + 1)) / 2**n
    return round(min(1.0, 2 * p), 4)


def served_models(arm_dir: Path) -> dict[str, int]:
    seen: dict[str, int] = {}
    for traj in arm_dir.rglob("trajectory.jsonl"):
        for line in traj.read_text(encoding="utf-8", errors="replace").splitlines():
            if '"model_call"' not in line:
                continue
            try:
                p = json.loads(line).get("payload") or {}
            except json.JSONDecodeError:
                continue
            m = p.get("served_model") or p.get("model")
            if m:
                seen[m] = seen.get(m, 0) + 1
    return seen


def arm_stats(arm_dir: Path) -> dict[str, Any]:
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(arm_dir.rglob("result.json"))]
    n = len(rows)
    solved = sum(1 for r in rows if r.get("resolved"))
    cost = sum(float(r.get("cost_cny") or 0) for r in rows)
    tin = sum(int(r.get("tokens_in") or 0) for r in rows)
    tcached = sum(int(r.get("tokens_cached") or 0) for r in rows)
    peak_calls = sum(int(r.get("peak_calls") or 0) for r in rows)
    errors = arm_dir / "errors.json"
    return {
        "graded": n,
        "solved": solved,
        "resolved_at_1": round(solved / n, 4) if n else None,
        "ci95": wilson(solved, n),
        "total_cost_cny": round(cost, 4),
        "cost_per_task": round(cost / n, 4) if n else None,
        "cost_per_resolved": round(cost / solved, 4) if solved else None,
        "cache_hit_rate": round(tcached / tin, 4) if tin else None,
        "false_success": sum(1 for r in rows if r.get("false_success")),
        "avg_steps": round(sum(int(r.get("steps") or 0) for r in rows) / n, 1) if n else None,
        "avg_wall_s": round(sum(float(r.get("wall_s") or 0) for r in rows) / n, 1) if n else None,
        "peak_calls": peak_calls,
        "infra_errors": json.loads(errors.read_text(encoding="utf-8")) if errors.is_file() else {},
        "served_models": served_models(arm_dir),
        "per_task": {r["task_id"]: bool(r.get("resolved")) for r in rows},
    }


def cmd_report(out: Path, arms: list[str]) -> Path:
    stats = {a: arm_stats(out / "results" / a) for a in arms if (out / "results" / a).is_dir()}
    if not stats:
        raise SystemExit(f"还没有结果（{out / 'results'}）")
    pricing = pricing_version()
    env = json.loads((out / "env.json").read_text(encoding="utf-8")) if (out / "env.json").is_file() else {}
    lines = [f"# W8-01 终测（套件 {SUITE}）", "",
             f"生成：{datetime.now(BJ):%F %H:%M} 北京时间；commit {env.get('git_sha') or git_sha()}；"
             f"价格表 verified_at={pricing['verified_at']}（sha256 {pricing['sha256']}）。", "",
             "| 臂 | 判分 | 解决 | Resolved@1 | Wilson 95% | ¥/题 | ¥/解决 | 缓存命中 | 假成功 | 平均回合 "
             "| 高峰调用 | 模型快照 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for a, s in stats.items():
        models = "、".join(f"{m}×{c}" for m, c in sorted(s["served_models"].items())) or "?"
        r1 = f"{s['resolved_at_1']:.1%}" if s["resolved_at_1"] is not None else "-"
        hit = f"{s['cache_hit_rate']:.1%}" if s["cache_hit_rate"] is not None else "-"
        lines.append(f"| {a} | {s['graded']} | {s['solved']} | {r1} | {s['ci95'][0]:.0%}–{s['ci95'][1]:.0%} | "
                     f"{s['cost_per_task'] or 0:.3f} | {s['cost_per_resolved'] or 0:.3f} | {hit} | "
                     f"{s['false_success']} | {s['avg_steps']} | {s['peak_calls']} | {models} |")  # fmt: skip
    paired = None
    if "baseline" in stats and "orchestrated" in stats:
        bt, ot = stats["baseline"]["per_task"], stats["orchestrated"]["per_task"]
        common = sorted(set(bt) & set(ot))
        b = sum(1 for t in common if ot[t] and not bt[t])  # 编排解决、基线没解决
        c = sum(1 for t in common if bt[t] and not ot[t])
        paired = {"n": len(common), "orch_only": b, "base_only": c, "mcnemar_p": mcnemar_exact(b, c)}
        lines += ["", f"配对（{len(common)} 题）：只有编排解决 {b}，只有基线解决 {c}，"
                  f"McNemar 精确 p={paired['mcnemar_p']}。"
                  "n=35 时可检出差异约 25–30 个百分点；p ≥ 0.05 写“无显著差异”。"]  # fmt: skip
    total = round(sum(s["total_cost_cny"] for s in stats.values()), 4)
    lines += ["", f"合计 result.json ¥{total:.4f}（指导线 ≤ ¥{BUDGET_GUIDE_CNY:.0f}，只报告；"
              "账本见 bundle 的 ledger.sqlite，"
              f"类别 {CATEGORY}）。基础设施错误不计入分母，见各臂 errors.json。", ""]  # fmt: skip
    rep = out / "report.md"
    rep.write_text("\n".join(lines), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps({"arms": stats, "paired": paired, "total_cny": total,
                                                  "pricing": pricing, "env": env}, ensure_ascii=False, indent=1)
                                      + "\n", encoding="utf-8")  # fmt: skip
    print(rep.read_text(encoding="utf-8"))
    return rep


# ---------------------------------------------------------------- bundle


def bundle_files(out: Path, ledger: Path | None) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for name in ("plan.json", "report.md", "summary.json", "run.log", "env.json"):
        if (out / name).is_file():
            files.append((out / name, f"final/{name}"))
    rep = out / "reproduce"
    if rep.is_dir():
        for p in sorted(rep.rglob("*")):
            if p.is_file() and "/.tw/" not in p.as_posix():
                files.append((p, f"final/{p.relative_to(out).as_posix()}"))
    res = out / "results"
    if res.is_dir():
        for p in sorted(res.rglob("*")):
            if p.is_file() and "/.tw/" not in p.as_posix() and "/worktrees/" not in p.as_posix():
                files.append((p, f"final/{p.relative_to(out).as_posix()}"))
    ledger = ledger or Path(os.environ.get("TW_HOME", Path.home() / ".triwitness")) / "ledger.sqlite"
    if ledger.is_file():
        files.append((ledger, "ledger.sqlite"))
    return files


def cmd_bundle(out: Path, ledger: Path | None, max_mb: float, dest_dir: Path | None = None) -> list[Path]:
    """打包；超过 max_mb 时按文件切成多个独立 zip（小文件 / 报告 / 账本在 part01）。"""
    stamp = datetime.now(BJ).strftime("%Y%m%d-%H%M")
    dest_dir = dest_dir or out.parent
    files = bundle_files(out, ledger)
    limit = int(max_mb * 1e6)
    meta = [f for f in files if not f[1].startswith("final/results/")]
    rest = [f for f in files if f[1].startswith("final/results/")]
    groups: list[list[tuple[Path, str]]] = [list(meta)]
    size = sum(p.stat().st_size for p, _ in meta)
    for f in rest:
        s = f[0].stat().st_size
        if size + s > limit * 2.5 and groups[-1]:  # 文本压缩比约 3–5×，按原始大小 2.5× 估
            groups.append([])
            size = 0
        groups[-1].append(f)
        size += s
    outs: list[Path] = []
    single = len(groups) == 1
    for i, g in enumerate(groups, 1):
        dest = dest_dir / (f"final-eval-{stamp}.zip" if single else f"final-eval-{stamp}-part{i:02d}.zip")
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            for p, arc in g:
                z.write(p, arc)
        outs.append(dest)
    # 压完仍超限的分卷再细分一次（极少见）
    final: list[Path] = []
    for d in outs:
        if d.stat().st_size > limit and len(zipfile.ZipFile(d).namelist()) > 1:
            names = zipfile.ZipFile(d).namelist()
            half = len(names) // 2
            with zipfile.ZipFile(d) as src:
                for j, chunk in enumerate((names[:half], names[half:]), 1):
                    nd = d.with_name(d.stem + f"{'ab'[j - 1]}.zip")
                    with zipfile.ZipFile(nd, "w", zipfile.ZIP_DEFLATED) as z:
                        for n in chunk:
                            z.writestr(n, src.read(n))
                    final.append(nd)
            d.unlink()
        else:
            final.append(d)
    for d in final:
        print(f"已打包：{d}（{d.stat().st_size / 1e6:.1f} MB）")
    return final


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run", "report", "bundle", "reproduce"):
        p = sub.add_parser(name)
        p.add_argument("--out", type=Path, default=ROOT / "out" / "final")
        p.add_argument("--arms", default=None, help="逗号分隔：baseline,orchestrated（默认两个都跑）")
        if name in ("plan", "run"):
            p.add_argument("--task", action="append", help="只跑这些任务（冒烟用），可多次")
        if name == "reproduce":
            p.add_argument("--task", default=None, help="复现哪一题（默认 baseline 臂最便宜的已解决题）")
            p.add_argument("--dry-run", action="store_true")
        if name == "run":
            p.add_argument("--concurrency", type=int, default=3)
            p.add_argument("--dry-run", action="store_true", help="只打印要执行的命令，不调用模型")
        if name == "bundle":
            p.add_argument("--ledger", type=Path, default=None)
            p.add_argument("--max-mb", type=float, default=24.0)
            p.add_argument("--dest", type=Path, default=None)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    arms = pick_arms(a.arms)
    if a.cmd == "plan":
        cmd_plan(a.out, arms, a.task)
    elif a.cmd == "run":
        return cmd_run(a.out, arms=arms, concurrency=a.concurrency, tasks=a.task, dry_run=a.dry_run)
    elif a.cmd == "report":
        cmd_report(a.out, arms)
    elif a.cmd == "reproduce":
        return cmd_reproduce(a.out, task=a.task, dry_run=a.dry_run)
    else:
        cmd_bundle(a.out, a.ledger, a.max_mb, a.dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
