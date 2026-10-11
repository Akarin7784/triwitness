"""spec 010 §11 Q5（Eva 21:35）：终端 tw run 在 TTY 里 y/N 审批；非 TTY 沿用一律拒绝。"""

from __future__ import annotations

from typing import Any

import pytest

from triwitness.cli.tty import make_tty_approver
from triwitness.core.events import ApprovalRequestedPayload


def req(tool: str = "Bash", **kw: Any) -> ApprovalRequestedPayload:
    return ApprovalRequestedPayload(request_id="h1", tool=tool, action=kw.pop("action", "pytest -q"),
                                    reason="运行命令", display=f"待批 · {tool}", **kw)  # fmt: skip


def approver(*answers: str | BaseException) -> tuple[Any, list[str], list[str]]:
    shown: list[str] = []
    prompts: list[str] = []
    it = iter(answers)

    def read(prompt: str) -> str:
        prompts.append(prompt)
        a = next(it)
        if isinstance(a, BaseException):
            raise a
        return a

    return make_tty_approver(read=read, write=shown.append), shown, prompts


@pytest.mark.parametrize(
    ("answer", "decision", "scope"),
    [("y", "allow", "once"), ("YES", "allow", "once"), ("s", "allow", "session"), ("", "deny", "once"),
     ("n", "deny", "once"), ("whatever", "deny", "once")],
)  # fmt: skip
async def test_permission_prompt(answer: str, decision: str, scope: str) -> None:
    a, shown, prompts = approver(answer)
    d = await a(req())
    assert d is not None and (d.decision, d.scope) == (decision, scope)
    assert "需要你确认" in shown[0] and "pytest -q" in shown[0] and "[s] 本次任务" in prompts[0]


async def test_plan_prompt_has_no_session_option() -> None:
    a, _, prompts = approver("s")
    d = await a(req("Plan", action="根因假设：…", options=["allow_once", "deny"]))
    assert d is not None and d.decision == "deny" and "批准这个计划" in prompts[0]


async def test_ask_human_free_text() -> None:
    a, _, prompts = approver("只要数字", "", "n")
    d1 = await a(req("AskHuman", action="add 要支持字符串吗？", options=["allow_once", "deny"]))
    d2 = await a(req("AskHuman", options=["allow_once", "deny"]))
    d3 = await a(req("AskHuman", options=["allow_once", "deny"]))
    assert d1 is not None and (d1.decision, d1.comment) == ("allow", "只要数字")
    assert d2 is not None and d2.decision == "deny" and d2.comment is None
    assert d3 is not None and (d3.decision, d3.comment) == ("deny", "否")
    assert "回答" in prompts[0]


async def test_eof_means_nobody_there() -> None:
    a, _, _ = approver(EOFError())
    assert await a(req()) is None


def test_non_tty_keeps_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    """CliRunner 的 stdin 不是 TTY：不构造终端审批（run_local 收到 approver=None → 非交互拒绝）。"""
    import triwitness.cli.main as m

    seen: dict[str, Any] = {}

    from typer.testing import CliRunner

    from triwitness.core.errors import TriWitnessError

    async def fake(*a: Any, **kw: Any) -> Any:
        seen.update(kw)
        raise TriWitnessError("stop")

    monkeypatch.setattr("triwitness.harness.local_run.run_local", fake)
    monkeypatch.setenv("TW_LLM_MODE", "replay")
    r = CliRunner().invoke(m.app, ["run", "--repo", ".", "--issue", "x"])
    assert r.exit_code == 2 and seen.get("approver") is None
