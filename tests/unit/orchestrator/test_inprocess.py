"""spec 010 AC4 / AC5 / AC8（W4-05 / 06 / 07 / 08）：InProcessOrchestrator 端到端。

FakeRouter 按角色分脚本 + 真实 none 后端（git worktree）+ 真 pytest；不调用模型。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from triwitness.core.models import Budget
from triwitness.harness.approvals import ApprovalDecision
from triwitness.harness.config import HarnessConfig
from triwitness.harness.run import TaskResult, run_task
from triwitness.harness.testing import FakeRouter, call, say
from triwitness.llm.types import LLMRequest, LLMResponse, Message
from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.store.sqlite import TaskStore
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools
from triwitness.verify.pipeline import EphemeralBackend, VerifyOptions
from triwitness.verify.testing import make_repo

PY = f'"{Path(sys.executable).as_posix()}" -m pytest -q -p no:cacheprovider'
REPRO = "tests/tw_repro/test_issue_1.py"
ISSUE = "`add(1, 2) == 3` 应该成立，现在 add(1, 2) 返回 -1。"
WRITE_REPRO = call("write_file", path=REPRO, content="from calc import add\n\n\ndef test_issue():\n"
                   "    assert add(1, 2) == 3\n")  # fmt: skip
WRONG = call("edit_file", path="calc.py", old_str="a - b", new_str="a * b + 1")
FIX_WRONG = call("edit_file", path="calc.py", old_str="a * b + 1", new_str="a + b")
RIGHT = call("edit_file", path="calc.py", old_str="a - b", new_str="a + b")
BLOCKER = {
    "severity": "blocker",
    "file": "calc.py",
    "line": 2,
    "message": "a * b + 1 只在 (1, 2) 上等于和；add(2, 0) = 1",
    "suggestion": "改成 a + b",
}


def finish() -> Message:
    return say(call("finish", summary="add 改成加法", changes=[{"path": "calc.py", "kind": "modified"}],
                    tests_run=[f"pytest {REPRO}"], tests_passed=True, confidence=0.9,
                    repro={"path": REPRO, "cmd": f"{PY} {REPRO}"}))  # fmt: skip


def plan(risk: str = "L1", **kw: Any) -> Message:
    args = {
        "root_cause_hypothesis": "calc.add 用了减法",
        "affected_files": ["calc.py"],
        "repro_strategy": "test",
        "acceptance_criteria": [{"id": "AC1", "description": "add(1, 2) == 3", "check": "test", "detail": REPRO}],
        "steps": [{"id": "S1", "goal": "把减法改成加法", "files": ["calc.py"]}],
        "estimated_risk": risk,
        **kw,
    }
    return say(call("submit_plan", **args))


def review(*findings: dict[str, Any]) -> Message:
    verdict = "request_changes" if any(f["severity"] == "blocker" for f in findings) else "approve"
    return say(call("submit_review", verdict=verdict, summary="见 findings", findings=list(findings)))


class RoleRouter:
    """按角色分脚本；评审的清单式变体单独一份脚本。"""

    vendor_policy = "single_vendor"

    def __init__(self, **scripts: list[Message]) -> None:
        self.r = {k: FakeRouter(v) for k, v in scripts.items()}

    async def complete(self, req: LLMRequest, **kw: Any) -> LLMResponse:
        key = str(req.role)
        if key == "reviewer" and "清单式" in (req.messages[0].content or ""):
            key = "reviewer_checklist"
        return await self.r[key].complete(req, **kw)


@pytest.fixture
def env(tmp_path: Path) -> tuple[LocalSandboxBackend, Path]:
    repo = make_repo(tmp_path, {"calc.py": "def add(a, b):\n    return a - b\n", "tests/__init__.py": "",
                                "tests/tw_repro/__init__.py": "",
                                "tests/test_calc.py": "from calc import add\n\n\ndef test_zero():\n"
                                                      "    assert add(2, 0) == 2\n"})  # fmt: skip
    return LocalSandboxBackend(home=tmp_path / "home"), repo


def cfg(**orch: Any) -> HarnessConfig:
    c = HarnessConfig.load("harness/orchestrated-1m.yaml")
    for k, v in orch.items():
        section, _, field = k.partition("__")
        setattr(getattr(c.orchestration, section), field, v)
    return c


async def go(env: tuple, router: RoleRouter, *, verify: bool = False, config: HarnessConfig | None = None,
             mode: str = "background", approver: Any = None, store: TaskStore | None = None,
             ) -> tuple[TaskResult, TrajectoryRecorder]:  # type: ignore[type-arg]  # fmt: skip
    backend, repo = env
    sb = await backend.create(SandboxSpec(repo=repo, run_id="exec1"))
    rec = TrajectoryRecorder("t_o", "r_o", run_dir=repo.parent / "run")
    if store is not None:
        rec.subscribe(store.observe)
    opts = None
    if verify:
        opts = VerifyOptions(backend=EphemeralBackend(backend), spec=SandboxSpec(repo=repo), static_tools=("ruff",),
                             python=Path(sys.executable).as_posix())  # fmt: skip
    try:
        res = await run_task(recorder=rec, router=router, registry=ToolRegistry(default_tools()), sandbox=sb,
                             issue_title="add 是减法", task_prompt=ISSUE, repo="o/r", budget=Budget(),
                             config_hash="c", test_command=PY, verify=opts, tw_dir=str(sb.tw_dir),  # type: ignore[attr-defined]
                             config=config or cfg(), mode=mode, approver=approver)  # type: ignore[arg-type]  # fmt: skip
    finally:
        await sb.finish("discard")  # type: ignore[attr-defined]
    return res, rec


def states(rec: TrajectoryRecorder) -> list[str]:
    return [str(e.payload["to"]) for e in rec.events if e.kind == "state_change"]


def kinds(rec: TrajectoryRecorder, kind: str) -> list[dict[str, Any]]:
    return [e.payload for e in rec.events if e.kind == kind]


async def test_full_flow_plan_verify_review_pass(env: tuple, tmp_path: Path) -> None:  # type: ignore[type-arg]
    """AC8：PLANNING → EXECUTING → VERIFYING → REVIEWING → PACKAGING → DONE，证据包带计划与同厂商评审标注。"""
    router = RoleRouter(
        planner=[say(call("read_file", path="calc.py"), call("grep", pattern="def add")), plan()],
        executor=[say(WRITE_REPRO), say(RIGHT), finish()],
        reviewer=[review({"severity": "minor", "file": "calc.py", "line": 2, "message": "可以加类型注解"})],
    )
    with TaskStore(tmp_path / "tw.db") as store:
        res, rec = await go(env, router, verify=True, store=store)
        (row,) = store.list_tasks()
        assert (row.state, row.status) == ("done", "done")
    assert res.status == "done", res.outcome
    assert states(rec) == ["preparing", "planning", "executing", "verifying", "reviewing", "packaging", "done"]
    assert res.states == ["received", *states(rec)]
    assert res.plan is not None and res.plan.estimated_risk == "L1" and res.plan.task_id == "t_o"
    # Planner 的两个只读调用并发执行，然后提交
    assert [e.payload["tool"] for e in rec.events if e.kind == "tool_call" and e.role == "planner"] == [
        "read_file", "grep", "submit_plan"]  # fmt: skip
    # 计划进了 Executor 的任务描述，验收标准交给验证，根因进证据包
    first = router.r["executor"].requests[0].messages[1].content or ""
    assert '<plan source="planner">' in first and "AC1" in first
    v = res.verification
    assert v is not None and v.evidence.verdict == "pass"
    assert v.evidence.root_cause == "calc.add 用了减法"
    assert v.evidence.review_variant == "adversarial" and v.evidence.vendor_policy == "single_vendor"
    assert [f.severity for f in v.evidence.findings] == ["minor"]
    assert "评审" in v.pr_body
    (rv,) = kinds(rec, "review")
    assert rv["blocking"] is False and rv["round"] == 1 and rv["variant"] == "adversarial"
    roles = {e.role for e in rec.events if e.kind == "model_call"}
    assert roles == {"planner", "executor", "reviewer"}
    # 5 次 planner/executor + 1 次 reviewer，每次 ¥0.001，全部进任务成本
    assert res.cost.total_cny == pytest.approx(0.006)
    saved = json.loads((env[1].parent / "run" / "artifacts" / "plan.json").read_text(encoding="utf-8"))
    assert saved["acceptance_criteria"][0]["id"] == "AC1"


async def test_review_blocker_reworks_in_same_context(env: tuple) -> None:  # type: ignore[type-arg]
    """AC5：blocker → 同一上下文续写返工 → 第二轮评审通过。"""
    router = RoleRouter(planner=[plan()], executor=[say(WRONG), finish(), say(FIX_WRONG), finish()],
                        reviewer=[review(BLOCKER), review()])  # fmt: skip
    res, rec = await go(env, router)
    assert res.status == "done" and res.review_rounds == 1 and res.unresolved_blockers == 0
    assert states(rec) == ["preparing", "planning", "executing", "reviewing", "executing", "reviewing", "packaging",
                           "done"]  # fmt: skip
    assert "a + b" in res.diff
    reqs = router.r["executor"].requests
    rework = reqs[2].messages
    assert len(rework) > len(reqs[1].messages)  # 只追加
    assert rework[: len(reqs[1].messages)] == reqs[1].messages[: len(reqs[1].messages)]
    assert "评审发现阻断问题" in (rework[-1].content or "") and "calc.py:2" in (rework[-1].content or "")
    first, second = kinds(rec, "review")
    assert (first["blocking"], second["blocking"], second["round"]) == (True, False, 2)


async def test_review_blockers_stop_at_cap(env: tuple) -> None:  # type: ignore[type-arg]
    router = RoleRouter(planner=[plan()], executor=[say(WRONG), finish(), say(text="我认为没问题"), finish()],
                        reviewer=[review(BLOCKER), review(BLOCKER)])  # fmt: skip
    res, rec = await go(env, router, config=cfg(reviewer__max_rounds=1))
    assert res.status == "done" and res.review_rounds == 1 and res.unresolved_blockers == 1
    assert states(rec)[-3:] == ["reviewing", "packaging", "done"]
    (fin,) = kinds(rec, "task_finished")
    assert "评审仍有 1 个阻断问题" in fin["display"]


async def test_unresolved_blocker_lands_in_evidence(env: tuple) -> None:  # type: ignore[type-arg]
    """验证通过但评审仍有 blocker（返工上限 0）：证据包里 blocker 为 open，风险计入 review_major_open。"""
    router = RoleRouter(planner=[plan()], executor=[say(WRITE_REPRO), say(RIGHT), finish()], reviewer=[review(BLOCKER)])
    res, _ = await go(env, router, verify=True, config=cfg(reviewer__max_rounds=0))
    v = res.verification
    assert v is not None and res.unresolved_blockers == 1
    assert [(f.severity, f.status) for f in v.evidence.findings] == [("blocker", "open")]
    assert "review_major_open" in {f.code for f in v.evidence.risk_factors}
    assert v.evidence.risk_level in ("L2", "L3")


async def test_consensus_split_does_not_rework(env: tuple) -> None:  # type: ignore[type-arg]
    router = RoleRouter(planner=[plan()], executor=[say(WRONG), finish()], reviewer=[review(BLOCKER)],
                        reviewer_checklist=[review()])  # fmt: skip
    res, rec = await go(env, router, config=cfg(reviewer__consensus=True))
    assert res.review_rounds == 0 and res.review is not None and not res.review.blocking
    (rv,) = kinds(rec, "review")
    assert rv["consensus"] is True and rv["variant"] == "adversarial+checklist"
    assert [f["severity"] for f in rv["findings"]] == ["major"]
    # 清单式变体用 effort=high
    req = router.r["reviewer_checklist"].requests[0]
    assert req.effort == "high" and router.r["reviewer"].requests[0].effort is None


async def test_consensus_agreement_reworks(env: tuple) -> None:  # type: ignore[type-arg]
    router = RoleRouter(
        planner=[plan()],
        executor=[say(WRONG), finish(), say(FIX_WRONG), finish()],
        reviewer=[review(BLOCKER), review()],
        reviewer_checklist=[review(BLOCKER), review()],
    )
    res, _ = await go(env, router, config=cfg(reviewer__consensus=True))
    assert res.review_rounds == 1 and "a + b" in res.diff


# ---------------------------------------------------------------- 计划确认（spec 010 §8 / §11 Q1–Q2）


async def test_plan_l2_without_channel_needs_human(env: tuple) -> None:  # type: ignore[type-arg]
    router = RoleRouter(planner=[plan("L2")], executor=[], reviewer=[])
    res, rec = await go(env, router)
    assert res.status == "needs_human" and res.diff == ""
    assert states(rec) == ["preparing", "planning", "await_plan_approval", "needs_human"]
    (req,) = kinds(rec, "approval_requested")
    assert req["tool"] == "Plan" and req["risk"] == "L2" and "风险预估 L2" in req["reason"]
    assert router.r["executor"].requests == []


async def test_open_questions_trigger_approval_and_user_approves(env: tuple) -> None:  # type: ignore[type-arg]
    seen: list[Any] = []

    async def approver(req: Any) -> ApprovalDecision:
        seen.append(req)
        return ApprovalDecision(decision="allow")

    router = RoleRouter(planner=[plan(open_questions=["负数要不要支持？"])], executor=[say(RIGHT), finish()],
                        reviewer=[review()])  # fmt: skip
    res, rec = await go(env, router, approver=approver)
    assert res.status == "done" and len(seen) == 1 and "待确认的问题" in seen[0].reason
    assert states(rec)[:4] == ["preparing", "planning", "await_plan_approval", "executing"]
    (resolved,) = kinds(rec, "approval_resolved")
    assert resolved["by"] == "user" and resolved["decision"] == "allow"


async def test_user_rejects_plan(env: tuple) -> None:  # type: ignore[type-arg]
    async def approver(req: Any) -> ApprovalDecision:
        return ApprovalDecision(decision="deny", comment="先别动构建")

    router = RoleRouter(planner=[plan(affected_files=["pyproject.toml"])], executor=[], reviewer=[])
    res, rec = await go(env, router, approver=approver)
    assert res.status == "cancelled" and states(rec)[-1] == "cancelled"
    (req,) = kinds(rec, "approval_requested")
    assert "pyproject.toml" in req["reason"]


@pytest.mark.parametrize(("risk", "status"), [("L2", "done"), ("L3", "cancelled")])
async def test_eval_mode_auto_policy(env: tuple, risk: str, status: str) -> None:  # type: ignore[type-arg]
    router = RoleRouter(planner=[plan(risk)], executor=[say(RIGHT), finish()], reviewer=[review()])
    res, rec = await go(env, router, mode="eval")
    assert res.status == status
    (resolved,) = kinds(rec, "approval_resolved")
    assert resolved["by"] == "policy" and not kinds(rec, "approval_requested")


async def test_planner_without_submission_continues(env: tuple) -> None:  # type: ignore[type-arg]
    """Planner 不提交（只说话 3 次 → stuck）：不阻断，Executor 无计划继续。"""
    router = RoleRouter(planner=[say(text="我想想")] * 3, executor=[say(RIGHT), finish()], reviewer=[review()])
    res, rec = await go(env, router)
    assert res.status == "done" and res.plan is None
    assert "无计划" in str([e.payload.get("display") for e in rec.events if e.kind == "state_change"])


async def test_planner_content_json_fallback(env: tuple) -> None:  # type: ignore[type-arg]
    body = json.loads(plan().tool_calls[0].arguments)  # type: ignore[index]
    text = "计划：\n```json\n" + json.dumps(body, ensure_ascii=False) + "\n```"
    router = RoleRouter(planner=[say(text=text)] * 3, executor=[say(RIGHT), finish()], reviewer=[review()])
    res, _ = await go(env, router)
    assert res.plan is not None and res.plan.root_cause_hypothesis == "calc.add 用了减法"


async def test_roles_off_keeps_w3_sequence(env: tuple) -> None:  # type: ignore[type-arg]
    router = RoleRouter(executor=[say(RIGHT), finish()])
    res, rec = await go(env, router, config=HarnessConfig.default())
    assert states(rec) == ["preparing", "executing", "packaging", "done"] and res.plan is None and res.review is None
