"""W5-13：用 Harbor 跑外部对照（Terminal-Bench 2.0 小子集，≤10 题），Agent = TriWitness（deepseek-flash 非思考）。

    uv run python scripts/harbor_external.py fetch  --dir ~/tw-harbor/terminal-bench-2
    uv run python scripts/harbor_external.py run    --dir ~/tw-harbor/terminal-bench-2 --out ~/tw-harbor/jobs
    uv run python scripts/harbor_external.py report --out ~/tw-harbor/jobs
    uv run python scripts/harbor_external.py bundle --out ~/tw-harbor/jobs

- Harbor 不是 TriWitness 的依赖：`run` 用 `uv run --with harbor==<版本> harbor run ...`；需要 docker + docker compose；
- 任务来自 laude-institute/terminal-bench-2 的固定提交（Apache-2.0），只取 10 个 easy / 较短的 medium、无 GPU 的题；
- TB2 的 verifier 会联网装 uv / pytest（任务自带 allow_internet = true），所以必须在网络正常的 Docker 上跑（box 的
  docker 自定义网络没有 DNS，跑不了，交给 Eva 的 PC：scripts/windows/run-harbor-tb2.ps1）；
- 北京时间工作日 9–12、14–18 不开始（退出码 3）；所有模型调用记账本（类别 harbor-external）。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BJ = timezone(timedelta(hours=8))
HARBOR = "harbor==0.24.0"
TB2_REPO = "https://github.com/laude-institute/terminal-bench-2.git"
TB2_SHA = "2fd12b88aafdd04a52c298e3940bcb189f9766d6"
AGENT = "triwitness.integrations.harbor_agent:TriWitnessAgent"
# 10 题：easy 全部 4 个 + 6 个专家估时 ≤ 30 分钟、无 GPU、不下载大模型的 medium
TASKS = [
    "fix-git", "cobol-modernization", "prove-plus-comm", "overfull-hbox",
    "constraints-scheduling", "nginx-request-logging", "openssl-selfsigned-cert", "polyglot-c-py",
    "multi-source-data-merger", "git-leak-recovery",
]  # fmt: skip
PEAK_EXIT = 3


def is_peak(now: datetime | None = None) -> bool:
    t = (now or datetime.now(BJ)).astimezone(BJ)
    return t.weekday() < 5 and (9 <= t.hour < 12 or 14 <= t.hour < 18)


def cmd_fetch(d: Path) -> None:
    if not (d / ".git").is_dir():
        d.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", TB2_REPO, str(d)], check=True)
    subprocess.run(["git", "-C", str(d), "fetch", "-q", "origin", TB2_SHA], check=False)
    subprocess.run(["git", "-C", str(d), "checkout", "-q", TB2_SHA], check=True)
    missing = [t for t in TASKS if not (d / t / "task.toml").is_file()]
    if missing:
        raise SystemExit(f"terminal-bench-2@{TB2_SHA[:12]} 里缺少：{missing}")
    print(f"terminal-bench-2 @ {TB2_SHA[:12]}：{len(TASKS)} 题就绪（{d}）")


def harbor_args(d: Path, out: Path, *, concurrency: int, attempts: int, tasks: list[str], thinking: bool) -> list[str]:
    args = ["uv", "run", "--with", HARBOR, "harbor", "run", "-p", str(d), "-a", AGENT, "--ak", "harness=baseline",
            "--ak", f"thinking={str(thinking).lower()}", "-n", str(concurrency), "-k", str(attempts), "-o", str(out),
            "-y"]  # fmt: skip
    for t in tasks:
        args += ["-i", t]
    return args


def cmd_run(d: Path, out: Path, *, concurrency: int, attempts: int, tasks: list[str], thinking: bool,
            allow_peak: bool, dry_run: bool) -> int:  # fmt: skip
    if is_peak() and not allow_peak:
        print(f"北京时间 {datetime.now(BJ):%H:%M} 是工作日高峰，不开始；高峰后重跑")
        return PEAK_EXIT
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("没有 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    args = harbor_args(d, out, concurrency=concurrency, attempts=attempts, tasks=tasks, thinking=thinking)
    if dry_run:
        args.append("--dry-run")
    print("==>", " ".join(args), flush=True)
    env = {**os.environ, "TW_LLM_MODE": "live"}
    return subprocess.run(args, cwd=ROOT, env=env, check=False).returncode


def collect(out: Path) -> list[dict]:
    rows = []
    for f in sorted(out.glob("*/*/result.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        if "task_name" not in r and "trial_name" not in r:
            continue
        vr = r.get("verifier_result") or {}
        meta = ((r.get("agent_result") or {}).get("metadata")) or {}
        exc = r.get("exception_info") or {}
        rows.append({
            "task": r.get("task_name") or f.parent.name.split("__")[0], "trial": f.parent.name,
            "reward": (vr.get("rewards") or {}).get("reward"), "status": meta.get("triwitness_status"),
            "cost_cny": meta.get("cost_cny"), "steps": meta.get("steps"), "cache_hit": meta.get("cache_hit_rate"),
            "error": exc.get("exception_type"),
        })  # fmt: skip
    return rows


def cmd_report(out: Path) -> Path:
    from triwitness.eval.ablation import wilson

    rows = collect(out)
    n = len(rows)
    k = sum(1 for r in rows if (r["reward"] or 0) >= 1)
    lo, hi = wilson(k, n) if n else (0.0, 0.0)
    cost = round(sum(r["cost_cny"] or 0 for r in rows), 4)
    head = (f"生成：{datetime.now(BJ):%F %H:%M} 北京时间；terminal-bench-2@{TB2_SHA[:12]}；"
            "Agent deepseek-flash（非思考），harness baseline（文件 + bash 工具，无快照 / diff）。")  # fmt: skip
    verdict = (f"**解决 {k}/{n}**（Wilson 95%：{lo:.0%}–{hi:.0%}）；"
               f"花费 ¥{cost}（Agent 上报，账本类别 harbor-external）。")  # fmt: skip
    lines = ["# 外部对照：Terminal-Bench 2.0 子集 × TriWitness（Harbor）", "", head, "", verdict,
             f"样本只有 {n} 次试验，只作外部参照，不和 dev / test 的 SWE 类结果直接比较。", "",
             "| 任务 | 试次 | 奖励 | TriWitness 状态 | 步数 | ¥ | 命中 | 异常 |",
             "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in rows:
        hit = f"{r['cache_hit']:.0%}" if isinstance(r["cache_hit"], int | float) else "—"
        cny = r["cost_cny"] if r["cost_cny"] is not None else "—"
        lines.append(f"| {r['task']} | {r['trial']} | {r['reward']} | {r['status'] or '—'} | "
                     f"{r['steps'] or '—'} | {cny} | {hit} | {r['error'] or ''} |")  # fmt: skip
    rep = out / "report.md"
    rep.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps({"solved": k, "n": n, "cost_cny": cost, "rows": rows},
                                                 ensure_ascii=False, indent=1) + "\n", encoding="utf-8")  # fmt: skip
    print(rep.read_text(encoding="utf-8"))
    return rep


def cmd_bundle(out: Path) -> Path:
    stamp = datetime.now(BJ).strftime("%Y%m%d-%H%M")
    dest = out.parent / f"harbor-tb2-{stamp}.zip"
    ledger = Path(os.environ.get("TW_HOME", Path.home() / ".triwitness")) / "ledger.sqlite"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob("*")):
            if p.is_file() and p.stat().st_size < 20_000_000:
                z.write(p, f"harbor/{p.relative_to(out).as_posix()}")
        if ledger.is_file():
            z.write(ledger, "ledger.sqlite")
    print(f"已打包：{dest}（{dest.stat().st_size / 1e6:.1f} MB）")
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    home = Path.home() / "tw-harbor"
    for name in ("fetch", "run", "report", "bundle"):
        p = sub.add_parser(name)
        if name in ("fetch", "run"):
            p.add_argument("--dir", type=Path, default=home / "terminal-bench-2")
        if name != "fetch":
            p.add_argument("--out", type=Path, default=home / "jobs")
        if name == "run":
            p.add_argument("--concurrency", type=int, default=2)
            p.add_argument("--attempts", type=int, default=1)
            p.add_argument("--task", action="append", help="只跑这些（默认 10 题子集）")
            p.add_argument("--thinking", action="store_true")
            p.add_argument("--allow-peak", action="store_true")
            p.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "fetch":
        cmd_fetch(a.dir)
    elif a.cmd == "run":
        return cmd_run(a.dir, a.out, concurrency=a.concurrency, attempts=a.attempts, tasks=a.task or TASKS,
                       thinking=a.thinking, allow_peak=a.allow_peak, dry_run=a.dry_run)  # fmt: skip
    elif a.cmd == "report":
        cmd_report(a.out)
    else:
        cmd_bundle(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
