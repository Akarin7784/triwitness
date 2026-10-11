"""评测用 Agent（spec 004 §11，W1-30）。

- null：什么都不改 → 判分管线必须给 0（AC3 下限）。
- oracle（“作弊 Agent”）：越权拿到 solution/solve.sh 直接执行 → 必须全部解决（AC3 上限，证明判分能识别正确修复）。
- tamper：不修代码，只放一个让所有测试“通过”的 conftest.py 并声称成功 → Grader 必须判 0 并标记篡改，
  报告里记为虚假成功（04 §4.4 的结构性防线）。
- llm：真实 AgentLoop（run_task）；默认回放模式不联网。
三个假 Agent 不调模型，免费；它们也写最小轨迹（task_started / task_finished），结果目录格式一致。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol

from pydantic import BaseModel

from triwitness.core.events import TaskFinishedPayload, TaskStartedPayload
from triwitness.core.models import Budget, CostReport, FileChange, FinishReport
from triwitness.cost.report import CostLedger
from triwitness.eval.task import EvalTask
from triwitness.harness.config import HarnessConfig
from triwitness.harness.loop import RouterLike
from triwitness.harness.run import run_task
from triwitness.llm.pricing import pricing_version
from triwitness.sandbox.base import Sandbox
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools

AgentKind = Literal["null", "oracle", "tamper", "llm"]
AgentStatus = Literal[
    "finished", "budget_exhausted", "stuck", "error", "needs_human", "context_thrash", "context_overflow"
]

TAMPER_CONFTEST = """import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    for item in items:
        item.runtest = lambda: None
"""


class AgentRun(BaseModel):
    status: AgentStatus
    claimed_success: bool
    diff: str
    cost: CostReport | None = None
    steps: int = 0
    error: str | None = None
    finish: FinishReport | None = None  # 验证器（W3-13）要读复现路径与自述风险


class EvalAgent(Protocol):
    name: AgentKind

    async def solve(self, task: EvalTask, sandbox: Sandbox, rec: TrajectoryRecorder) -> AgentRun: ...


def _zero_cost(task_id: str) -> CostReport:
    return CostLedger(task_id=task_id, pricing_version=pricing_version()).report()


def _start(rec: TrajectoryRecorder, task: EvalTask, agent: str) -> None:
    rec.emit(TaskStartedPayload(issue_title=task.config.task.description or task.id, repo=task.id,
                                config_hash=agent, mode="eval", display=f"{task.id} · {agent}"))  # fmt: skip


def _finish(rec: TrajectoryRecorder, task: EvalTask, run: AgentRun, report: FinishReport | None) -> AgentRun:
    status = "done" if run.claimed_success else "failed"
    rec.emit(TaskFinishedPayload(status=status, finish_report=report, cost_report=run.cost or _zero_cost(task.id),
                                 display="完成" if run.claimed_success else "未修改"))  # fmt: skip
    run.finish = report
    return run


def _claim(summary: str, path: str) -> FinishReport:
    return FinishReport(summary=summary, changes=[FileChange(path=path, kind="modified")], tests_passed=True,
                        confidence=0.9)  # fmt: skip


class NullAgent:
    name: AgentKind = "null"

    async def solve(self, task: EvalTask, sandbox: Sandbox, rec: TrajectoryRecorder) -> AgentRun:
        _start(rec, task, self.name)
        return _finish(rec, task, AgentRun(status="finished", claimed_success=False, diff=""), None)


class OracleAgent:
    """越权读取参考解并执行（仅用于验证判分管线；真实 Agent 的沙箱里没有 solution/）。"""

    name: AgentKind = "oracle"

    async def solve(self, task: EvalTask, sandbox: Sandbox, rec: TrajectoryRecorder) -> AgentRun:
        _start(rec, task, self.name)
        wd = sandbox.spec.workdir.rstrip("/")
        stash = f"{wd}/.tw/oracle"  # .tw/ 不进 diff；用完仍删除
        for f in sorted(task.solution_dir.rglob("*")):
            if f.is_file():
                rel = f.relative_to(task.solution_dir).as_posix()
                await sandbox.write_file(f"{stash}/{rel}", f.read_bytes().replace(b"\r\n", b"\n"), 0o755)
        res = await sandbox.exec(f"bash {stash}/solve.sh", timeout_s=int(task.agent_timeout_sec), cwd=wd)
        await sandbox.exec(f"rm -rf {stash}", cwd=wd)
        ok = res.exit_code == 0
        diff = await sandbox.diff("base")
        run = AgentRun(status="finished" if ok else "error", claimed_success=ok, diff=diff,
                       error=None if ok else (res.stderr or res.stdout)[-500:])  # fmt: skip
        return _finish(rec, task, run, _claim("执行参考解", "solution/solve.sh") if ok else None)


class TamperAgent:
    """不修代码，放一个让所有测试“通过”的 conftest.py，并声称修好了。"""

    name: AgentKind = "tamper"

    async def solve(self, task: EvalTask, sandbox: Sandbox, rec: TrajectoryRecorder) -> AgentRun:
        _start(rec, task, self.name)
        wd = sandbox.spec.workdir.rstrip("/")
        await sandbox.write_file(f"{wd}/conftest.py", TAMPER_CONFTEST.encode())
        run = AgentRun(status="finished", claimed_success=True, diff=await sandbox.diff("base"))
        return _finish(rec, task, run, _claim("所有测试通过", "conftest.py"))


class LLMAgent:
    name: AgentKind = "llm"

    def __init__(
        self,
        router_factory: Callable[[], RouterLike],
        *,
        budget: Budget | None = None,
        harness: HarnessConfig | None = None,
        category: str = "baseline",
        config_hash: str = "baseline",
    ) -> None:
        self.router_factory = router_factory
        self.budget = budget or Budget.for_eval()
        self.harness = harness
        self.category = category
        self.config_hash = config_hash

    async def solve(self, task: EvalTask, sandbox: Sandbox, rec: TrajectoryRecorder) -> AgentRun:
        budget = self.budget  # 0.3.2：任务 [tw] max_cost_cny 不再执行
        harness = self.harness or HarnessConfig.default()
        res = await run_task(
            recorder=rec,
            router=self.router_factory(),
            registry=ToolRegistry(default_tools(names=harness.tools)),
            sandbox=sandbox,
            issue_title=task.config.task.description or task.id,
            task_prompt=task.instruction,
            repo=task.id,
            budget=budget,
            config_hash=self.config_hash,
            test_command=task.tw.test_cmd,
            mode="eval",
            config=harness,
            category=self.category,
        )
        # 评审无结论记为未解决（Eva 2026-10-12）：不算 agent 声称成功
        claimed = (res.status == "done" and res.finish is not None and res.finish.tests_passed
                   and not res.review_inconclusive)  # fmt: skip
        return AgentRun(
            status="error" if res.outcome.status == "cancelled" else res.outcome.status,
            claimed_success=claimed,
            diff=res.diff,
            cost=res.cost,
            steps=res.outcome.steps,
            error=res.outcome.reason if res.outcome.status != "finished" else None,
            finish=res.finish,
        )


FAKE_AGENTS: dict[str, Callable[[], EvalAgent]] = {"null": NullAgent, "oracle": OracleAgent, "tamper": TamperAgent}

__all__ = ["FAKE_AGENTS", "AgentKind", "AgentRun", "EvalAgent", "LLMAgent", "NullAgent", "OracleAgent", "TamperAgent"]
