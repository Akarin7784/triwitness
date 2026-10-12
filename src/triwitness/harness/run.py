"""任务驱动的兼容入口（W1-24 / W1-32；W4-07 起由 InProcessOrchestrator 实现，spec 010 §8）。

`run_task(...)` 的参数与返回值不变：内部构造 `orchestrator.inprocess.InProcessOrchestrator` 并运行。
`tw run`、桌面端、`tw eval` 都经过它；harness 配置里 Planner / Reviewer 关闭时行为与 W3 一致。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from triwitness.core.models import Budget
from triwitness.github.publish import Publisher
from triwitness.harness.approvals import Approver
from triwitness.harness.config import HarnessConfig
from triwitness.harness.loop import RouterLike
from triwitness.harness.prepare import PrepareOptions
from triwitness.harness.resume import ResumeState
from triwitness.memory.context import MemoryContext
from triwitness.orchestrator.inprocess import FinishStatus, InProcessOrchestrator, TaskResult
from triwitness.prompts import load_prompt
from triwitness.sandbox.base import Sandbox
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools.base import ToolRegistry
from triwitness.verify.pipeline import VerifyOptions

EXECUTOR_PROMPT = load_prompt("executor").text  # 版本化提示：src/triwitness/prompts/executor.md


async def run_task(
    *,
    recorder: TrajectoryRecorder,
    router: RouterLike,
    registry: ToolRegistry,
    sandbox: Sandbox,
    issue_title: str,
    task_prompt: str,
    repo: str,
    budget: Budget,
    config_hash: str,
    issue_number: int | None = None,
    test_command: str | None = None,
    mode: Literal["background", "eval"] = "background",
    agents_md: str | None = None,
    config: HarnessConfig | None = None,
    tw_dir: str = "/workspace/.tw",
    category: str = "dev",
    verify: VerifyOptions | None = None,
    prepare: PrepareOptions | None = None,
    stream: bool = False,
    resume: ResumeState | None = None,
    progress_dir: Path | None = None,
    approver: Approver | None = None,
    publisher: Publisher | None = None,
    memory: MemoryContext | None = None,
) -> TaskResult:
    orch = InProcessOrchestrator(
        recorder=recorder, router=router, registry=registry, sandbox=sandbox, issue_title=issue_title,
        task_prompt=task_prompt, repo=repo, budget=budget, config_hash=config_hash, issue_number=issue_number,
        test_command=test_command, mode=mode, agents_md=agents_md, config=config, tw_dir=tw_dir, category=category,
        verify=verify, prepare=prepare, stream=stream, resume=resume, progress_dir=progress_dir, approver=approver,
        publisher=publisher, memory=memory,
    )  # fmt: skip
    return await orch.run()


__all__ = ["EXECUTOR_PROMPT", "FinishStatus", "TaskResult", "run_task"]
