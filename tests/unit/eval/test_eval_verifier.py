"""W3-13：评测接入验证器（none / deterministic / model）+ 新指标。假 Agent / FakeRouter，离线。"""

from __future__ import annotations

from pathlib import Path

import pytest

from triwitness.eval.agents import LLMAgent
from triwitness.eval.report import build_report, render_markdown
from triwitness.eval.runner import EvalRunner, RunConfig
from triwitness.eval.task import EvalTask, discover, load_task
from triwitness.eval.verification import verifier_metrics
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.sandbox.base import ExecResult

from .test_runner import OFF_PEAK, FakeGrader

DEV = Path(__file__).resolve().parents[3] / "evals" / "tasks" / "dev"
REPRO = "tests/tw_repro/test_issue.py"


@pytest.fixture(scope="module")
def tasks() -> list[EvalTask]:
    return [load_task(d) for d in discover(DEV)][:3]


class PatchingSandbox(FakeSandbox):
    """apply_patch 只模拟两件事：FIX.py（修复）与复现测试文件；任何测试命令在 FIX.py 存在时通过。"""

    async def apply_patch(self, patch: str) -> None:
        if "FIX.py" in patch:
            self.files["FIX.py"] = b"FIXED = True\n"
        if REPRO in patch:
            self.files[REPRO] = b"from FIX import FIXED\n"
        if "conftest.py" in patch:
            self.files["conftest.py"] = b"# tamper\n"


class VerifyingGrader(FakeGrader):
    async def new_sandbox(self, task: EvalTask) -> FakeSandbox:  # type: ignore[override]
        base = await super().new_sandbox(task)

        def handler(cmd: str, sb: FakeSandbox) -> ExecResult:
            if "solve.sh" in cmd:
                sb.files["FIX.py"] = b"FIXED = True\n"
                return ExecResult(exit_code=0, stdout="", stderr="", duration_ms=1, timed_out=False)
            ok = "FIX.py" in sb.files
            return ExecResult(exit_code=0 if ok else 1, stdout="", stderr="", duration_ms=1, timed_out=False)

        return PatchingSandbox({k: v for k, v in base.files.items()}, exec_handler=handler)


FINISH = {"summary": "修好", "changes": [{"path": "FIX.py", "kind": "added"}], "tests_run": ["pytest"],
          "tests_passed": True, "confidence": 0.8, "repro": {"path": REPRO, "cmd": f"python {REPRO}"}}  # fmt: skip


def scripted(cfg: RunConfig) -> LLMAgent:
    def router() -> FakeRouter:
        return FakeRouter([say(call("write_file", path=REPRO, content="from FIX import FIXED\n"),
                               call("write_file", path="FIX.py", content="FIXED = True\n")),
                           say(call("finish", **FINISH))])  # fmt: skip

    return LLMAgent(router, category=cfg.category, config_hash=cfg.name)


def verdict_router() -> FakeRouter:
    return FakeRouter([say(call("submit_verdict", verdict="pass", confidence=0.9, rationale="ok"))] * 1)


async def test_eval_with_verifier_modes(tmp_path: Path, tasks: list[EvalTask]) -> None:
    g = VerifyingGrader()
    r = EvalRunner(grader=g, llm_agent_factory=scripted, results_root=tmp_path, now=lambda: OFF_PEAK,  # type: ignore[arg-type]
                   verifier_router_factory=verdict_router)  # fmt: skip
    cfgs = [
        RunConfig(name="null-det", agent="null", verifier="deterministic"),
        RunConfig(name="tamper-det", agent="tamper", verifier="deterministic"),
        RunConfig(name="llm-none", agent="llm"),
        RunConfig(name="llm-det", agent="llm", verifier="deterministic"),
        RunConfig(name="llm-model", agent="llm", verifier="model"),
    ]
    s = await r.run(tasks, cfgs, out_dir=tmp_path / "run")
    assert not s.infra_errors
    by = {(x.config, x.task_id): x for x in s.done}
    t = tasks[0].id
    assert by[("null-det", t)].verifier_verdict == "fail"
    tamper = by[("tamper-det", t)]
    assert tamper.verifier_verdict != "pass" and tamper.false_success  # 自称修好，验证器不放行
    assert by[("llm-none", t)].verifier_verdict is None and by[("llm-none", t)].verifier_mode is None
    det = by[("llm-det", t)]
    assert det.verify_repro_status == "reproduced" and det.verifier_deterministic in ("pass", "inconclusive")
    assert det.verifier_error is None and det.risk_level is not None
    mod = by[("llm-model", t)]
    assert mod.verifier_model_verdict == "pass" and mod.verifier_verdict == det.verifier_verdict  # 取更保守者
    assert (tmp_path / "run" / "llm-det" / t / "1" / "verification.json").exists()

    rep = build_report(tmp_path / "run")
    rows = {x.config: x for x in rep.rows}
    assert rows["llm-none"].verifier is None
    v = rows["tamper-det"].verifier
    assert v is not None and v.false_success_claimed == len(tasks) and v.false_success_verified == 0
    md = render_markdown(rep)
    assert "## 验证器（以隐藏测试为真值）" in md and "精确率" in md and "tamper-det" in md


def test_verifier_metrics() -> None:
    rows = [(True, True, "pass", "L0"), (False, True, "pass", "L1"), (True, True, "inconclusive", "L2"),
            (False, False, "fail", "L2"), (True, True, None, None)]  # fmt: skip
    m = verifier_metrics(rows)
    assert m is not None and m.n == 4 and m.verified_pass == 2 and m.true_pass == 1
    assert (m.precision, m.recall) == (0.5, 0.5)
    assert m.false_success_claimed == 1 and m.false_success_verified == 1
    assert m.by_risk == {"L0": (1, 1.0), "L1": (1, 0.0), "L2": (2, 0.5)}
    assert verifier_metrics([(True, True, None, None)]) is None
