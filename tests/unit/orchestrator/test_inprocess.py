"""spec 010 AC4 / AC5 / AC8（W4-05 / 06 / 07 / 08）：InProcessOrchestrator 端到端。

FakeRouter 按角色分脚本 + 真实 none 后端（git worktree）+ 真 pytest；不调用模型。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, ClassVar

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
        if key == "reviewer" and "清单式" in (req.messages[0].content or "") and "reviewer_checklist" in self.r:
            key = "reviewer_checklist"  # 共识测试单独给清单式变体脚本；单评审（默认 checklist）用 reviewer 脚本
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


async def go(env: tuple, router: Any, *, verify: bool | VerifyOptions = False, config: HarnessConfig | None = None,
             mode: str = "background", approver: Any = None, store: TaskStore | None = None,
             tools: list[str] | None = None, progress_dir: Path | None = None, resume: Any = None,
             ) -> tuple[TaskResult, TrajectoryRecorder]:  # type: ignore[type-arg]  # fmt: skip
    backend, repo = env
    sb = await backend.create(SandboxSpec(repo=repo, run_id="exec1"))
    rec = TrajectoryRecorder("t_o", "r_o", run_dir=repo.parent / "run")
    if store is not None:
        rec.subscribe(store.observe)
    opts = verify if isinstance(verify, VerifyOptions) else None
    if verify is True:
        opts = VerifyOptions(backend=EphemeralBackend(backend), spec=SandboxSpec(repo=repo), static_tools=("ruff",),
                             python=Path(sys.executable).as_posix())  # fmt: skip
    try:
        res = await run_task(recorder=rec, router=router, registry=ToolRegistry(default_tools(names=tools)), sandbox=sb,
                             issue_title="add 是减法", task_prompt=ISSUE, repo="o/r", budget=Budget(),
                             config_hash="c", test_command=PY, verify=opts, tw_dir=str(sb.tw_dir),  # type: ignore[attr-defined]
                             config=config or cfg(), mode=mode, approver=approver,  # type: ignore[arg-type]
                             progress_dir=progress_dir, resume=resume)  # fmt: skip
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
    # 默认评审 = checklist（Eva 2026-10-12，W4-14）
    assert v.evidence.review_variant == "checklist" and v.evidence.vendor_policy == "single_vendor"
    assert v.evidence.review_status == "concluded"
    assert [f.severity for f in v.evidence.findings] == ["minor"]
    assert "评审" in v.pr_body
    (rv,) = kinds(rec, "review")
    assert rv["blocking"] is False and rv["round"] == 1 and rv["variant"] == "checklist"
    assert rv["inconclusive"] is False
    # checklist 变体：非思考 + temperature 1.0（覆盖路由的思考开关）
    (rq,) = router.r["reviewer"].requests
    assert rq.thinking_override is False and rq.temperature == 1.0 and rq.tool_choice == "auto"
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


READ_ONLY = say(call("read_file", path="calc.py"))


async def test_reviewer_inconclusive_eval_is_unresolved(env: tuple) -> None:  # type: ignore[type-arg]
    """评审强制提交后仍没结论：不静默放行——证据包 review_status=inconclusive、风险下限 L2；评测里记为未解决。"""
    router = RoleRouter(planner=[plan()], executor=[say(WRITE_REPRO), say(RIGHT), finish()],
                        reviewer=[READ_ONLY, READ_ONLY])  # fmt: skip
    res, rec = await go(env, router, verify=True, config=cfg(reviewer__max_turns=2), mode="eval")
    assert res.status == "done" and res.review_inconclusive and res.review is not None
    assert res.review.inconclusive and not res.review.blocking
    v = res.verification
    assert v is not None and v.evidence.review_status == "inconclusive"
    assert v.evidence.risk_level in ("L2", "L3")
    assert "floor:reviewer_inconclusive" in {f.code for f in v.evidence.risk_factors}
    (rv,) = kinds(rec, "review")
    assert rv["inconclusive"] is True and "无结论" in rv["display"]
    # 第二次（最后一次）评审调用是强制提交
    assert router.r["reviewer"].requests[-1].tool_choice != "auto"
    (fin,) = kinds(rec, "task_finished")
    assert "记为未解决" in fin["display"]


async def test_reviewer_inconclusive_interactive_needs_human(env: tuple) -> None:  # type: ignore[type-arg]
    router = RoleRouter(planner=[plan()], executor=[say(RIGHT), finish()], reviewer=[READ_ONLY, READ_ONLY])
    res, rec = await go(env, router, config=cfg(reviewer__max_turns=2))
    assert res.status == "needs_human" and res.review_inconclusive
    assert states(rec)[-2:] == ["reviewing", "needs_human"]
    (req,) = kinds(rec, "approval_requested")
    assert req["tool"] == "ReviewInconclusive"


@pytest.mark.parametrize(("decision", "status"), [("allow", "done"), ("deny", "failed")])
async def test_reviewer_inconclusive_interactive_decision(env: tuple, decision: str, status: str) -> None:  # type: ignore[type-arg]
    async def approver(req: Any) -> ApprovalDecision:
        return ApprovalDecision(decision=decision)  # type: ignore[arg-type]

    router = RoleRouter(planner=[plan()], executor=[say(RIGHT), finish()], reviewer=[READ_ONLY, READ_ONLY])
    res, rec = await go(env, router, config=cfg(reviewer__max_turns=2), approver=approver)
    assert res.status == status and res.review_inconclusive
    (resolved,) = [p for p in kinds(rec, "approval_resolved") if p["by"] == "user"]
    assert resolved["decision"] == decision


async def test_eval_agent_does_not_claim_success_when_review_inconclusive() -> None:
    """LLMAgent：评审无结论 → claimed_success=False（评测里记为未解决）。"""
    import inspect

    from triwitness.eval import agents

    src = inspect.getsource(agents.LLMAgent.solve)
    assert "not res.review_inconclusive" in src


async def test_consensus_split_does_not_rework(env: tuple) -> None:  # type: ignore[type-arg]
    router = RoleRouter(planner=[plan()], executor=[say(WRONG), finish()], reviewer=[review(BLOCKER)],
                        reviewer_checklist=[review()])  # fmt: skip
    res, rec = await go(env, router, config=cfg(reviewer__consensus=True))
    assert res.review_rounds == 0 and res.review is not None and not res.review.blocking
    (rv,) = kinds(rec, "review")
    assert rv["consensus"] is True and rv["variant"] == "adversarial+checklist"
    assert [f["severity"] for f in rv["findings"]] == ["major"]
    # 清单式变体：非思考 t=1.0（W4-14 checklist_t10）；对抗式沿用路由（思考 effort=max）
    req = router.r["reviewer_checklist"].requests[0]
    assert req.thinking_override is False and req.temperature == 1.0
    adv = router.r["reviewer"].requests[0]
    assert adv.effort is None and adv.thinking_override is None


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


@pytest.mark.parametrize(
    ("risk", "reject_from", "status"),
    [("L2", "never", "done"), ("L3", "never", "done"), ("L3", "L3", "cancelled")],
)
async def test_eval_mode_auto_policy(env: tuple, risk: str, reject_from: str, status: str) -> None:  # type: ignore[type-arg]
    """Eva 21:36：评测里计划全部自动批准（含 L3）；eval_reject_from 仍可配置回旧策略。"""
    router = RoleRouter(planner=[plan(risk)], executor=[say(RIGHT), finish()], reviewer=[review()])
    res, rec = await go(env, router, mode="eval", config=cfg(plan_approval__eval_reject_from=reject_from))
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


# ---------------------------------------------------------------- W4-10：ask_human
W1_ASK = ["bash", "edit_file", "finish", "grep", "list_files", "read_file", "run_tests", "write_file", "ask_human"]
ASK = call("ask_human", question="add 要支持字符串拼接吗？", options=["只要数字", "也支持字符串"])


async def test_ask_human_blocking_gets_answer(env: tuple) -> None:  # type: ignore[type-arg]
    seen: list[Any] = []

    async def approver(req: Any) -> ApprovalDecision:
        seen.append(req)
        return ApprovalDecision("allow", comment="只要数字")

    router = RoleRouter(planner=[plan()], executor=[say(ASK), say(RIGHT), finish()], reviewer=[review()])
    res, rec = await go(env, router, approver=approver, tools=W1_ASK)
    assert res.status == "done"
    (req,) = seen
    assert req.tool == "AskHuman" and "字符串拼接" in req.action and "也支持字符串" in req.action
    answer = router.r["executor"].requests[1].messages[-1]
    assert answer.role == "tool" and "用户的回答：只要数字" in (answer.content or "")
    (resolved,) = kinds(rec, "approval_resolved")
    assert resolved["by"] == "user" and resolved["comment"] == "只要数字"


async def test_ask_human_without_channel_pauses_and_is_resumable(env: tuple, tmp_path: Path) -> None:  # type: ignore[type-arg]
    router = RoleRouter(planner=[plan()], executor=[say(ASK), say(RIGHT), finish()])
    (tmp_path / "run1").mkdir()
    res, rec = await go(env, router, tools=W1_ASK, progress_dir=tmp_path / "run1")
    assert res.status == "needs_human" and "Executor 提问" in (res.outcome.reason or "")
    assert states(rec)[-1] == "needs_human"
    assert (tmp_path / "run1" / "resume" / "resume.json").is_file()


async def test_ask_human_non_blocking_and_eval(env: tuple) -> None:  # type: ignore[type-arg]
    nb = call("ask_human", question="要不要顺便加类型注解？", blocking=False)
    router = RoleRouter(planner=[plan()], executor=[say(nb), say(ASK), say(RIGHT), finish()], reviewer=[review()])
    res, rec = await go(env, router, tools=W1_ASK, mode="eval")
    assert res.status == "done"
    reqs = router.r["executor"].requests
    assert "不等待回答" in (reqs[1].messages[-1].content or "")
    assert "评测模式不能问人" in (reqs[2].messages[-1].content or "")
    assert "approval_requested" not in [e.kind for e in rec.events]
    (audit,) = kinds(rec, "approval_resolved")
    assert audit["by"] == "policy" and audit["decision"] == "deny"


# ---------------------------------------------------------------- spec 010 §11 Q6：计划确认的续跑点
async def test_plan_pending_saves_resume_point_and_resume_reuses_plan(env: tuple, tmp_path: Path) -> None:  # type: ignore[type-arg]
    from triwitness.core.ids import new_run_id
    from triwitness.harness.resume import load_resume

    home = tmp_path / "home2"
    first = new_run_id()
    run1 = home / "runs" / first
    run1.mkdir(parents=True)
    router = RoleRouter(planner=[plan("L2")])
    res, _ = await go(env, router, progress_dir=run1)
    assert res.status == "needs_human"
    doc = json.loads((run1 / "resume" / "resume.json").read_text(encoding="utf-8"))
    assert doc["stage"] == "await_plan_approval" and doc["files"] == []
    (run1 / "summary.json").write_text(json.dumps({"status": "needs_human"}), encoding="utf-8")
    state = load_resume(home, first)
    assert state.stage == "await_plan_approval"

    asked: list[Any] = []

    async def approver(req: Any) -> ApprovalDecision:
        asked.append(req)
        return ApprovalDecision("allow")

    router2 = RoleRouter(planner=[], executor=[say(WRITE_REPRO), say(RIGHT), finish()], reviewer=[review()])
    run2 = home / "runs" / new_run_id()
    run2.mkdir()
    res2, rec2 = await go(env, router2, approver=approver, progress_dir=run2, resume=state)
    assert res2.status == "done", res2.outcome
    assert router2.r["planner"].requests == []  # 没有重新规划
    assert [r.tool for r in asked] == ["Plan"] and "风险预估 L2" in asked[0].reason
    assert states(rec2)[:3] == ["preparing", "await_plan_approval", "executing"]
    first_prompt = router2.r["executor"].requests[0].messages[1].content or ""
    assert '<plan source="planner">' in first_prompt and "<resume" not in first_prompt


# ---------------------------------------------------------------- W4-08：cross_vendor（假模型，不联网）
class ScriptClient:
    """某个厂商的假客户端：按脚本回复，记录 (角色, 模型)。"""

    def __init__(self, script: list[Message]) -> None:
        self.fake = FakeRouter(script)
        self.calls: list[tuple[str, str]] = []

    async def complete(self, req: LLMRequest, model: str, **kw: Any) -> LLMResponse:
        self.calls.append((str(req.role), model))
        resp = await self.fake.complete(req, guard=kw.get("guard"))
        resp.model = model.rsplit("/", 1)[-1]
        resp.served_model = resp.model
        return resp


def cross_router(reviewer_model: str, ds: list[Message], zp: list[Message], qw: list[Message]) -> Any:
    from triwitness.llm.router import RoleRoute, Router

    routes = {
        "executor": RoleRoute(model="deepseek/deepseek-flash"),
        "planner": RoleRoute(model="deepseek/deepseek-flash"),
        "verifier": RoleRoute(model="qwen/qwen3.8-flash"),
        "reviewer": RoleRoute(model=reviewer_model, variant="cross"),
    }
    clients = {"deepseek": ScriptClient(ds), "zhipu": ScriptClient(zp), "qwen": ScriptClient(qw)}
    return Router(routes, clients, vendor_policy="cross_vendor"), clients  # type: ignore[arg-type]


VERDICT = say(call("submit_verdict", verdict="pass", criteria=[{"criterion": "AC1", "judgement": "met"}],
                   confidence=0.9, rationale="复现转绿，全量通过"))  # fmt: skip


async def test_cross_vendor_end_to_end(env: tuple) -> None:  # type: ignore[type-arg]
    """DoD：cross_vendor 只改配置即可启用——reviewer 走智谱、verifier 走千问，证据包标注不同厂商。"""
    backend, repo = env
    nit = {"severity": "nit", "file": "calc.py", "line": 2, "message": "可加注解"}
    router, clients = cross_router("zhipu/glm-5.3", ds=[plan(), say(WRITE_REPRO), say(RIGHT), finish()],
                                   zp=[review(nit)], qw=[VERDICT])  # fmt: skip
    opts = VerifyOptions(backend=EphemeralBackend(backend), spec=SandboxSpec(repo=repo), static_tools=("ruff",),
                         python=Path(sys.executable).as_posix(), mode="model", router=router,
                         model_policy="always")  # fmt: skip
    res, rec = await go(env, router, verify=opts)
    assert res.status == "done", res.outcome
    assert {r for r, _ in clients["deepseek"].calls} == {"planner", "executor"}
    assert clients["zhipu"].calls == [("reviewer", "zhipu/glm-5.3")]
    assert clients["qwen"].calls == [("verifier", "qwen/qwen3.8-flash")]
    ev = res.verification.evidence  # type: ignore[union-attr]
    assert ev.vendor_policy == "cross_vendor" and ev.review_model == "glm-5.3"
    assert ev.verifier_model == "qwen3.8-flash"
    (rv,) = kinds(rec, "review")
    assert rv["vendor_policy"] == "cross_vendor"
    assert "与执行者不同厂商" in res.verification.pr_body  # type: ignore[union-attr]


async def test_cross_vendor_same_vendor_reviewer_fails_before_any_call(env: tuple) -> None:  # type: ignore[type-arg]
    router, clients = cross_router("deepseek/deepseek-flash", ds=[plan()], zp=[], qw=[])
    res, rec = await go(env, router)
    assert res.status == "failed" and states(rec) == ["preparing", "failed"]
    (err,) = kinds(rec, "error")
    assert err["type"] == "ConstraintViolation" and "reviewer" in err["message"]
    assert all(not c.calls for c in clients.values())


def test_eval_agent_runs_without_permission_gate() -> None:
    """Eva 21:36：评测默认完全放开——tw eval 的工具集不挂权限闸门（不审批命令），
    只受模型白名单与非金钱安全上限约束。"""
    import inspect

    from triwitness.eval.agents import LLMAgent

    src = inspect.getsource(LLMAgent.solve)
    assert "registry=ToolRegistry(default_tools(names=harness.tools))," in src
    assert 'mode="eval"' in src


def test_with_review_floors_inconclusive_to_l2() -> None:
    """低风险（L0）证据包 + 评审无结论 → L2 + floor:reviewer_inconclusive。"""
    from triwitness.verify.pipeline import PipelineResult

    captured: dict[str, Any] = {}

    class _Ev:
        risk_level = "L0"
        risk_factors: ClassVar[list[Any]] = []

        def model_copy(self, update: dict[str, Any]) -> Any:
            captured.update(update)
            return self

    pr = PipelineResult.__new__(PipelineResult)
    pr.rebuild = lambda **kw: (_Ev(), None)  # type: ignore[assignment]
    import triwitness.verify.pipeline as pl

    orig = pl.render_pr
    pl.render_pr = lambda ev: ""  # type: ignore[assignment]
    try:
        for name in ("deterministic", "reasons", "static", "model"):
            setattr(pr, name, None)
        pr.with_review(findings=[], review_model="m", review_variant="checklist", reviewer_inconclusive=True)
    finally:
        pl.render_pr = orig
    assert captured["risk_level"] == "L2" and captured["review_status"] == "inconclusive"
    assert [f.code for f in captured["risk_factors"]] == ["floor:reviewer_inconclusive"]
