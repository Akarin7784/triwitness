"""W8-05 `tw eval reproduce <run>`：用相同的任务 / 配置 / 模型 ID 重跑一次旧评测，并与原结果逐题对比。

- 输入：旧结果目录（含 run.json），或 `evals/results/<名字>`；
- 计划：run.json 里的 configs（RunConfig 原样）+ tasks（任务 id，到 evals/tasks 下按 id 找目录）+ 实际跑过的尝试次数；
- 运行由 CLI 交给 EvalRunner（默认回放 ¥0；`--live` 才真调用）；
- 对比：每个 (配置, 任务, 尝试) 原来 / 现在是否解决、花费；一致率；模型快照（served_model）前后是否相同；
- 永远附带提示：DeepSeek 等服务端模型可能已更新（同一模型 ID 不等于同一权重），结果有差异是正常的。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from triwitness.core.errors import ConfigError

BJ = timezone(timedelta(hours=8))
SERVER_WARNING = (
    "注意：模型服务端可能已更新（同一模型 ID 不保证同一权重 / 同一推理栈），"
    "且采样有随机性；复现结果与原结果有差异是正常的，不代表代码回归。"
)


@dataclass
class ReproducePlan:
    source: Path
    configs: list[dict[str, Any]]
    task_ids: list[str]
    attempts: int
    models: dict[str, int] = field(default_factory=dict)
    live: bool = False


def resolve_run(ref: str | Path, results_root: Path = Path("evals/results")) -> Path:
    """路径、`evals/results/<ref>`，或 results 下唯一一个名为 ref 的含 run.json 的目录。"""
    p = Path(ref)
    for cand in (p, results_root / str(ref)):
        if (cand / "run.json").is_file():
            return cand
    hits = (
        [d.parent for d in results_root.rglob("run.json") if d.parent.name == str(ref)] if results_root.is_dir() else []
    )
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise ConfigError(f"{ref} 不唯一：{', '.join(str(h) for h in hits[:5])}；请给完整路径")
    raise ConfigError(f"找不到评测结果 {ref}（需要含 run.json 的目录）")


def _results(run_dir: Path) -> dict[tuple[str, str, int], dict[str, Any]]:
    out: dict[tuple[str, str, int], dict[str, Any]] = {}
    for f in sorted(run_dir.rglob("result.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if "task_id" not in d:
            continue
        out[(str(d.get("config")), str(d["task_id"]), int(d.get("attempt", 1)))] = d
    return out


def served_models(run_dir: Path) -> dict[str, int]:
    seen: dict[str, int] = {}
    for traj in run_dir.rglob("trajectory.jsonl"):
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


def load_plan(run_dir: Path) -> ReproducePlan:
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    configs = list(meta.get("configs") or [])
    if not configs:
        raise ConfigError(f"{run_dir}/run.json 没有 configs")
    for c in configs:
        model = (c.get("executor") or {}).get("model")
        if model is not None and model != "deepseek-flash":
            raise ConfigError(f"{c.get('name')}：executor.model 只允许 deepseek-flash（ADR-0002），收到 {model}")
    res = _results(run_dir)
    attempts = max((k[2] for k in res), default=1)
    task_ids = list(meta.get("tasks") or sorted({k[1] for k in res}))
    return ReproducePlan(source=run_dir, configs=configs, task_ids=task_ids, attempts=attempts,
                         models=served_models(run_dir), live=bool(meta.get("live")))  # fmt: skip


def find_task_dirs(task_ids: list[str], root: Path = Path("evals/tasks")) -> tuple[list[Path], list[str]]:
    """按任务 id 在 evals/tasks 下找目录（task.toml 所在目录名即 id）。返回 (找到的目录, 缺失的 id)。"""
    index: dict[str, Path] = {}
    for toml in root.rglob("task.toml"):
        index.setdefault(toml.parent.name, toml.parent)
    found = [index[t] for t in task_ids if t in index]
    missing = [t for t in task_ids if t not in index]
    return found, missing


def compare(orig_dir: Path, new_dir: Path) -> dict[str, Any]:
    a, b = _results(orig_dir), _results(new_dir)
    # 只把复现计划里的任务算作“缺少”（--task 只复现子集时，其余题不是缺失）
    try:
        planned = set(json.loads((new_dir / "run.json").read_text(encoding="utf-8")).get("tasks") or [])
    except (OSError, json.JSONDecodeError):
        planned = set()
    planned = planned or {k[1] for k in a}
    rows = []
    for key in sorted(set(a) & set(b)):
        ra, rb = a[key], b[key]
        rows.append({"config": key[0], "task_id": key[1], "attempt": key[2],
                     "orig_resolved": bool(ra.get("resolved")), "new_resolved": bool(rb.get("resolved")),
                     "orig_cost_cny": ra.get("cost_cny"), "new_cost_cny": rb.get("cost_cny")})  # fmt: skip
    n = len(rows)
    agree = sum(1 for r in rows if r["orig_resolved"] == r["new_resolved"])
    m_a, m_b = served_models(orig_dir), served_models(new_dir)
    return {
        "source": str(orig_dir),
        "reproduction": str(new_dir),
        "compared": n,
        "missing_in_reproduction": [f"{k[0]}/{k[1]}/{k[2]}" for k in sorted(set(a) - set(b)) if k[1] in planned],
        "agreement": round(agree / n, 4) if n else None,
        "orig_solved": sum(r["orig_resolved"] for r in rows),
        "new_solved": sum(r["new_resolved"] for r in rows),
        "orig_cost_cny": round(sum(float(r["orig_cost_cny"] or 0) for r in rows), 4),
        "new_cost_cny": round(sum(float(r["new_cost_cny"] or 0) for r in rows), 4),
        "orig_models": m_a,
        "new_models": m_b,
        "model_snapshot_changed": bool(m_a and m_b and set(m_a) != set(m_b)),
        "rows": rows,
        "warning": SERVER_WARNING,
        "generated_at": datetime.now(BJ).isoformat(timespec="seconds"),
    }


def render_markdown(cmp: dict[str, Any]) -> str:
    lines = ["# 评测复现对比（tw eval reproduce）", "", f"> {cmp['warning']}", "",
             f"- 原结果：`{cmp['source']}`", f"- 复现：`{cmp['reproduction']}`",
             f"- 对比 {cmp['compared']} 次；结论一致率 "
             + (f"{cmp['agreement']:.0%}" if cmp["agreement"] is not None else "-"),
             f"- 解决数：原 {cmp['orig_solved']} → 现 {cmp['new_solved']}；"
             f"花费：原 ¥{cmp['orig_cost_cny']:.4f} → 现 ¥{cmp['new_cost_cny']:.4f}",
             f"- 模型快照：原 {cmp['orig_models'] or '?'} → 现 {cmp['new_models'] or '?'}"
             + ("（**快照名变了**）" if cmp["model_snapshot_changed"] else ""), ""]  # fmt: skip
    if cmp["missing_in_reproduction"]:
        lines += [f"- 复现缺少（基础设施错误或未跑）：{', '.join(cmp['missing_in_reproduction'])}", ""]
    lines += ["| 配置 | 任务 | 尝试 | 原 | 现 | 原 ¥ | 现 ¥ |", "|---|---|---|---|---|---|---|"]
    for r in cmp["rows"]:
        lines.append(f"| {r['config']} | {r['task_id']} | {r['attempt']} | {'✓' if r['orig_resolved'] else '✗'} | "
                     f"{'✓' if r['new_resolved'] else '✗'} | {r['orig_cost_cny']} | {r['new_cost_cny']} |")  # fmt: skip
    return "\n".join(lines) + "\n"


def write_comparison(orig_dir: Path, new_dir: Path) -> dict[str, Any]:
    cmp = compare(orig_dir, new_dir)
    (new_dir / "reproduce.json").write_text(json.dumps(cmp, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (new_dir / "reproduce.md").write_text(render_markdown(cmp), encoding="utf-8")
    return cmp


__all__ = ["SERVER_WARNING", "ReproducePlan", "compare", "find_task_dirs", "load_plan", "render_markdown",
           "resolve_run", "served_models", "write_comparison"]  # fmt: skip
