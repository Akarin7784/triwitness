"""报告 v1（spec 004 §6.8，W1-32 → W2-24）：汇总 result.json → report.json + report.md。`tw eval report <dir>` 可重建。

每个配置一行：Resolved@1（带任务级 bootstrap 95% 置信区间）、解决数/有效任务数、总成本、平均每任务成本、
每解决任务成本、平均步数、平均耗时、虚假成功数（声称修好但判分不过）、缓存命中率（<90% 告警，W1-22）、
疑似篡改数，以及失败分类。

基础设施错误（errors.json 里没写出 result.json 的 attempt，以及判分没产出 reward 的 attempt）单独列出，
不计入 Resolved@1 的分母（04 §6.2）。
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, Field

from triwitness.eval.runner import AttemptResult

LOW_HIT_RATE = 0.9
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 0

# 失败分类（按优先级）：infra_error 不计入分母
CATEGORIES = ("resolved", "infra_error", "patch_not_applied", "false_success", "agent_error", "unresolved")


def classify(r: AttemptResult) -> str:
    if r.resolved:
        return "resolved"
    if r.patch_applied and r.reward is None:
        return "infra_error"  # 判分环境没产出 reward（不是 Agent 的错）
    if not r.patch_applied:
        return "patch_not_applied"
    if r.false_success:
        return "false_success"
    if r.agent_status != "finished" or r.error:
        return "agent_error"
    return "unresolved"


def bootstrap_ci(
    outcomes: list[bool], *, n: int = BOOTSTRAP_N, seed: int = BOOTSTRAP_SEED, alpha: float = 0.05
) -> tuple[float, float] | None:
    """任务级重采样的百分位 bootstrap 置信区间；固定种子保证报告可复现。"""
    if not outcomes:
        return None
    rng = random.Random(seed)
    k = len(outcomes)
    stats = sorted(sum(rng.choices(outcomes, k=k)) / k for _ in range(n))
    lo = stats[int(alpha / 2 * n)]
    hi = stats[min(n - 1, int((1 - alpha / 2) * n))]
    return round(lo, 4), round(hi, 4)


class ConfigRow(BaseModel):
    config: str
    agent: str
    tasks: int
    attempts: int
    resolved_at_1: float
    solved: int  # attempt 1 解决的任务数
    total_cost_cny: float
    avg_cost_per_task: float
    cost_per_resolved: float | None
    avg_steps: float
    avg_wall_s: float
    false_success: int
    tampered: int
    cache_hit_rate: float | None
    live: bool
    ci95: tuple[float, float] | None = None  # Resolved@1 的 bootstrap 95% 置信区间
    graded: int = 0  # 计入分母的 attempt 1 数（去掉 infra_error）
    failure_categories: dict[str, int] = Field(default_factory=dict)


class EvalReport(BaseModel):
    run_dir: str
    rows: list[ConfigRow]
    missing: list[str]  # 计划内但没有 result.json 的 attempt（中断 / 高峰暂停 / 基础设施错误）
    warnings: list[str]
    infra_errors: dict[str, str] = Field(default_factory=dict)  # attempt → 原因（errors.json + 判分无 reward）


def load_results(run_dir: Path) -> list[AttemptResult]:
    return [
        AttemptResult.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(run_dir.glob("*/*/*/result.json"))
    ]


def _planned(run_dir: Path) -> list[str]:
    meta = run_dir / "run.json"
    if not meta.exists():
        return []
    m = json.loads(meta.read_text(encoding="utf-8"))
    out = []
    for c in m.get("configs", []):
        for t in m.get("tasks", []):
            for a in range(1, int(c.get("attempts", 1)) + 1):
                out.append(f"{c['name']}/{t}/{a}")
    return out


def build_report(run_dir: Path) -> EvalReport:
    results = load_results(run_dir)
    rows: list[ConfigRow] = []
    warnings: list[str] = []
    for cfg in sorted({r.config for r in results}):
        rs = [r for r in results if r.config == cfg]
        cats = {id(r): classify(r) for r in rs}
        first = [r for r in rs if r.attempt == 1 and cats[id(r)] != "infra_error"]
        tasks = len({r.task_id for r in rs})
        solved = sum(r.resolved for r in first)
        outcomes = [r.resolved for r in sorted(first, key=lambda r: r.task_id)]
        cost = sum(r.cost_cny for r in rs)
        tin = sum(r.tokens_in for r in rs)
        hit = (sum(r.tokens_cached for r in rs) / tin) if tin else None
        row = ConfigRow(
            config=cfg,
            agent=rs[0].agent,
            tasks=tasks,
            attempts=len(rs),
            resolved_at_1=solved / len(first) if first else 0.0,
            solved=solved,
            total_cost_cny=round(cost, 4),
            avg_cost_per_task=round(cost / len(rs), 4),
            cost_per_resolved=round(cost / solved, 4) if solved else None,
            avg_steps=round(sum(r.steps for r in rs) / len(rs), 1),
            avg_wall_s=round(sum(r.wall_s for r in rs) / len(rs), 1),
            false_success=sum(r.false_success for r in rs),
            tampered=sum(bool(r.tamper_paths) for r in rs),
            cache_hit_rate=round(hit, 4) if hit is not None else None,
            live=any(r.live for r in rs),
            ci95=bootstrap_ci(outcomes),
            graded=len(first),
            failure_categories=dict(sorted(Counter(cats.values()).items(), key=lambda kv: CATEGORIES.index(kv[0]))),
        )
        rows.append(row)
        if hit is not None and hit < LOW_HIT_RATE:
            warnings.append(f"{cfg}：缓存命中率 {hit:.0%} < {LOW_HIT_RATE:.0%}（检查前缀稳定性）")
        if row.false_success:
            warnings.append(f"{cfg}：{row.false_success} 次虚假成功（声称修好但隐藏测试不过）")
        if row.tampered:
            warnings.append(f"{cfg}：{row.tampered} 次改动测试基础设施（Grader 已忽略这些改动）")
    done = {f"{r.config}/{r.task_id}/{r.attempt}" for r in results}
    missing = [p for p in _planned(run_dir) if p not in done]
    if missing:
        warnings.append(f"{len(missing)} 个 attempt 未完成（续跑：同一目录再跑一次）")
    infra = _errors(run_dir)
    for r in results:
        if classify(r) == "infra_error":
            infra[f"{r.config}/{r.task_id}/{r.attempt}"] = r.error or "判分未产出 reward"
    if infra:
        warnings.append(f"{len(infra)} 个基础设施错误，单独列出、不计入分母")
    return EvalReport(run_dir=str(run_dir), rows=rows, missing=missing, warnings=warnings, infra_errors=infra)


def _errors(run_dir: Path) -> dict[str, str]:
    p = run_dir / "errors.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _cny(x: float | None) -> str:
    return "—" if x is None else f"¥{x:.4f}"


def render_markdown(rep: EvalReport) -> str:
    head = (
        "| 配置 | Agent | Resolved@1（95% CI） | 解决/有效 | 总成本 | 平均每任务 | 每解决任务 | 平均步数 | 平均耗时 "
        "| 虚假成功 | 篡改 | 缓存命中 |\n|---|---|---|---|---|---|---|---|---|---|---|---|"
    )
    lines = [f"# 评测报告 · {Path(rep.run_dir).name}", "", head]
    for r in rep.rows:
        hit = "—" if r.cache_hit_rate is None else f"{r.cache_hit_rate:.0%}"
        live = "" if r.live else "（离线）" if r.agent == "llm" else ""
        ci = f"（{r.ci95[0]:.0%}–{r.ci95[1]:.0%}）" if r.ci95 else ""
        lines.append(
            f"| {r.config}{live} | {r.agent} | {r.resolved_at_1:.0%}{ci} | {r.solved}/{r.graded} "
            f"| {_cny(r.total_cost_cny)} | {_cny(r.avg_cost_per_task)} | {_cny(r.cost_per_resolved)} "
            f"| {r.avg_steps:g} | {r.avg_wall_s:g}s "
            f"| {r.false_success} | {r.tampered} | {hit} |"
        )
    if rep.rows:
        lines += ["", "## 失败分类", "", "| 配置 | " + " | ".join(CATEGORIES) + " |",
                  "|---|" + "---|" * len(CATEGORIES)]  # fmt: skip
        for r in rep.rows:
            lines.append(
                f"| {r.config} | " + " | ".join(str(r.failure_categories.get(c, 0)) for c in CATEGORIES) + " |"
            )
    if rep.infra_errors:
        lines += ["", "## 基础设施错误（不计入分母）", ""]
        lines += [f"- `{k}`：{v.splitlines()[0][:200] if v else ''}" for k, v in sorted(rep.infra_errors.items())]
    if rep.warnings:
        lines += ["", *[f"- ⚠ {w}" for w in rep.warnings]]
    return "\n".join(lines) + "\n"


def write_report(run_dir: Path) -> EvalReport:
    rep = build_report(run_dir)
    (run_dir / "report.json").write_text(rep.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(render_markdown(rep), encoding="utf-8")
    return rep


__all__ = [
    "CATEGORIES",
    "ConfigRow",
    "EvalReport",
    "bootstrap_ci",
    "build_report",
    "classify",
    "load_results",
    "render_markdown",
    "write_report",
]
