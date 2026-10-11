"""spec 010 §5 / AC3（W4-04）：submit_plan / submit_review 契约与结构化输出降级助手。"""

from __future__ import annotations

import json
from typing import Any

from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.llm.types import Message
from triwitness.roles.contracts import (
    PlanSubmission,
    Review,
    check_review,
    parse_model,
    structured_call,
    submit_plan_tool,
    submit_review_tool,
    submit_tool_schema,
)
from triwitness.tools import ToolRegistry
from triwitness.tools.base import ToolContext

PLAN: dict[str, Any] = {
    "root_cause_hypothesis": "calc.add 用了减法",
    "affected_files": ["calc.py"],
    "repro_strategy": "test",
    "acceptance_criteria": [{"id": "AC1", "description": "add(1, 2) == 3", "check": "test",
                             "detail": "tests/tw_repro/test_issue_1.py"}],
    "steps": [{"id": "S1", "goal": "改成加法", "files": ["calc.py"]}],
    "estimated_risk": "L1",
}  # fmt: skip


async def test_submit_plan_valid_and_invalid() -> None:
    reg = ToolRegistry([submit_plan_tool()])  # type: ignore[list-item]
    ctx = ToolContext(sandbox=FakeSandbox())
    ok, _ = await reg.dispatch(call("submit_plan", **PLAN), ctx)
    assert ok.ok and ok.data == {"submission": PlanSubmission.model_validate(PLAN).model_dump(mode="json")}
    bad = {**PLAN, "acceptance_criteria": [], "estimated_risk": "L9"}
    res, _ = await reg.dispatch(call("submit_plan", **bad), ctx)
    assert not res.ok and res.error_code == "bad_args"
    assert "acceptance_criteria" in res.content and "estimated_risk" in res.content
    plan = PlanSubmission.model_validate(PLAN).to_plan(task_id="t_1", model="deepseek-flash")
    assert plan.task_id == "t_1" and plan.acceptance_criteria[0].check == "test"


async def test_submit_review_consistency_check() -> None:
    reg = ToolRegistry([submit_review_tool()])  # type: ignore[list-item]
    ctx = ToolContext(sandbox=FakeSandbox())
    blocker = {"severity": "blocker", "file": "calc.py", "line": 2, "message": "不是加法"}
    res, _ = await reg.dispatch(call("submit_review", verdict="approve", findings=[blocker]), ctx)
    assert not res.ok and "request_changes" in res.content
    res, _ = await reg.dispatch(call("submit_review", verdict="request_changes", findings=[]), ctx)
    assert not res.ok and "blocker / major" in res.content
    res, _ = await reg.dispatch(call("submit_review", verdict="request_changes", findings=[blocker]), ctx)
    assert res.ok
    r = Review.model_validate(res.data["submission"])  # type: ignore[index]
    assert r.blocking and r.blockers[0].to_finding().status == "open"


def _validate(raw: Any) -> tuple[Review | None, str]:
    return parse_model(Review, raw, check_review)


async def test_structured_call_repair_then_content_json() -> None:
    tool = submit_tool_schema("submit_review", "提交", Review)
    msgs = [Message(role="system", content="s"), Message(role="user", content="u")]
    bad = say(call("submit_review", verdict="approve", findings=[{"severity": "blocker", "message": "x"}]))
    good = say(call("submit_review", verdict="approve", findings=[]))
    router = FakeRouter([bad, good])
    res = await structured_call(router, role="reviewer", messages=msgs, tool=tool, validate=_validate)
    assert res.path == "repair" and res.attempts == 2 and res.value is not None
    # 修复请求里带着校验错误
    assert "request_changes" in (router.requests[1].messages[-1].content or "")
    # 没调工具 → 从 content 抽 JSON
    text = "结论如下：\n```json\n" + json.dumps({"verdict": "approve", "findings": []}) + "\n```"
    res2 = await structured_call(FakeRouter([say(text=text)]), role="reviewer", messages=msgs, tool=tool,
                                 validate=_validate)  # fmt: skip
    assert res2.path == "content_json" and res2.value is not None


async def test_structured_call_gives_up() -> None:
    tool = submit_tool_schema("submit_review", "提交", Review)
    msgs = [Message(role="system", content="s"), Message(role="user", content="u")]
    res = await structured_call(FakeRouter([say(text="不知道")] * 3), role="reviewer", messages=msgs, tool=tool,
                                validate=_validate)  # fmt: skip
    assert res.value is None and res.path == "failed" and res.attempts == 3 and "没有调用" in res.last_error
