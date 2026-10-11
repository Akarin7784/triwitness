"""W4-14 评审者消融：在 W4-13 注入缺陷集（evals/reviewer/items）上比较几种评审配置。

用法（仓库根目录；真调需要 TW_LLM_MODE=live 与 DEEPSEEK_API_KEY，只用 deepseek-flash）：
    python scripts/reviewer_ablation.py prepare --out out/ablation            # 下载 / 复制基线源码，建每题的 git 仓库
    python scripts/reviewer_ablation.py run --out out/ablation --parallel 4   # 跑各臂（可中断，重跑跳过已完成）
    python scripts/reviewer_ablation.py score --out out/ablation              # 汇总检出率 / 误报率（Wilson 95% CI）
    python scripts/reviewer_ablation.py bundle --out out/ablation             # 结果 + 账本打成一个 zip

臂（arm）：
    none            不评审（计算得出：检出 0、误报 0，零调用）
    same            普通评审提示（reviewer-plain），flash 思考 effort=high —— 与执行者同配置的“同模型复查”
    adversarial     对抗式提示（reviewer.md），flash 思考 effort=max（当前路由默认）
    checklist_t03   清单式提示，flash 非思考，temperature=0.3
    checklist_t10   清单式提示，flash 非思考，temperature=1.0
    consensus_*     事后计算：adversarial 与某个 checklist 臂都判阻断才算阻断（不额外调用）

判定（score）：
    缺陷题“检出”= 有一条 blocker/major 发现落在注入文件、行号与注入行相差 ≤ --tol（默认 3）；
    “宽松检出”= 同文件任一 blocker/major，或 verdict=request_changes；
    干净题“误报”= 出现任何 blocker（verdict 退回）；“误报（含 major）”= 出现 blocker 或 major。
    findings.csv 列出全部发现，供人工复核位置匹配的边界情况。
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
import time
import tomllib
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "evals" / "reviewer" / "items"
MANIFEST = ROOT / "evals" / "reviewer" / "manifest.json"
TASKS = ROOT / "evals" / "tasks"
BJ = timezone(timedelta(hours=8))
MODEL = "deepseek/deepseek-flash"  # 只允许 flash（路由里的规范名；实际服务名记在结果 served_model）


@dataclass(frozen=True)
class Arm:
    name: str
    variant: str  # roles/reviewer._VARIANTS 的键（adversarial / checklist / plain）
    thinking: bool
    effort: str | None = None
    temperature: float | None = None


ARMS: dict[str, Arm] = {
    "same": Arm("same", "plain", True, "high"),
    "adversarial": Arm("adversarial", "adversarial", True, "max"),
    "checklist_t03": Arm("checklist_t03", "checklist", False, None, 0.3),
    "checklist_t10": Arm("checklist_t10", "checklist", False, None, 1.0),
}
DEFAULT_ARMS = list(ARMS)


# ---------------------------------------------------------------- 工具函数


def is_peak(now: datetime | None = None) -> bool:
    """北京时间工作日 9–12、14–18 为高峰（Eva 要求避开）。"""
    t = (now or datetime.now(BJ)).astimezone(BJ)
    return t.weekday() < 5 and (9 <= t.hour < 12 or 14 <= t.hour < 18)


def manifest() -> list[dict[str, Any]]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]


def task_dir(task: str) -> Path:
    for split in ("dev", "test"):
        d = TASKS / split / task
        if d.is_dir():
            return d
    raise SystemExit(f"找不到任务 {task}")


def git(*args: str, cwd: Path) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "ablation",
        "GIT_AUTHOR_EMAIL": "ablation@localhost",
        "GIT_COMMITTER_NAME": "ablation",
        "GIT_COMMITTER_EMAIL": "ablation@localhost",
    }
    r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{r.stderr.strip()[:500]}")
    return r.stdout


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


# ---------------------------------------------------------------- prepare


def _fetch_source(task: str, cache: Path) -> Path:
    """基线源码：合成任务复制 environment/repo；swe 任务下载 base_commit 的 GitHub 源码包（缓存）。"""
    d = task_dir(task)
    dest = cache / "src" / task
    if dest.is_dir():
        return dest
    local = d / "environment" / "repo"
    tmp = dest.with_name(task + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    if local.is_dir():
        shutil.copytree(local, tmp, ignore=shutil.ignore_patterns(".git"))
    else:
        meta = tomllib.loads((d / "task.toml").read_text(encoding="utf-8"))["metadata"]
        repo = meta["repo"].removeprefix("https://github.com/").removesuffix(".git")
        url = f"https://codeload.github.com/{repo}/tar.gz/{meta['base_commit']}"
        print(f"  下载 {repo}@{meta['base_commit'][:10]}", flush=True)
        with urllib.request.urlopen(url, timeout=300) as r:
            data = r.read()
        tmp.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            for m in tf.getmembers():
                parts = Path(m.name).parts[1:]  # 去掉顶层 <repo>-<sha>/
                if not parts or m.issym() or m.islnk() or ".." in parts:
                    continue
                m.name = str(Path(*parts))
                tf.extract(m, tmp, filter="data") if sys.version_info >= (3, 12) else tf.extract(m, tmp)
    tmp.rename(dest)
    return dest


def cmd_prepare(out: Path, only: list[str] | None, repos: Path) -> None:
    repos.mkdir(parents=True, exist_ok=True)
    for it in manifest():
        if only and it["id"] not in only:
            continue
        dest = repos / it["id"]
        if (dest / ".git").is_dir():
            continue
        src = _fetch_source(it["task"], repos.parent / "cache")
        tmp = dest.with_name(it["id"] + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(src, tmp)
        git("init", "-q", "-b", "main", cwd=tmp)
        git("add", "-A", cwd=tmp)
        git("commit", "-q", "--no-verify", "-m", "base", cwd=tmp)
        patch = ITEMS / it["id"] / "patch.diff"
        git("apply", "--whitespace=nowarn", str(patch), cwd=tmp)
        git("add", "-A", cwd=tmp)
        git("commit", "-q", "--no-verify", "-m", "candidate patch", cwd=tmp)
        tmp.rename(dest)
        print(f"  {it['id']} 就绪", flush=True)
    print(f"prepare 完成：{repos}")


# ---------------------------------------------------------------- run


def _arm_router(arm: Arm) -> Any:
    from triwitness.llm.router import Router

    base = Router.deepseek_default()
    routes = dict(base.routes)
    r = routes["reviewer"]
    if r.model != MODEL or any(m != MODEL for m in r.fallback):
        raise SystemExit(f"reviewer 路由不是只用 {MODEL}：{r.model} / {r.fallback}，拒绝运行")
    routes["reviewer"] = r.model_copy(update={"thinking": arm.thinking, "effort": arm.effort if arm.thinking else None})

    class ArmRouter(Router):
        async def complete(self, req: Any, **kw: Any) -> Any:  # type: ignore[override]
            upd: dict[str, Any] = {}
            if req.role == "reviewer":
                if arm.temperature is not None:
                    upd["temperature"] = arm.temperature
                if arm.thinking and arm.effort:
                    upd["effort"] = arm.effort
                if not arm.thinking:
                    upd["effort"] = None
            return await super().complete(req.model_copy(update=upd) if upd else req, **kw)

    return ArmRouter(routes, base.clients, vendor_policy=base.vendor_policy)


async def _one_job(
    it: dict[str, Any], arm: Arm, rep: int, out: Path, router: Any, lock: asyncio.Lock, *, repos: Path, work: Path
) -> None:
    from triwitness.core.ids import new_run_id, new_task_id
    from triwitness.core.models import Budget
    from triwitness.harness.config import HarnessConfig
    from triwitness.roles.reviewer import ReviewInput, run_variant
    from triwitness.sandbox.base import SandboxSpec
    from triwitness.sandbox.local import LocalSandboxBackend
    from triwitness.telemetry.trajectory import TrajectoryRecorder
    from triwitness.tools.base import ToolContext

    res_path = out / "results" / f"{it['id']}__{arm.name}__r{rep}.json"
    repo = repos / it["id"]
    run_id = new_run_id()
    run_dir = out / "runs" / f"{it['id']}__{arm.name}__r{rep}"
    shutil.rmtree(run_dir, ignore_errors=True)
    home = work  # worktree 放容器本地盘（Windows 挂载目录上跑 git 慢且易出权限问题）
    async with lock:  # 同一仓库并发 git worktree add 会抢锁
        sb = await LocalSandboxBackend(home=home).create(SandboxSpec(repo=repo, run_id=run_id, network="none"))
    t0 = time.monotonic()
    rec = TrajectoryRecorder(new_task_id(), run_id, run_dir=run_dir)
    row: dict[str, Any] = {
        "item": it["id"],
        "task": it["task"],
        "kind": it["kind"],
        "truth": it["defect"],
        "arm": arm.name,
        "rep": rep,
        "model": MODEL,
    }
    try:
        diff = git("diff", "HEAD~1", "HEAD", cwd=repo)
        issue = (ITEMS / it["id"] / "issue.md").read_text(encoding="utf-8")
        cfg = HarnessConfig.default()
        ctx = ToolContext(sandbox=sb, task_id=rec.task_id, run_id=run_id)
        vr = await run_variant(
            arm.variant,  # type: ignore[arg-type]
            ReviewInput(issue=issue, diff=diff),
            router=router,
            rec=rec,
            ctx=ctx,
            cfg=cfg,
            budget=Budget(),
            mode="eval",
            category="reviewer-ablation",
        )
        rv = vr.review
        row.update(
            path=vr.path,
            served_model=vr.model,
            verdict=rv.verdict if rv else None,
            findings=[f.model_dump() for f in rv.findings] if rv else [],
            error=None,
        )
    except Exception as e:
        row.update(verdict=None, findings=[], error=f"{type(e).__name__}: {str(e)[:300]}")
    finally:
        await sb.close()
    calls = [e for e in rec.events if e.kind == "model_call"]
    row["calls"] = len(calls)
    row["cost_cny"] = round(sum(float(e.payload.get("cost_cny") or 0) for e in calls), 6)
    for k in ("input_tokens", "cache_hit_tokens", "output_tokens"):
        row[k] = sum(int((e.payload.get("usage") or {}).get(k) or 0) for e in calls)
    row["models"] = sorted({str(e.payload.get("model")) for e in calls})
    row["elapsed_s"] = round(time.monotonic() - t0, 1)
    res_path.write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
    tag = row["verdict"] or ("ERR " + (row["error"] or ""))[:60]
    print(f"  {it['id']:<16} {arm.name:<14} r{rep} {tag}  ¥{row['cost_cny']:.4f}", flush=True)


async def cmd_run(
    out: Path,
    arms: list[str],
    repeats: int,
    parallel: int,
    only: list[str] | None,
    allow_peak: bool,
    limit: int | None,
    *,
    repos: Path,
    work: Path,
) -> int:
    if os.environ.get("TW_LLM_MODE") != "live":
        print("提示：未设置 TW_LLM_MODE=live（record 模式会命中本地缓存，重复样本不独立）", file=sys.stderr)
    (out / "results").mkdir(parents=True, exist_ok=True)
    items = [it for it in manifest() if not only or it["id"] in only]
    missing = [it["id"] for it in items if not (repos / it["id"] / ".git").is_dir()]
    if missing:
        raise SystemExit(f"这些题还没 prepare：{missing[:5]}…")
    routers = {a: _arm_router(ARMS[a]) for a in arms}
    jobs = [
        (it, ARMS[a], r)
        for r in range(repeats)
        for a in arms
        for it in items
        if not (out / "results" / f"{it['id']}__{a}__r{r}.json").is_file()
    ]
    if limit is not None:
        jobs = jobs[:limit]
    print(f"待跑 {len(jobs)} 个（{len(items)} 题 × {len(arms)} 臂 × {repeats} 次，已完成的跳过），并发 {parallel}")
    locks = {it["id"]: asyncio.Lock() for it in items}
    sem = asyncio.Semaphore(parallel)
    stopped = 0

    async def guarded(job: tuple[dict[str, Any], Arm, int]) -> None:
        nonlocal stopped
        async with sem:
            if not allow_peak and is_peak():
                stopped += 1
                return
            await _one_job(*job, out, routers[job[1].name], locks[job[0]["id"]], repos=repos, work=work)

    await asyncio.gather(*(guarded(j) for j in jobs))
    if stopped:
        print(f"进入北京时间高峰，{stopped} 个未跑；高峰过后重跑同一命令即可续上。")
        return 3
    return 0


# ---------------------------------------------------------------- score


def _norm(p: str | None) -> str:
    return (p or "").replace("\\", "/").lstrip("./").removeprefix("repo/").removeprefix("workspace/repo/")


def classify(row: dict[str, Any], tol: int) -> dict[str, bool]:
    fs = row.get("findings") or []
    serious = [f for f in fs if f.get("severity") in ("blocker", "major")]
    blocker = any(f.get("severity") == "blocker" for f in fs) or row.get("verdict") == "request_changes"
    t: dict[str, Any] = row.get("truth") or {}
    if row["kind"] == "clean":
        return {"fp": blocker, "fp_major": blocker or bool(serious), "ok": row.get("verdict") is not None}
    file = _norm(t["file"])
    same_file = [
        f for f in serious if _norm(f.get("file")).endswith(file) or file.endswith(_norm(f.get("file")) or "\0")
    ]
    hit = any(f.get("line") is not None and abs(int(f["line"]) - int(t["line"])) <= tol for f in same_file)
    hit_blocker = any(
        f.get("severity") == "blocker" and f.get("line") is not None and abs(int(f["line"]) - int(t["line"])) <= tol
        for f in same_file
    )
    return {
        "hit": hit,
        "hit_blocker": hit_blocker,
        "loose": bool(same_file) or blocker,
        "blocked": blocker,
        "ok": row.get("verdict") is not None,
    }


def _rate(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.0%} [{lo:.0%}, {hi:.0%}]" if n else "—"


def cmd_score(out: Path, tol: int) -> None:
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((out / "results").glob("*.json"))]
    if not rows:
        raise SystemExit("没有结果")
    by: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        r["cls"] = classify(r, tol)
        by.setdefault(r["arm"], []).append(r)
    # 事后共识：adversarial ∧ checklist_*（同一题同一次重复）
    adv = {(r["item"], r["rep"]): r for r in by.get("adversarial", [])}
    for ck in [a for a in by if a.startswith("checklist")]:
        name = "consensus_" + ck.removeprefix("checklist_")
        for r in by[ck]:
            a = adv.get((r["item"], r["rep"]))
            if a is None:
                continue
            c1, c2 = a["cls"], r["cls"]
            merged = {k: bool(c1.get(k)) and bool(c2.get(k)) for k in c1}
            merged["ok"] = bool(c1.get("ok")) and bool(c2.get("ok"))
            by.setdefault(name, []).append({**r, "arm": name, "cls": merged, "cost_cny": a["cost_cny"] + r["cost_cny"]})
    lines = [
        f"# 评审者消融结果（W4-14）\n\n题目 {len({r['item'] for r in rows})}，结果 {len(rows)} 条，"
        f"位置容差 ±{tol} 行。"
        "检出 = blocker/major 落在注入位置；误报 = 干净补丁被判 blocker。区间为 Wilson 95%。\n",
        "| 臂 | 检出（位置） | 检出（blocker@位置） | 宽松检出 | 误报（blocker） | 误报（含 major） "
        "| 失败 | ¥/次 | 合计 ¥ |",
        "|---|---|---|---|---|---|---|---|---|",
        "| none | 0% | 0% | 0% | 0% | 0% | 0 | 0 | 0 |",
    ]
    summary: dict[str, Any] = {}
    for arm in sorted(by):
        rs = by[arm]
        d = [r for r in rs if r["kind"] == "defect"]
        c = [r for r in rs if r["kind"] == "clean"]
        cnt = {k: sum(bool(r["cls"].get(k)) for r in d) for k in ("hit", "hit_blocker", "loose")}
        fp = sum(bool(r["cls"].get("fp")) for r in c)
        fpm = sum(bool(r["cls"].get("fp_major")) for r in c)
        fail = sum(not r["cls"].get("ok") for r in rs)
        cost = sum(float(r.get("cost_cny") or 0) for r in rs)
        summary[arm] = {
            "n_defect": len(d),
            "n_clean": len(c),
            **cnt,
            "fp": fp,
            "fp_major": fpm,
            "failed": fail,
            "cost_cny": round(cost, 4),
        }
        lines.append(
            f"| {arm} | {_rate(cnt['hit'], len(d))} | {_rate(cnt['hit_blocker'], len(d))} | "
            f"{_rate(cnt['loose'], len(d))} | {_rate(fp, len(c))} | {_rate(fpm, len(c))} | {fail} | "
            f"{cost / max(len(rs), 1):.4f} | {cost:.4f} |"
        )
    cats = sorted({r["truth"]["category"] for r in rows if r["kind"] == "defect"})
    lines += [
        "\n## 按缺陷类别（检出/题数，位置判定）\n",
        "| 类别 | " + " | ".join(sorted(by)) + " |",
        "|---|" + "---|" * len(by),
    ]
    for cat in cats:
        cells = []
        for arm in sorted(by):
            d = [r for r in by[arm] if r["kind"] == "defect" and r["truth"]["category"] == cat]
            cells.append(f"{sum(bool(r['cls'].get('hit')) for r in d)}/{len(d)}")
        lines.append(f"| {cat} | " + " | ".join(cells) + " |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    with (out / "findings.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["item", "kind", "arm", "rep", "truth_file", "truth_line", "verdict", "severity", "file", "line", "message"]
        )
        for r in rows:
            t = r.get("truth") or {}
            for f in r.get("findings") or [{}]:
                w.writerow(
                    [
                        r["item"],
                        r["kind"],
                        r["arm"],
                        r["rep"],
                        t.get("file"),
                        t.get("line"),
                        r.get("verdict"),
                        f.get("severity"),
                        f.get("file"),
                        f.get("line"),
                        (f.get("message") or "")[:300],
                    ]
                )
    print("\n".join(lines))


# ---------------------------------------------------------------- bundle


def cmd_bundle(out: Path, ledger: Path | None) -> Path:
    stamp = datetime.now(BJ).strftime("%Y%m%d-%H%M")
    dest = out.parent / f"reviewer-ablation-{stamp}.zip"
    ledger = ledger or Path(os.environ.get("TW_HOME", Path.home() / ".triwitness")) / "ledger.sqlite"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in ("results", "runs"):
            for p in sorted((out / sub).rglob("*")) if (out / sub).is_dir() else []:
                if p.is_file() and "/.tw/" not in p.as_posix():
                    z.write(p, f"ablation/{p.relative_to(out).as_posix()}")
        for name in ("report.md", "summary.json", "findings.csv", "run.log", "env.json"):
            if (out / name).is_file():
                z.write(out / name, f"ablation/{name}")
        if ledger.is_file():
            z.write(ledger, "ledger.sqlite")
    print(f"已打包：{dest}（{dest.stat().st_size / 1e6:.1f} MB）")
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "run", "score", "bundle"):
        p = sub.add_parser(name)
        p.add_argument("--out", type=Path, default=ROOT / "out" / "ablation")
        if name in ("prepare", "run"):
            p.add_argument("--items", help="逗号分隔的题目 id（默认全部 40 题）")
            p.add_argument("--repos", type=Path, help="每题 git 仓库所在目录（默认 <out>/repos）")
        if name == "run":
            p.add_argument("--arms", default=",".join(DEFAULT_ARMS))
            p.add_argument("--repeats", type=int, default=1)
            p.add_argument("--parallel", type=int, default=4)
            p.add_argument("--limit", type=int, help="最多跑几个（冒烟用）")
            p.add_argument("--allow-peak", action="store_true", help="允许在北京时间高峰跑（默认拒绝）")
            p.add_argument("--work", type=Path, help="沙箱 worktree 目录（默认 <out>/tw-sandbox）")
        if name == "score":
            p.add_argument("--tol", type=int, default=3)
        if name == "bundle":
            p.add_argument("--ledger", type=Path)
    a = ap.parse_args(argv)
    out = a.out.resolve()
    only = a.items.split(",") if getattr(a, "items", None) else None
    repos = (getattr(a, "repos", None) or out / "repos").resolve()
    if a.cmd == "prepare":
        cmd_prepare(out, only, repos)
    elif a.cmd == "run":
        arms = [x.strip() for x in a.arms.split(",") if x.strip()]
        bad = [x for x in arms if x not in ARMS]
        if bad:
            raise SystemExit(f"未知的臂：{bad}（可选 {list(ARMS)}）")
        if not a.allow_peak and is_peak():
            print("现在是北京时间高峰（工作日 9–12、14–18），不跑。加 --allow-peak 可强制。", file=sys.stderr)
            return 3
        work = (a.work or out / "tw-sandbox").resolve()
        return asyncio.run(
            cmd_run(out, arms, a.repeats, max(1, a.parallel), only, a.allow_peak, a.limit, repos=repos, work=work)
        )
    elif a.cmd == "score":
        cmd_score(out, a.tol)
    else:
        cmd_bundle(out, a.ledger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
