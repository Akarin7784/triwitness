"""EvalRunner（spec 004 §5、§6.2/6.4–6.7，W1-31）。

任务 × 配置 × 尝试，并发跑；每个 attempt：Grader 同规格新建 Agent 沙箱 → Agent → diff → Grader 另起干净沙箱判分。
结果目录 evals/results/<北京时间戳>/<config>/<task>/<attempt>/{result.json, patch.diff, trajectory.jsonl,
verifier.log}（ADR-0001 #6）。result.json 原子写入，存在即跳过（断点续跑；Ctrl-C 后重跑不重复执行）。

费用护栏（只对 llm Agent 且 live 时生效；假 Agent 与回放模式不花钱）：
- 启动前：高峰闸门（PeakGate.check_start）、预估总额 > max_total_cny 不开始、全局账本 / 类别信封预检；
- 运行中：跨入高峰不再派发新 attempt（已在跑的允许完成），未跑的留给下次续跑；
- 每个任务：Budget.max_cost_cny = min(配置, 任务 [tw] max_cost_cny)，由 TaskBudgetGuard 执行。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from triwitness.core.errors import ConfigError, TriWitnessError
from triwitness.cost.ledger import GlobalLedger
from triwitness.eval.agents import FAKE_AGENTS, AgentKind, AgentRun, EvalAgent
from triwitness.eval.grade import Grader, GradeResult
from triwitness.eval.task import EvalTask
from triwitness.llm.gate import PeakGate, estimate_run
from triwitness.llm.pricing import to_shanghai
from triwitness.telemetry.trajectory import TrajectoryRecorder

log = logging.getLogger(__name__)

DEFAULT_RESULTS = Path("evals/results")
# W1-34 首跑校准（2026-10-10，dev 10 × 1，思考 high）：平均输入 198k（SWE 379k，最高 1.09M）、输出 4.8k（SWE 8.6k），
# 命中 95%，¥0.033/任务。默认值取 SWE 实测的约 2 倍，给 test 集更难的任务留余量；有历史结果时优先用历史均值。
DEFAULT_AVG_INPUT = 800_000
DEFAULT_AVG_OUTPUT = 20_000


class EstimateTooHigh(TriWitnessError):
    """AC7：预估超过上限，不开始运行。"""


class RunConfig(BaseModel):
    name: str
    agent: AgentKind = "llm"
    executor: dict[str, Any] = Field(default_factory=dict)
    attempts: int = Field(default=1, ge=1)
    budget_profile: str = "eval"
    harness: str | None = None
    category: str = "baseline"  # 全局账本类别信封（configs/budget.yaml envelopes_cny）

    @classmethod
    def load(cls, path: Path) -> RunConfig:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        model = (data.get("executor") or {}).get("model")
        if model is not None and model != "deepseek-flash":
            raise ConfigError(f"{path}：executor.model 只允许 deepseek-flash（ADR-0002），收到 {model}")
        return cls.model_validate(data)

    @classmethod
    def fake(cls, agent: AgentKind) -> RunConfig:
        return cls(name=f"{agent}-agent", agent=agent)


class AttemptResult(BaseModel):
    task_id: str
    config: str
    agent: AgentKind
    attempt: int
    resolved: bool
    reward: float | None
    agent_status: str
    agent_claimed_success: bool
    false_success: bool  # 声称修好但判分不过
    tamper_paths: list[str] = Field(default_factory=list)
    ignored_paths: list[str] = Field(default_factory=list)
    patch_applied: bool = True
    cost_cny: float = 0.0
    tokens_in: int = 0
    tokens_cached: int = 0
    tokens_out: int = 0
    peak_calls: int = 0
    steps: int = 0
    wall_s: float = 0.0
    trajectory_id: str
    live: bool = False
    error: str | None = None


@dataclass(frozen=True)
class Job:
    task: EvalTask
    config: RunConfig
    attempt: int

    def rel(self) -> Path:
        return Path(self.config.name) / self.task.id / str(self.attempt)


@dataclass
class RunSummary:
    out_dir: Path
    done: list[AttemptResult] = field(default_factory=list)
    skipped_existing: int = 0
    deferred_peak: int = 0
    infra_errors: dict[str, str] = field(default_factory=dict)
    estimate_cny: float = 0.0


def run_stamp(now: datetime) -> str:
    return f"{to_shanghai(now):%Y-%m-%dT%H-%M-%S}"


def historical_avg_cost(results_root: Path) -> float | None:
    """历史平均每任务成本：已有 result.json 里 llm Agent 的实际花费。"""
    costs = []
    if results_root.is_dir():
        for p in results_root.glob("*/*/*/*/result.json"):
            try:
                r = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if r.get("agent") == "llm" and r.get("live") and r.get("cost_cny", 0) > 0:
                costs.append(float(r["cost_cny"]))
    return sum(costs) / len(costs) if costs else None


@dataclass(frozen=True)
class UsageHistory:
    """历史 live 结果的每任务平均用量（`tw eval estimate` 用；W1 校准值是没有历史时的先验）。"""

    n: int
    avg_input_tokens: int
    avg_output_tokens: int
    cache_hit_rate: float
    avg_cost_cny: float


def historical_usage(results_root: Path) -> UsageHistory | None:
    rows: list[dict[str, Any]] = []
    if results_root.is_dir():
        for p in results_root.glob("*/*/*/*/result.json"):
            try:
                r = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if r.get("agent") == "llm" and r.get("live") and r.get("tokens_in", 0) > 0:
                rows.append(r)
    if not rows:
        return None
    n = len(rows)
    tin = sum(int(r["tokens_in"]) for r in rows)
    return UsageHistory(
        n=n,
        avg_input_tokens=round(tin / n),
        avg_output_tokens=round(sum(int(r.get("tokens_out", 0)) for r in rows) / n),
        cache_hit_rate=round(sum(int(r.get("tokens_cached", 0)) for r in rows) / tin, 4),
        avg_cost_cny=round(sum(float(r.get("cost_cny", 0.0)) for r in rows) / n, 4),
    )


def default_per_task_estimate() -> float:
    return estimate_run(tasks=1, avg_input_tokens=DEFAULT_AVG_INPUT, avg_output_tokens=DEFAULT_AVG_OUTPUT).off_peak_cny


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class EvalRunner:
    def __init__(
        self,
        *,
        grader: Grader,
        llm_agent_factory: Callable[[RunConfig], EvalAgent] | None = None,
        live: bool = False,
        gate: PeakGate | None = None,
        ledger: GlobalLedger | None = None,
        max_total_cny: float = 50.0,
        per_task_estimate_cny: float | None = None,
        results_root: Path = DEFAULT_RESULTS,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.grader = grader
        self.llm_agent_factory = llm_agent_factory
        self.live = live
        self.gate = gate or PeakGate(now=now)
        self.ledger = ledger
        self.max_total_cny = max_total_cny
        self.per_task_estimate_cny = per_task_estimate_cny
        self.results_root = results_root
        self.now = now

    # ------------------------------------------------------------ 计划与预检
    def plan(self, tasks: list[EvalTask], configs: list[RunConfig], *, attempts: int | None = None,
             limit: int | None = None) -> list[Job]:  # fmt: skip
        tasks = tasks[:limit] if limit else tasks
        return [Job(t, c, a) for c in configs for t in tasks for a in range(1, (attempts or c.attempts) + 1)]

    def estimate(self, jobs: list[Job]) -> float:
        paid = [j for j in jobs if j.config.agent == "llm"]
        if not paid or not self.live:
            return 0.0
        per = self.per_task_estimate_cny
        if per is None:
            per = historical_avg_cost(self.results_root) or default_per_task_estimate()
        return round(per * len(paid), 4)

    def preflight(self, jobs: list[Job]) -> float:
        """启动前护栏；返回预估总额。不通过时抛异常，什么都不运行。"""
        paid = [j for j in jobs if j.config.agent == "llm"]
        if paid and not self.live and os.environ.get("TW_LLM_MODE", "replay").strip().lower() != "replay":
            raise ConfigError("TW_LLM_MODE 不是 replay：真实调用必须显式 --live（并经过高峰闸门与预算预检）")
        if paid and self.llm_agent_factory is None:
            raise ConfigError("llm Agent 需要 llm_agent_factory")
        est = self.estimate(jobs)
        if not paid or not self.live:
            return est
        self.gate.check_start("评测")
        if est > self.max_total_cny:
            raise EstimateTooHigh(
                f"预估 ¥{est:.2f}（{len(paid)} 个 attempt）超过上限 ¥{self.max_total_cny:g}，不开始；"
                "调高 --max-total-cny 或用 --limit 减少任务"
            )
        if self.ledger is not None:
            for cat in sorted({j.config.category for j in paid}):
                n = sum(1 for j in paid if j.config.category == cat)
                self.ledger.precheck(est * n / len(paid), cat)
        return est

    # ------------------------------------------------------------ 运行
    async def run(
        self,
        tasks: list[EvalTask],
        configs: list[RunConfig],
        *,
        attempts: int | None = None,
        concurrency: int = 4,
        limit: int | None = None,
        out_dir: Path | None = None,
    ) -> RunSummary:
        jobs = self.plan(tasks, configs, attempts=attempts, limit=limit)
        est = self.preflight(jobs)
        out = out_dir or self.results_root / run_stamp(self.now())
        out.mkdir(parents=True, exist_ok=True)
        summary = RunSummary(out_dir=out, estimate_cny=est)
        _write_json_atomic(out / "run.json", {
            "started_at": to_shanghai(self.now()).isoformat(), "live": self.live, "estimate_cny": est,
            "max_total_cny": self.max_total_cny, "configs": [c.model_dump() for c in configs],
            "tasks": [t.id for t in (tasks[:limit] if limit else tasks)],
            "peak_flag": self.gate.report_flag,
        })  # fmt: skip
        sem = asyncio.Semaphore(max(1, concurrency))

        async def one(job: Job) -> None:
            d = out / job.rel()
            if (d / "result.json").exists():
                summary.skipped_existing += 1
                return
            async with sem:
                if self.live and job.config.agent == "llm" and not self.gate.may_dispatch():
                    summary.deferred_peak += 1  # 跨入高峰：不派发，留给续跑
                    return
                try:
                    res = await self.run_attempt(job, d)
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # 基础设施错误：不写 result.json，续跑时重试
                    log.exception("attempt 失败：%s", job.rel().as_posix())
                    summary.infra_errors[job.rel().as_posix()] = f"{type(e).__name__}: {e}"[:500]
                    return
                summary.done.append(res)

        await asyncio.gather(*(one(j) for j in jobs))
        if summary.infra_errors:
            _write_json_atomic(out / "errors.json", summary.infra_errors)
        return summary

    def _agent(self, cfg: RunConfig) -> EvalAgent:
        if cfg.agent == "llm":
            assert self.llm_agent_factory is not None
            return self.llm_agent_factory(cfg)
        return FAKE_AGENTS[cfg.agent]()

    async def run_attempt(self, job: Job, d: Path) -> AttemptResult:
        d.mkdir(parents=True, exist_ok=True)
        t0 = time.monotonic()
        rec = TrajectoryRecorder(job.task.id, f"{job.config.name}-{job.task.id}-{job.attempt}", run_dir=d)
        agent = self._agent(job.config)
        sb = await self.grader.new_sandbox(job.task)
        try:
            run: AgentRun = await agent.solve(job.task, sb, rec)
        finally:
            await sb.close()
        (d / "patch.diff").write_text(run.diff, encoding="utf-8")
        grade: GradeResult = await self.grader.grade(job.task, run.diff)
        (d / "verifier.log").write_text(grade.log_tail + (f"\n{grade.error}" if grade.error else ""), encoding="utf-8")
        tin = tcached = tout = peak = 0
        if run.cost is not None:
            for ln in run.cost.lines:
                tin += ln.usage.input_tokens
                tcached += ln.usage.cache_hit_tokens
                tout += ln.usage.output_tokens
                peak += ln.peak_calls
        res = AttemptResult(
            task_id=job.task.id,
            config=job.config.name,
            agent=job.config.agent,
            attempt=job.attempt,
            resolved=grade.resolved,
            reward=grade.reward,
            agent_status=run.status,
            agent_claimed_success=run.claimed_success,
            false_success=run.claimed_success and not grade.resolved,
            tamper_paths=grade.tamper_paths,
            ignored_paths=grade.ignored_paths,
            patch_applied=grade.patch_applied,
            cost_cny=run.cost.total_cny if run.cost else 0.0,
            tokens_in=tin,
            tokens_cached=tcached,
            tokens_out=tout,
            peak_calls=peak,
            steps=run.steps,
            wall_s=round(time.monotonic() - t0, 2),
            trajectory_id=(job.rel() / "trajectory.jsonl").as_posix(),
            live=self.live and job.config.agent == "llm",
            error=run.error or grade.error,
        )
        _write_json_atomic(d / "result.json", res.model_dump())
        return res


__all__ = [
    "AttemptResult",
    "EstimateTooHigh",
    "EvalRunner",
    "Job",
    "RunConfig",
    "RunSummary",
    "UsageHistory",
    "default_per_task_estimate",
    "historical_avg_cost",
    "historical_usage",
    "run_stamp",
]
