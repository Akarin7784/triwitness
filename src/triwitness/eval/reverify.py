"""`tw eval reverify`（W3-14 用）：在已保存的评测结果上只重跑验证阶段，不重跑 Executor。

输入：一次 `tw eval run` 的结果目录（<config>/<task>/<attempt>/result.json + patch.diff + trajectory.jsonl）。
- diff 取 patch.diff；FinishReport 取轨迹里 task_finished 的 finish_report（没有则 finish.json，再没有为 None）。
- 判分真值（resolved / false_success / 篡改）沿用原结果，不重新判分；隐藏测试不进入验证沙箱。
- 每个档位写成一个新配置 `<原配置>+<档位>`：<out>/<原配置>+<档位>/<task>/<attempt>/{result.json, verification.json}，
  report.md 里三档并排（none 档 = 原结果，不验证）。
- 续跑：已有 result.json 的跳过。model 档真实调用需显式 live，并过高峰闸门 + 预估上限（verify_estimate）。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from triwitness.core.errors import ConfigError
from triwitness.core.models import FinishReport
from triwitness.eval.report import load_results
from triwitness.eval.runner import AttemptResult, EstimateTooHigh, _write_json_atomic
from triwitness.eval.task import EvalTask
from triwitness.eval.verification import VerificationOutcome, VerifierMode, verify_run
from triwitness.eval.verify_estimate import estimate, sizes_from_results
from triwitness.llm.gate import PeakGate
from triwitness.sandbox.base import Sandbox
from triwitness.verify.verifier import RouterLike

log = logging.getLogger(__name__)
MODES: tuple[VerifierMode, ...] = ("none", "deterministic", "model")


@dataclass
class SavedAttempt:
    result: AttemptResult
    diff: str
    finish: FinishReport | None
    dir: Path


@dataclass
class ReverifySummary:
    out_dir: Path
    done: int = 0
    skipped_existing: int = 0
    missing_task: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    estimate_cny: float = 0.0
    verifier_cost_cny: float = 0.0


def _finish_from(d: Path) -> FinishReport | None:
    traj = d / "trajectory.jsonl"
    if traj.is_file():
        for line in reversed(traj.read_text(encoding="utf-8").splitlines()):
            if '"task_finished"' not in line:
                continue
            ev = json.loads(line)
            if ev.get("kind") == "task_finished" and ev.get("payload", {}).get("finish_report"):
                return FinishReport.model_validate(ev["payload"]["finish_report"])
    fin = d / "finish.json"
    return FinishReport.model_validate_json(fin.read_text(encoding="utf-8")) if fin.is_file() else None


def load_saved(src: Path) -> list[SavedAttempt]:
    out: list[SavedAttempt] = []
    for r in load_results(src):
        d = src / r.config / r.task_id / str(r.attempt)
        patch = d / "patch.diff"
        out.append(SavedAttempt(result=r, diff=patch.read_text(encoding="utf-8") if patch.is_file() else "",
                                finish=_finish_from(d), dir=d))  # fmt: skip
    return out


def _row(base: AttemptResult, mode: VerifierMode, ver: VerificationOutcome | None, err: str | None) -> AttemptResult:
    cfg = f"{base.config}+{mode}"
    return base.model_copy(update={
        "config": cfg,
        "trajectory_id": (Path(base.config) / base.task_id / str(base.attempt) / "trajectory.jsonl").as_posix(),
        "cost_cny": base.cost_cny - base.verifier_cost_cny + (ver.cost_cny if ver else 0.0),
        "verifier_mode": mode if mode != "none" else None,
        "verifier_verdict": ver.verdict if ver else None,
        "verifier_deterministic": ver.deterministic if ver else None,
        "verifier_model_verdict": ver.model_verdict if ver else None,
        "verify_repro_status": ver.repro_status if ver else None,
        "risk_level": ver.risk_level if ver else None,
        "verifier_cost_cny": ver.cost_cny if ver else 0.0,
        "verifier_error": err,
    })  # fmt: skip


async def reverify(
    src: Path,
    out: Path,
    *,
    tasks: dict[str, EvalTask],
    grader: Any,  # 只用 new_sandbox(task)：与判分同款的全新任务沙箱
    modes: tuple[VerifierMode, ...] = MODES,
    router_factory: Callable[[], RouterLike] | None = None,
    regression: bool = True,
    live: bool = False,
    gate: PeakGate | None = None,
    max_total_cny: float = 3.0,
    concurrency: int = 2,
    limit: int | None = None,
    configs: list[str] | None = None,
) -> ReverifySummary:
    if src.resolve() == out.resolve():
        raise ConfigError("输出目录不能和原结果目录相同（原结果只读）")
    saved = [s for s in load_saved(src) if not configs or s.result.config in configs]
    if limit is not None:
        saved = saved[:limit]
    summary = ReverifySummary(out_dir=out)
    if "model" in modes:
        if router_factory is None:
            raise ConfigError("model 档需要 router_factory")
        if live:
            (gate or PeakGate()).check_start("reverify（Verifier 模型）")
            wanted = {s.result.task_id for s in saved}
            sizes = [z for z in sizes_from_results(src) if z.task_id in wanted]
            summary.estimate_cny = estimate(sizes).high_cny if sizes else 0.0
            if summary.estimate_cny > max_total_cny:
                raise EstimateTooHigh(f"预估（保守）¥{summary.estimate_cny:.2f} 超过上限 ¥{max_total_cny:g}，不开始")
    out.mkdir(parents=True, exist_ok=True)
    meta = {"source": str(src), "modes": list(modes), "live": live, "estimate_cny": summary.estimate_cny,
            "configs": [{"name": f"{c}+{m}", "attempts": max(s.result.attempt for s in saved if s.result.config == c)}
                        for c in sorted({s.result.config for s in saved}) for m in modes],
            "tasks": sorted({s.result.task_id for s in saved})}  # fmt: skip
    (out / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    sem = asyncio.Semaphore(concurrency)

    async def one(s: SavedAttempt, mode: VerifierMode) -> None:
        r = s.result
        d = out / f"{r.config}+{mode}" / r.task_id / str(r.attempt)
        key = f"{r.config}+{mode}/{r.task_id}/{r.attempt}"
        if (d / "result.json").exists():
            summary.skipped_existing += 1
            return
        task = tasks.get(r.task_id)
        if task is None and mode != "none":
            summary.missing_task.append(key)
            return
        ver: VerificationOutcome | None = None
        err: str | None = None
        if mode != "none":
            assert task is not None
            async with sem:
                try:
                    ver = await verify_run(
                        issue=task.instruction, diff=s.diff, finish=s.finish,
                        new_sandbox=_factory(grader, task), mode=mode, test_cmd=task.tw.test_cmd,
                        run_regression=regression, router=_router(router_factory, mode),
                        task_id=task.id,
                    )  # fmt: skip
                except Exception as e:  # 单个 attempt 出错不影响其他
                    log.exception("reverify 失败：%s", key)
                    err = f"{type(e).__name__}: {e}"[:500]
                    summary.errors[key] = err
        d.mkdir(parents=True, exist_ok=True)
        if ver is not None:
            _write_json_atomic(d / "verification.json", ver.model_dump(mode="json"))
            summary.verifier_cost_cny += ver.cost_cny
        _write_json_atomic(d / "result.json", _row(r, mode, ver, err).model_dump())
        summary.done += 1

    await asyncio.gather(*(one(s, m) for m in modes for s in saved))
    if summary.errors:
        (out / "errors.json").write_text(json.dumps(summary.errors, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _router(factory: Callable[[], RouterLike] | None, mode: VerifierMode) -> RouterLike | None:
    return factory() if factory is not None and mode == "model" else None


def _factory(grader: Any, task: EvalTask) -> Callable[[], Awaitable[Sandbox]]:
    return lambda: grader.new_sandbox(task)


__all__ = ["MODES", "ReverifySummary", "SavedAttempt", "load_saved", "reverify"]
