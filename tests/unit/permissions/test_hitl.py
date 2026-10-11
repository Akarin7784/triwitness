"""W4-10 / 04 §3.7：改依赖声明、改 CI / 构建配置是人工确认点——不交给审核模型，非交互拒绝，评测 / full_access 不经过。"""

from __future__ import annotations

from pathlib import Path

import pytest

from triwitness.core.events import ApprovalRequestedPayload
from triwitness.core.models import Budget
from triwitness.harness.approvals import ApprovalDecision, PermissionGate
from triwitness.harness.config import HitlConfig
from triwitness.harness.events import EventEmitter
from triwitness.harness.loop import AgentLoop
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.permissions.config import SessionOverrides, load_policy
from triwitness.permissions.engine import PermissionEngine
from triwitness.permissions.hitl import classify_command, classify_edit, hitl_point
from triwitness.permissions.reviewer import ReviewDecision
from triwitness.sandbox.base import ExecResult
from triwitness.tools import ToolContext, ToolRegistry, default_tools

FIN = {"summary": "s", "changes": [], "tests_passed": False, "confidence": 0.5}


@pytest.mark.parametrize(
    ("path", "want"),
    [
        ("pyproject.toml", "dependency"),
        ("requirements-dev.txt", "dependency"),
        ("apps/web/package.json", "dependency"),
        ("/workspace/repo/uv.lock", "dependency"),
        ("go.mod", "dependency"),
        (".github/workflows/ci.yml", "ci_config"),
        ("/workspace/repo/.github/workflows/release.yml", "ci_config"),
        ("Makefile", "ci_config"),
        ("docker/app.Dockerfile", "ci_config"),
        (".pre-commit-config.yaml", "ci_config"),
        ("src/calc.py", None),
        ("docs/Makefile.md", None),
        ("tests/test_setup.py", None),
    ],
)
def test_classify_edit(path: str, want: str | None) -> None:
    assert classify_edit(path) == want


@pytest.mark.parametrize(
    ("cmd", "want"),
    [
        ("uv add httpx", "dependency"),
        ("cd web && npm install lodash", "dependency"),
        ("npm i -D vitest", "dependency"),
        ("poetry update", "dependency"),
        ("go get example.com/x@v2", "dependency"),
        ("cargo add serde", "dependency"),
        ("npm install", None),  # 只按 lock 安装，不改声明
        ("npm ci", None),
        ("pip install -r requirements.txt", None),
        ("pytest -q", None),
        ("make build", None),
    ],
)
def test_classify_command(cmd: str, want: str | None) -> None:
    assert classify_command(cmd) == want


def test_hitl_point_switches() -> None:
    assert hitl_point("Edit", "pyproject.toml", dependency=False) is None
    assert hitl_point("Edit", "Makefile", ci=False) is None
    p = hitl_point("Bash", "uv add x")
    assert p is not None and p.label == "修改依赖声明"
    assert hitl_point("Read", "pyproject.toml") is None


# ---------------------------------------------------------------- PermissionGate


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("CI", raising=False)
    r = tmp_path / "repo"
    (r / ".git").mkdir(parents=True)
    return r


def engine(repo: Path, *, mode: str = "auto_review", interactive: bool = True, eval_mode: bool = False,
           ) -> PermissionEngine:  # fmt: skip
    pol = load_policy(repo, backend="docker", interactive=interactive, eval_mode=eval_mode,
                      session=SessionOverrides(mode=mode),  # type: ignore[arg-type]
                      home=repo.parent / "home", managed_path=repo.parent / "m.yaml")  # fmt: skip
    return PermissionEngine(pol, windows=False, workspace=str(repo), home="/home/eva")


class _AllowAll:
    """审核模型：什么都批准——确认点不能交给它。"""

    def __init__(self) -> None:
        self.calls = 0

    async def review(self, req: ApprovalRequestedPayload) -> ReviewDecision:
        self.calls += 1
        return ReviewDecision("allow", "看起来没问题", cost_cny=0.0001, model="deepseek-flash")


EDIT_PYPROJECT = call("edit_file", path="pyproject.toml", old_str="x = 1", new_str="x = 2")
EDIT_CI = call("write_file", path=".github/workflows/ci.yml", content="on: push\n")


async def _run(gate: PermissionGate, em: EventEmitter, *calls: object) -> FakeSandbox:
    sb = FakeSandbox({"pyproject.toml": "x = 1\n", "a.py": "y\n"},
                     exec_handler=lambda c, s: ExecResult(exit_code=0, stdout="ok", stderr="", duration_ms=1,
                                                          timed_out=False))  # fmt: skip
    reg = ToolRegistry(default_tools(), gate=gate)
    script = [say(c) for c in calls] + [say(call("finish", **FIN))]  # type: ignore[arg-type]
    loop = AgentLoop(FakeRouter(script), reg, system_prompt="s", budget=Budget(), emitter=em)
    await loop.run("x", ToolContext(sandbox=sb))
    return sb


def payloads(em: EventEmitter, kind: str) -> list[dict]:  # type: ignore[type-arg]
    return [e.payload for e in em.events if e.kind == kind]


async def test_dependency_edit_goes_to_human_not_reviewer_model(repo: Path) -> None:
    em = EventEmitter("t", "r")
    asked: list[ApprovalRequestedPayload] = []

    async def approver(r: ApprovalRequestedPayload) -> ApprovalDecision:
        asked.append(r)
        return ApprovalDecision("allow")

    rv = _AllowAll()
    sb = await _run(PermissionGate(engine(repo), em, approver=approver, reviewer=rv), em, EDIT_PYPROJECT)
    assert rv.calls == 0 and len(asked) == 1
    assert asked[0].rule == "hitl:dependency" and "修改依赖声明" in asked[0].reason and asked[0].risk == "L2"
    assert "allow_always" not in asked[0].options  # 确认点不写进规则文件
    assert sb.files["pyproject.toml"] == b"x = 2\n"
    (res,) = payloads(em, "approval_resolved")
    assert res["by"] == "user" and res["decision"] == "allow"


async def test_human_deny_blocks_edit(repo: Path) -> None:
    em = EventEmitter("t", "r")

    async def approver(r: ApprovalRequestedPayload) -> ApprovalDecision:
        return ApprovalDecision("deny", comment="不要动依赖")

    sb = await _run(PermissionGate(engine(repo), em, approver=approver), em, EDIT_PYPROJECT)
    assert sb.files["pyproject.toml"] == b"x = 1\n"
    (tc,) = [p for p in payloads(em, "tool_call") if p["tool"] == "edit_file"]
    assert tc["ok"] is False and tc["permission"] == "deny"


async def test_session_allow_covers_rest_of_task(repo: Path) -> None:
    em = EventEmitter("t", "r")
    asked: list[str] = []

    async def approver(r: ApprovalRequestedPayload) -> ApprovalDecision:
        asked.append(r.rule or "")
        return ApprovalDecision("allow", "session")

    second = call("edit_file", path="pyproject.toml", old_str="x = 2", new_str="x = 3")
    sb = await _run(PermissionGate(engine(repo), em, approver=approver), em, EDIT_PYPROJECT, second, EDIT_CI)
    assert asked == ["hitl:dependency", "hitl:ci_config"]  # 依赖只问一次；CI 是另一个确认点
    assert sb.files["pyproject.toml"] == b"x = 3\n"


async def test_non_interactive_denies_with_reason(repo: Path) -> None:
    em = EventEmitter("t", "r")
    sb = await _run(PermissionGate(engine(repo, interactive=False), em), em, EDIT_CI, call("bash", command="uv add x"))
    assert ".github/workflows/ci.yml" not in sb.files and sb.commands == []
    res = payloads(em, "approval_resolved")
    assert [r["by"] for r in res] == ["policy", "policy"] and all(r["decision"] == "deny" for r in res)
    assert "approval_requested" not in em.kinds()


async def test_eval_and_full_access_bypass(repo: Path) -> None:
    em = EventEmitter("t", "r")
    sb = await _run(PermissionGate(engine(repo, interactive=False, eval_mode=True), em), em, EDIT_PYPROJECT)
    assert sb.files["pyproject.toml"] == b"x = 2\n" and "approval_resolved" not in em.kinds()


async def test_config_can_turn_points_off(repo: Path) -> None:
    em = EventEmitter("t", "r")
    gate = PermissionGate(engine(repo, interactive=False), em, hitl=HitlConfig(dependency_changes=False))
    sb = await _run(gate, em, EDIT_PYPROJECT)
    assert sb.files["pyproject.toml"] == b"x = 2\n"
