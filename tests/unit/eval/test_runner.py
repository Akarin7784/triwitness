"""EvalRunner / 报告 v0 的离线单测（FakeGrader + FakeSandbox + FakeRouter，不需要 Docker、不调模型）。

覆盖 spec 004 AC4（断点续跑）、AC5（报告与 result.json 一致）、AC7（预估超限不开始），以及高峰闸门 / 预算预检
/ 跨入高峰暂停派发 / 非 replay 模式必须显式 --live。
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from triwitness.core.errors import BudgetExceeded, ConfigError, PeakHourBlocked
from triwitness.core.models import Usage
from triwitness.cost.ledger import GlobalLedger
from triwitness.eval.agents import LLMAgent, NullAgent, OracleAgent, TamperAgent
from triwitness.eval.grade import GradeResult, filter_patch
from triwitness.eval.report import build_report, render_markdown, write_report
from triwitness.eval.runner import EstimateTooHigh, EvalRunner, RunConfig, historical_avg_cost
from triwitness.eval.task import EvalTask, discover, load_task
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.sandbox.base import ExecResult
from triwitness.telemetry.trajectory import Trajectory, TrajectoryRecorder

DEV = Path(__file__).resolve().parents[3] / "evals" / "tasks" / "dev"
OFF_PEAK = datetime(2026, 10, 10, 13, 0, tzinfo=UTC)  # 周六 21:00 北京时间
PEAK = datetime(2026, 10, 12, 2, 0, tzinfo=UTC)  # 周一 10:00 北京时间


@pytest.fixture(scope="module")
def tasks() -> list[EvalTask]:
    return [load_task(d) for d in discover(DEV)]


class FakeGrader:
    """沙箱 = 任务仓库文件的内存副本；判分 = 过滤后的 diff 里出现 FIXED。"""

    def __init__(self) -> None:
        self.sandboxes = 0
        self.graded: list[str] = []
        self.fail_on: str | None = None

    async def new_sandbox(self, task: EvalTask) -> FakeSandbox:
        self.sandboxes += 1
        if task.id == self.fail_on:
            raise RuntimeError("docker 挂了")
        repo = task.environment_dir / "repo"
        files = {p.relative_to(repo).as_posix(): p.read_bytes() for p in repo.rglob("*") if p.is_file()}

        def handler(cmd: str, sb: FakeSandbox) -> ExecResult:
            if "solve.sh" in cmd:  # oracle：参考解的效果
                sb.files["FIX.py"] = b"FIXED = True\n"
            return ExecResult(exit_code=0, stdout="==== 1 passed ====", stderr="", duration_ms=1, timed_out=False)

        return FakeSandbox(files, exec_handler=handler)  # type: ignore[arg-type]

    async def grade(self, task: EvalTask, patch: str) -> GradeResult:
        self.graded.append(task.id)
        keep, tamper, ignored = filter_patch(patch)
        ok = "FIXED" in keep
        return GradeResult(resolved=ok, reward=1.0 if ok else 0.0, patch_applied=True, tamper_paths=tamper,
                           ignored_paths=ignored, log_tail="ok" if ok else "1 failed")  # fmt: skip


FINISH = {"summary": "修好", "changes": [{"path": "FIX.py", "kind": "added"}], "tests_run": ["pytest"],
          "tests_passed": True, "confidence": 0.8}  # fmt: skip


def scripted_llm(cfg: RunConfig) -> LLMAgent:
    usage = Usage(input_tokens=1000, cache_hit_tokens=950, cache_miss_tokens=50, output_tokens=100)

    def router() -> FakeRouter:
        return FakeRouter([say(call("write_file", path="FIX.py", content="FIXED = True\n")),
                           say(call("finish", **FINISH))], cost_cny=0.002, usage=usage)  # fmt: skip

    return LLMAgent(router, category=cfg.category, config_hash=cfg.name)


def runner(tmp_path: Path, **kw: Any) -> tuple[EvalRunner, FakeGrader]:
    g = FakeGrader()
    kw.setdefault("now", lambda: OFF_PEAK)
    r = EvalRunner(grader=g, llm_agent_factory=scripted_llm, results_root=tmp_path / "results", **kw)  # type: ignore[arg-type]
    return r, g


ALL_FAKE = [RunConfig.fake("null"), RunConfig.fake("oracle"), RunConfig.fake("tamper")]


async def test_fake_agents_scored(tmp_path: Path, tasks: list[EvalTask]) -> None:
    r, _ = runner(tmp_path)
    s = await r.run(tasks, [*ALL_FAKE, RunConfig(name="scripted", agent="llm")], out_dir=tmp_path / "run")
    by = {(x.config, x.task_id): x for x in s.done}
    n = len(tasks)
    assert len(s.done) == 4 * n
    assert sum(x.resolved for x in s.done if x.agent == "null") == 0
    assert sum(x.resolved for x in s.done if x.agent == "oracle") == n
    tamper = [x for x in s.done if x.agent == "tamper"]
    assert not any(x.resolved for x in tamper)
    assert all(x.false_success and x.tamper_paths == ["conftest.py"] for x in tamper)
    assert sum(x.resolved for x in s.done if x.agent == "llm") == n
    llm = by[("scripted", tasks[0].id)]
    assert llm.cost_cny == pytest.approx(0.004) and llm.tokens_in == 2000 and llm.tokens_cached == 1900
    assert llm.steps == 2 and not llm.live
    # 结果目录：每个 attempt 四个文件，轨迹能读回
    d = tmp_path / "run" / "scripted" / tasks[0].id / "1"
    assert {p.name for p in d.iterdir()} >= {"result.json", "patch.diff", "trajectory.jsonl", "verifier.log"}
    assert "FIXED" in (d / "patch.diff").read_text()
    kinds = [e.kind for e in Trajectory.read_events(d / "trajectory.jsonl")]
    assert kinds[0] == "task_started" and kinds[-1] == "task_finished" and "model_call" in kinds
    null_kinds = [e.kind for e in Trajectory.read_events(tmp_path / "run" / "null-agent" / tasks[0].id / "1" /
                                                          "trajectory.jsonl")]  # fmt: skip
    assert null_kinds == ["task_started", "task_finished"]


async def test_ac5_report_matches_results(tmp_path: Path, tasks: list[EvalTask]) -> None:
    r, _ = runner(tmp_path)
    out = tmp_path / "run"
    await r.run(tasks, [*ALL_FAKE, RunConfig(name="scripted", agent="llm")], out_dir=out)
    rep = write_report(out)
    rows = {x.config: x for x in rep.rows}
    results = [json.loads(p.read_text()) for p in out.glob("*/*/*/result.json")]
    for cfg, row in rows.items():
        mine = [x for x in results if x["config"] == cfg]
        assert row.solved == sum(x["resolved"] for x in mine)
        assert row.total_cost_cny == pytest.approx(sum(x["cost_cny"] for x in mine))
        assert row.false_success == sum(x["false_success"] for x in mine)
        assert row.avg_steps == pytest.approx(sum(x["steps"] for x in mine) / len(mine), abs=0.05)
    assert rows["oracle-agent"].resolved_at_1 == 1.0 and rows["null-agent"].resolved_at_1 == 0.0
    assert rows["tamper-agent"].tampered == len(tasks) and rows["tamper-agent"].false_success == len(tasks)
    assert rows["scripted"].cost_per_resolved == pytest.approx(0.004)
    assert rows["scripted"].cache_hit_rate == pytest.approx(0.95)
    md = (out / "report.md").read_text(encoding="utf-8")
    for col in ("Resolved@1", "解决/总数", "总成本", "平均每任务", "每解决任务", "平均步数", "平均耗时", "虚假成功",
                "缓存命中"):  # fmt: skip
        assert col in md
    assert "tamper-agent" in md and "虚假成功（声称修好" in md
    assert json.loads((out / "report.json").read_text())["rows"]
    assert rep.missing == []


async def test_ac4_resume_after_interrupt(tmp_path: Path, tasks: list[EvalTask]) -> None:
    out = tmp_path / "run"
    calls: list[str] = []

    third = asyncio.Event()

    class Interrupting(NullAgent):
        async def solve(self, task, sandbox, rec):  # type: ignore[no-untyped-def]
            calls.append(task.id)
            if len(calls) == 3:
                third.set()
                await asyncio.sleep(3600)  # 第 3 个 attempt 进行中时被 Ctrl-C
            return await super().solve(task, sandbox, rec)

    r, _ = runner(tmp_path)
    r._agent = lambda cfg: Interrupting()  # type: ignore[method-assign]
    run = asyncio.create_task(r.run(tasks, [RunConfig.fake("null")], out_dir=out, concurrency=1))
    await third.wait()
    run.cancel()  # asyncio.run 收到 KeyboardInterrupt 时同样是取消主任务
    with pytest.raises(asyncio.CancelledError):
        await run
    done_first = len(list(out.glob("*/*/*/result.json")))
    assert done_first == 2
    assert len(build_report(out).missing) == len(tasks) - 2

    calls.clear()
    r2, _ = runner(tmp_path)
    r2._agent = lambda cfg: NullAgent()  # type: ignore[method-assign]
    seen: list[str] = []
    orig = r2.run_attempt

    async def spy(job, d):  # type: ignore[no-untyped-def]
        seen.append(job.task.id)
        return await orig(job, d)

    r2.run_attempt = spy  # type: ignore[method-assign]
    s = await r2.run(tasks, [RunConfig.fake("null")], out_dir=out, concurrency=1)
    assert s.skipped_existing == 2 and len(seen) == len(tasks) - 2
    assert len(list(out.glob("*/*/*/result.json"))) == len(tasks)


async def test_infra_error_leaves_attempt_for_resume(tmp_path: Path, tasks: list[EvalTask]) -> None:
    r, g = runner(tmp_path)
    g.fail_on = tasks[1].id
    s = await r.run(tasks, [RunConfig.fake("null")], out_dir=tmp_path / "run")
    assert len(s.done) == len(tasks) - 1 and list(s.infra_errors) == [f"null-agent/{tasks[1].id}/1"]
    assert "docker 挂了" in (tmp_path / "run" / "errors.json").read_text(encoding="utf-8")
    assert not (tmp_path / "run" / "null-agent" / tasks[1].id / "1" / "result.json").exists()


# ---------------------------------------------------------------- 费用护栏（live 才生效）
LLM = [RunConfig(name="baseline", agent="llm", category="baseline")]


async def test_ac7_estimate_over_cap_does_not_start(tmp_path: Path, tasks: list[EvalTask]) -> None:
    r, g = runner(tmp_path, live=True, max_total_cny=1.0, per_task_estimate_cny=0.3)
    with pytest.raises(EstimateTooHigh, match="超过上限"):
        await r.run(tasks, LLM, out_dir=tmp_path / "run")
    assert g.sandboxes == 0 and not (tmp_path / "run").exists()


async def test_peak_blocks_live_start(tmp_path: Path, tasks: list[EvalTask]) -> None:
    r, g = runner(tmp_path, live=True, now=lambda: PEAK, per_task_estimate_cny=0.01)
    r.gate.now = lambda: PEAK
    with pytest.raises(PeakHourBlocked):
        await r.run(tasks, LLM, out_dir=tmp_path / "run")
    assert g.sandboxes == 0


async def test_peak_does_not_block_offline_or_fake(tmp_path: Path, tasks: list[EvalTask]) -> None:
    r, _ = runner(tmp_path, now=lambda: PEAK)
    r.gate.now = lambda: PEAK
    s = await r.run(tasks[:1], [*LLM, RunConfig.fake("null")], out_dir=tmp_path / "run")
    assert len(s.done) == 2 and s.estimate_cny == 0


async def test_crossing_into_peak_stops_dispatch(tmp_path: Path, tasks: list[EvalTask]) -> None:
    clock = iter([OFF_PEAK, OFF_PEAK] + [PEAK] * 100)
    r, _ = runner(tmp_path, live=True, per_task_estimate_cny=0.01)
    r.gate.now = lambda: next(clock)
    s = await r.run(tasks, LLM, out_dir=tmp_path / "run", concurrency=1)
    assert len(s.done) == 1 and s.deferred_peak == len(tasks) - 1
    assert len(build_report(tmp_path / "run").missing) == len(tasks) - 1


async def test_ledger_envelope_precheck(tmp_path: Path, tasks: list[EvalTask]) -> None:
    ledger = GlobalLedger(
        tmp_path / "spend.sqlite", total_cny=100, envelopes={"baseline": 0.05}, stop_file=tmp_path / "STOP"
    )
    r, g = runner(tmp_path, live=True, ledger=ledger, per_task_estimate_cny=0.02)
    with pytest.raises(BudgetExceeded, match="baseline"):
        await r.run(tasks, LLM, out_dir=tmp_path / "run")
    assert g.sandboxes == 0


async def test_non_replay_mode_requires_live(tmp_path: Path, tasks: list[EvalTask],
                                             monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.setenv("TW_LLM_MODE", "live")
    r, _ = runner(tmp_path)
    with pytest.raises(ConfigError, match="--live"):
        await r.run(tasks, LLM, out_dir=tmp_path / "run")
    s = await r.run(tasks[:1], [RunConfig.fake("null")], out_dir=tmp_path / "run2")  # 假 Agent 不受影响
    assert len(s.done) == 1


def test_estimate_uses_history(tmp_path: Path) -> None:
    root = tmp_path / "results"
    for i, c in enumerate([0.1, 0.3]):
        d = root / "ts" / "cfg" / f"t{i}" / "1"
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps({"agent": "llm", "live": True, "cost_cny": c}))
    assert historical_avg_cost(root) == pytest.approx(0.2)
    assert historical_avg_cost(tmp_path / "none") is None


def test_run_config_rejects_pro(tmp_path: Path) -> None:
    p = tmp_path / "c.yaml"
    p.write_text("name: x\nexecutor: {model: deepseek-v4-pro}\n")
    with pytest.raises(ConfigError, match="deepseek-flash"):
        RunConfig.load(p)
    cfg = RunConfig.load(Path(__file__).resolve().parents[3] / "configs" / "runs" / "baseline-deepseek.yaml")
    assert cfg.agent == "llm" and cfg.attempts == 1


async def test_oracle_and_tamper_agents_on_fake_sandbox(tasks: list[EvalTask]) -> None:
    g = FakeGrader()
    sb = await g.new_sandbox(tasks[0])
    run = await OracleAgent().solve(tasks[0], sb, TrajectoryRecorder("t", "r"))
    assert run.claimed_success and "FIXED" in run.diff and ".tw/oracle" not in run.diff
    assert any("solve.sh" in c for c in sb.commands)
    sb2 = await g.new_sandbox(tasks[0])
    run2 = await TamperAgent().solve(tasks[0], sb2, TrajectoryRecorder("t", "r"))
    assert run2.claimed_success and "conftest.py" in run2.diff


def test_markdown_render_empty(tmp_path: Path) -> None:
    rep = build_report(tmp_path)
    assert "Resolved@1" in render_markdown(rep)
