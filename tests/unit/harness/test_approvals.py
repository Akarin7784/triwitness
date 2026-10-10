"""W1-42 审批事件接线：spec 006 AC6（非交互 ask→deny + approval_resolved(by=policy)）及交互审批。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from triwitness.core.events import ApprovalRequestedPayload
from triwitness.core.models import Budget
from triwitness.harness.approvals import ApprovalBroker, ApprovalDecision, PermissionGate
from triwitness.harness.events import EventEmitter
from triwitness.harness.loop import AgentLoop
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.permissions.config import SessionOverrides, load_policy
from triwitness.permissions.engine import PermissionEngine
from triwitness.sandbox.base import ExecResult
from triwitness.tools import ToolContext, ToolRegistry, default_tools

ASK_CMD = "make build"
FIN = {"summary": "s", "changes": [], "tests_passed": False, "confidence": 0.5}


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("CI", raising=False)
    r = tmp_path / "repo"
    (r / ".git").mkdir(parents=True)
    return r


def engine(repo: Path, *, interactive: bool, eval_mode: bool = False) -> PermissionEngine:
    pol = load_policy(
        repo,
        backend="docker",
        interactive=interactive,
        eval_mode=eval_mode,
        session=SessionOverrides(),
        home=repo.parent / "home",
        managed_path=repo.parent / "m.yaml",
    )
    return PermissionEngine(pol, windows=False, workspace=str(repo), home="/home/eva")


def sandbox() -> FakeSandbox:
    return FakeSandbox(
        {"a.py": "x\n"},
        exec_handler=lambda c, s: ExecResult(exit_code=0, stdout="ok", stderr="", duration_ms=1, timed_out=False),
    )


async def run_loop(gate: PermissionGate, em: EventEmitter, script: list) -> tuple:  # type: ignore[type-arg]
    reg = ToolRegistry(default_tools(), gate=gate)
    loop = AgentLoop(FakeRouter(script), reg, system_prompt="s", budget=Budget(), emitter=em)
    sb = sandbox()
    out = await loop.run("x", ToolContext(sandbox=sb))
    return out, loop, sb


def test_precondition_ask_command(repo: Path) -> None:
    from triwitness.permissions.engine import Action

    assert engine(repo, interactive=True).check(Action("Bash", ASK_CMD, tool="bash")).decision == "ask"
    assert engine(repo, interactive=True).check(Action("Bash", "ls", tool="bash")).decision == "allow"


@pytest.mark.parametrize("eval_mode", [False, True])
async def test_ac6_noninteractive_ask_becomes_deny(repo: Path, eval_mode: bool) -> None:
    em = EventEmitter("t", "r")
    gate = PermissionGate(engine(repo, interactive=False, eval_mode=eval_mode), em)
    out, loop, sb = await run_loop(gate, em, [say(call("bash", command=ASK_CMD)), say(call("finish", **FIN))])
    assert out.status == "finished"
    assert sb.commands == []  # 没有执行
    assert em.kinds() == ["model_call", "approval_resolved", "tool_call", "model_call", "tool_call"]
    resolved = next(e for e in em.events if e.kind == "approval_resolved")
    assert resolved.payload["by"] == "policy" and resolved.payload["decision"] == "deny"
    tc = next(e for e in em.events if e.kind == "tool_call")
    assert tc.payload["permission"] == "deny" and tc.payload["ok"] is False
    tool_msg = next(m for m in loop.messages if m.role == "tool")
    assert "权限拒绝" in (tool_msg.content or "")


async def test_allow_runs_and_records_permission(repo: Path) -> None:
    em = EventEmitter("t", "r")
    gate = PermissionGate(engine(repo, interactive=False), em)
    _, _, sb = await run_loop(gate, em, [say(call("bash", command="ls")), say(call("finish", **FIN))])
    assert sb.commands == ["ls"] and "approval_resolved" not in em.kinds()
    assert next(e for e in em.events if e.kind == "tool_call").payload["permission"] == "allow"


async def test_interactive_approve_once(repo: Path) -> None:
    em = EventEmitter("t", "r")
    seen: list[ApprovalRequestedPayload] = []

    async def approver(req: ApprovalRequestedPayload) -> ApprovalDecision:
        seen.append(req)
        return ApprovalDecision("allow")

    gate = PermissionGate(engine(repo, interactive=True), em, approver=approver)
    script = [say(call("bash", command=ASK_CMD)), say(call("bash", command=ASK_CMD + " ")), say(call("finish", **FIN))]
    _, _, sb = await run_loop(gate, em, script)
    assert len(seen) == 2 and seen[0].tool == "Bash" and seen[0].action == ASK_CMD and seen[0].risk == "L2"
    assert seen[0].suggested_rule
    assert len(sb.commands) == 2
    kinds = em.kinds()
    assert kinds[:4] == ["model_call", "approval_requested", "approval_resolved", "tool_call"]
    res = next(e for e in em.events if e.kind == "approval_resolved")
    assert res.payload["by"] == "user" and res.payload["request_id"] == seen[0].request_id


async def test_interactive_deny_comment_reaches_model(repo: Path) -> None:
    em = EventEmitter("t", "r")

    async def approver(req: ApprovalRequestedPayload) -> ApprovalDecision:
        return ApprovalDecision("deny", comment="别装依赖，用标准库")

    gate = PermissionGate(engine(repo, interactive=True), em, approver=approver)
    _, loop, sb = await run_loop(gate, em, [say(call("bash", command=ASK_CMD)), say(call("finish", **FIN))])
    assert sb.commands == []
    msg = next(m for m in loop.messages if m.role == "tool").content or ""
    assert "用户拒绝" in msg and "别装依赖，用标准库" in msg


async def test_session_scope_remembered(repo: Path) -> None:
    em = EventEmitter("t", "r")
    calls = 0

    async def approver(req: ApprovalRequestedPayload) -> ApprovalDecision:
        nonlocal calls
        calls += 1
        return ApprovalDecision("allow", scope="session")

    gate = PermissionGate(engine(repo, interactive=True), em, approver=approver)
    script = [say(call("bash", command=ASK_CMD)), say(call("bash", command=ASK_CMD)), say(call("finish", **FIN))]
    _, _, sb = await run_loop(gate, em, script)
    assert calls == 1 and len(sb.commands) == 2
    assert not (repo / ".triwitness" / "permissions.local.yaml").exists()


async def test_always_scope_saved_to_local_yaml(repo: Path) -> None:
    em = EventEmitter("t", "r")

    async def approver(req: ApprovalRequestedPayload) -> ApprovalDecision:
        return ApprovalDecision("allow", scope="always")

    gate = PermissionGate(engine(repo, interactive=True), em, approver=approver, repo_for_always=repo)
    await run_loop(gate, em, [say(call("bash", command=ASK_CMD)), say(call("finish", **FIN))])
    local = repo / ".triwitness" / "permissions.local.yaml"
    assert local.exists() and "Bash(make build)" in local.read_text(encoding="utf-8")
    res = next(e for e in em.events if e.kind == "approval_resolved")
    assert res.payload["saved_rule"] and res.payload["scope"] == "always"
    # 新引擎读取到保存的规则后不再询问
    from triwitness.permissions.engine import Action

    assert engine(repo, interactive=True).check(Action("Bash", ASK_CMD, tool="bash")).decision == "allow"


async def test_no_approver_needs_human(repo: Path) -> None:
    em = EventEmitter("t", "r")
    gate = PermissionGate(engine(repo, interactive=True), em)
    out, _, sb = await run_loop(gate, em, [say(call("bash", command=ASK_CMD))])
    assert out.status == "needs_human" and sb.commands == []
    assert em.kinds()[-1] == "approval_requested"


async def test_broker_resolve() -> None:
    broker = ApprovalBroker()
    req = ApprovalRequestedPayload(
        request_id="hitl_1", tool="Bash", action="x", reason="r", risk="L2", backend="docker"
    )
    task = asyncio.create_task(broker.wait(req))
    await asyncio.sleep(0)
    assert broker.resolve_approval("nope", "allow") is False
    assert broker.resolve_approval("hitl_1", "deny", comment="c") is True
    d = await task
    assert d is not None and d.decision == "deny" and d.comment == "c"
    assert broker.pending == {} and broker.resolve_approval("hitl_1", "allow") is False
