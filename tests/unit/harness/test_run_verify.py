"""W3-12 后续：run_task 主流程接入 VERIFYING（真实 none 后端 + 真 pytest，FakeRouter 驱动，不调用模型）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from triwitness.core.models import Budget
from triwitness.harness.run import TaskResult, run_task
from triwitness.harness.testing import FakeRouter, call, say
from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools
from triwitness.verify.pipeline import EphemeralBackend, VerifyOptions
from triwitness.verify.testing import git, make_repo

PY = f'"{Path(sys.executable).as_posix()}" -m pytest -q -p no:cacheprovider'
REPRO = "tests/tw_repro/test_issue_1.py"
BUGGY = "def add(a, b):\n    return a - b\n"
ISSUE = "`add(1, 2) == 3` 应该成立，现在 add(1, 2) 返回 -1。"
WRITE_REPRO = call("write_file", path=REPRO, content="from calc import add\n\n\ndef test_issue():\n"
                   "    assert add(1, 2) == 3\n")  # fmt: skip
WRONG = call("edit_file", path="calc.py", old_str="a - b", new_str="a * b + 1")  # add(1,2)=3 但 add(2,0)=1
RIGHT_AFTER_WRONG = call("edit_file", path="calc.py", old_str="a * b + 1", new_str="a + b")
RIGHT = call("edit_file", path="calc.py", old_str="a - b", new_str="a + b")


def finish() -> Any:
    return say(call("finish", summary="add 改成加法", changes=[{"path": "calc.py", "kind": "modified"}],
                    tests_run=[f"pytest {REPRO}"], tests_passed=True, confidence=0.9,
                    repro={"path": REPRO, "cmd": f"{PY} {REPRO}"}))  # fmt: skip


@pytest.fixture
def env(tmp_path: Path) -> tuple[LocalSandboxBackend, Path]:
    repo = make_repo(tmp_path, {"calc.py": BUGGY, "tests/__init__.py": "", "tests/tw_repro/__init__.py": "",
                                "tests/test_calc.py": "from calc import add\n\n\ndef test_zero():\n"
                                                      "    assert add(2, 0) == 2\n"})  # fmt: skip
    return LocalSandboxBackend(home=tmp_path / "home"), repo


async def go(
    env: tuple, script: list, verifier: list | None = None, **kw: Any
) -> tuple[TaskResult, TrajectoryRecorder]:  # type: ignore[type-arg]
    backend, repo = env
    sb = await backend.create(SandboxSpec(repo=repo, run_id="exec1"))
    rec = TrajectoryRecorder("t_v", "r_v", run_dir=repo.parent / "run")
    opts = VerifyOptions(backend=EphemeralBackend(backend), spec=SandboxSpec(repo=repo), static_tools=("ruff",),
                         python=Path(sys.executable).as_posix(), mode="model" if verifier else "deterministic",
                         router=FakeRouter(verifier) if verifier else None, **kw)  # fmt: skip
    try:
        res = await run_task(recorder=rec, router=FakeRouter(script), registry=ToolRegistry(default_tools()),
                             sandbox=sb, issue_title="add 是减法", task_prompt=ISSUE, repo="o/r", budget=Budget(),
                             config_hash="c", test_command=PY, verify=opts, tw_dir=str(sb.tw_dir))  # type: ignore[attr-defined]  # fmt: skip
    finally:
        await sb.finish("discard")  # type: ignore[attr-defined]
    return res, rec


def states(rec: TrajectoryRecorder) -> list[str]:
    return [str(e.payload["to"]) for e in rec.events if e.kind == "state_change"]


def verifications(rec: TrajectoryRecorder) -> list[dict[str, Any]]:
    return [e.payload for e in rec.events if e.kind == "verification"]


async def test_verifying_produces_evidence_and_pr(env: tuple) -> None:  # type: ignore[type-arg]
    res, rec = await go(env, [say(WRITE_REPRO), say(RIGHT), finish()])
    assert res.status == "done", res.outcome
    assert states(rec) == ["preparing", "executing", "verifying", "packaging", "done"]
    v = res.verification
    assert v is not None
    assert v.evidence.repro_status == "reproduced", v.reasons
    assert v.evidence.verdict == "pass" and v.tests_passed
    reg = [r for r in v.evidence.test_runs if r.scope == "full"]
    assert reg and reg[0].new_failures == []
    assert v.evidence.static_checks["ruff"] in ("pass", "skipped") and v.evidence.static_checks["secrets"] == "pass"
    # none 后端：干净环境未验证 → 风险至少 L2，PR 正文有横幅
    assert (v.evidence.clean_env, v.unverified_reason, v.evidence.risk_level) == ("unverified", "no_sandbox", "L2")
    assert "TriWitness 证据包" in v.pr_body
    (ev,) = verifications(rec)
    assert ev["verdict"] == "pass" and ev["risk_level"] == "L2" and ev["clean_env"] == "unverified"
    run_dir = env[1].parent / "run"
    saved = json.loads((run_dir / ev["evidence_ref"]).read_text(encoding="utf-8"))
    assert saved["repro_status"] == "reproduced"
    # 复跑用的 worktree / 分支都已丢弃
    assert "verify-" not in git(env[1], "branch", "--list")


async def test_regression_fails_then_rework(env: tuple) -> None:  # type: ignore[type-arg]
    script = [say(WRITE_REPRO), say(WRONG), finish(), say(RIGHT_AFTER_WRONG), finish()]
    res, rec = await go(env, script, max_retries=1)
    assert res.status == "done" and res.verify_rounds == 2
    assert states(rec) == ["preparing", "executing", "verifying", "executing", "verifying", "packaging", "done"]
    first, second = verifications(rec)
    assert first["verdict"] == "fail" and second["verdict"] == "pass"
    assert res.verification is not None and res.verification.evidence.verdict == "pass"


async def test_regression_fail_without_retries_marks_failed(env: tuple) -> None:  # type: ignore[type-arg]
    res, rec = await go(env, [say(WRITE_REPRO), say(WRONG), finish()])
    assert res.status == "failed" and states(rec)[-1] == "failed"
    v = res.verification
    assert v is not None and v.evidence.verdict == "fail"
    assert any("test_zero" in f for r in v.evidence.test_runs for f in r.new_failures), v.evidence.test_runs
    assert "test_zero" in v.feedback()


async def test_model_verifier_conservative_and_costed(env: tuple) -> None:  # type: ignore[type-arg]
    verdict = say(call("submit_verdict", verdict="inconclusive", confidence=0.4, rationale="没覆盖负数",
                       criteria=[{"criterion": "add 返回和", "judgement": "unknown", "evidence": []}],
                       evidence_gaps=["负数"]))  # fmt: skip
    res, rec = await go(env, [say(WRITE_REPRO), say(RIGHT), finish()], verifier=[verdict])
    v = res.verification
    assert v is not None and v.deterministic == "pass" and v.evidence.verdict == "inconclusive"
    assert res.status == "done"  # inconclusive 不算失败，但风险更高、交给人看
    calls = [e for e in rec.events if e.kind == "model_call" and e.role == "verifier"]
    assert len(calls) == 1
    assert res.cost.total_cny == pytest.approx(0.004)  # 3 次 executor + 1 次 verifier
    assert v.evidence.criteria_results == {"add 返回和": "unknown"}


async def test_no_verify_keeps_w2_behaviour(env: tuple) -> None:  # type: ignore[type-arg]
    backend, repo = env
    sb = await backend.create(SandboxSpec(repo=repo, run_id="exec2"))
    rec = TrajectoryRecorder("t_n", "r_n")
    try:
        res = await run_task(recorder=rec, router=FakeRouter([say(RIGHT), finish()]),
                             registry=ToolRegistry(default_tools()), sandbox=sb, issue_title="x", task_prompt=ISSUE,
                             repo="o/r", budget=Budget(), config_hash="c")  # fmt: skip
    finally:
        await sb.finish("discard")  # type: ignore[attr-defined]
    assert res.verification is None and "verifying" not in states(rec)
