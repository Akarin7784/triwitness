"""`tw eval reverify`：在已保存的 W2 结果上只重跑验证阶段（不重跑 Executor、不重新判分）。离线。"""

from __future__ import annotations

from pathlib import Path

import pytest

from triwitness.core.errors import ConfigError, PeakHourBlocked
from triwitness.eval.report import build_report, render_markdown
from triwitness.eval.reverify import load_saved, reverify
from triwitness.eval.runner import EstimateTooHigh, EvalRunner, RunConfig
from triwitness.eval.task import EvalTask, discover, load_task
from triwitness.llm.gate import PeakGate

from .test_eval_verifier import DEV, VerifyingGrader, scripted, verdict_router
from .test_runner import OFF_PEAK, PEAK


@pytest.fixture(scope="module")
def tasks() -> list[EvalTask]:
    return [load_task(d) for d in discover(DEV)][:3]


async def make_saved(tmp_path: Path, tasks: list[EvalTask]) -> Path:
    """模拟 W2 基线：llm（verifier=none）+ tamper（自称修好、实际篡改）各跑一遍。"""
    r = EvalRunner(grader=VerifyingGrader(), llm_agent_factory=scripted, results_root=tmp_path,  # type: ignore[arg-type]
                   now=lambda: OFF_PEAK)  # fmt: skip
    await r.run(tasks, [RunConfig(name="w2", agent="llm"), RunConfig(name="tamp", agent="tamper")],
                out_dir=tmp_path / "w2")  # fmt: skip
    return tmp_path / "w2"


@pytest.fixture
async def saved(tmp_path: Path, tasks: list[EvalTask]) -> Path:
    return await make_saved(tmp_path, tasks)


def by_id(tasks: list[EvalTask]) -> dict[str, EvalTask]:
    return {t.id: t for t in tasks}


async def test_load_saved_reads_diff_and_finish(saved: Path) -> None:
    xs = {(s.result.config, s.result.task_id): s for s in load_saved(saved)}
    llm = next(s for (c, _), s in xs.items() if c == "w2")
    assert "FIX.py" in llm.diff and llm.finish is not None and llm.finish.repro is not None
    tamp = next(s for (c, _), s in xs.items() if c == "tamp")
    assert tamp.finish is None or tamp.finish.repro is None  # 假 Agent 没有复现


async def test_three_tiers_without_rerunning_executor(saved: Path, tmp_path: Path, tasks: list[EvalTask]) -> None:
    calls: list[int] = []

    def router():  # type: ignore[no-untyped-def]
        calls.append(1)
        return verdict_router()

    g = VerifyingGrader()
    before = {s.result.config + s.result.task_id: s.result for s in load_saved(saved)}
    out = tmp_path / "rv"
    s = await reverify(saved, out, tasks=by_id(tasks), grader=g, router_factory=router)
    n = len(tasks)
    assert s.done == 3 * 2 * n and not s.errors and not s.missing_task
    assert len(calls) == 2 * n  # 只有 model 档调用 Verifier；Executor 一次都没跑
    assert g.graded == []  # 不重新判分
    rows = {(x.config, x.task_id): x for x in _results(out)}
    t = tasks[0].id
    none, det, mod = rows[("w2+none", t)], rows[("w2+deterministic", t)], rows[("w2+model", t)]
    assert none.verifier_verdict is None and none.resolved == before["w2" + t].resolved
    assert det.verify_repro_status == "reproduced" and det.verifier_model_verdict is None
    assert mod.verifier_model_verdict == "pass" and mod.verifier_verdict == det.verifier_verdict
    assert rows[("tamp+deterministic", t)].verifier_verdict != "pass"  # 篡改：自称修好，验证不放行
    assert (out / "w2+model" / t / "1" / "verification.json").exists()
    rep = build_report(out)
    assert {r.config for r in rep.rows} == {
        f"{c}+{m}" for c in ("w2", "tamp") for m in ("none", "deterministic", "model")
    }
    assert not rep.missing
    md = render_markdown(rep)
    assert "w2+deterministic" in md and "精确率" in md
    v = {r.config: r.verifier for r in rep.rows}["tamp+deterministic"]
    assert v is not None and v.false_success_claimed == n and v.false_success_verified == 0
    # 续跑：全部跳过，Verifier 不再调用
    s2 = await reverify(saved, out, tasks=by_id(tasks), grader=VerifyingGrader(), router_factory=router)
    assert s2.done == 0 and s2.skipped_existing == 3 * 2 * n and len(calls) == 2 * n


def _results(out: Path):  # type: ignore[no-untyped-def]
    from triwitness.eval.report import load_results

    return load_results(out)


async def test_guards(saved: Path, tmp_path: Path, tasks: list[EvalTask]) -> None:
    with pytest.raises(ConfigError):
        await reverify(saved, saved, tasks=by_id(tasks), grader=VerifyingGrader(), modes=("deterministic",))
    with pytest.raises(ConfigError):  # model 档没有 router
        await reverify(saved, tmp_path / "a", tasks=by_id(tasks), grader=VerifyingGrader(), modes=("model",))
    with pytest.raises(PeakHourBlocked):
        await reverify(saved, tmp_path / "b", tasks=by_id(tasks), grader=VerifyingGrader(), modes=("model",),
                       router_factory=verdict_router, live=True, gate=PeakGate(now=lambda: PEAK))  # fmt: skip
    with pytest.raises(EstimateTooHigh):
        await reverify(saved, tmp_path / "c", tasks=by_id(tasks), grader=VerifyingGrader(), modes=("model",),
                       router_factory=verdict_router, live=True, gate=PeakGate(now=lambda: OFF_PEAK),
                       max_total_cny=0.0)  # fmt: skip
    assert not (tmp_path / "c").exists()  # 什么都没运行
    # 缺任务定义：记下来，不中断；只选一个配置
    s = await reverify(saved, tmp_path / "d", tasks={}, grader=VerifyingGrader(), modes=("deterministic",),
                       configs=["w2"])  # fmt: skip
    assert len(s.missing_task) == len(tasks) and s.done == 0


def test_cli_none_tier_and_bad_mode(tmp_path: Path, tasks: list[EvalTask]) -> None:
    import asyncio

    from typer.testing import CliRunner

    from triwitness.cli.main import app

    saved = asyncio.run(make_saved(tmp_path, tasks))
    out = tmp_path / "cli"
    res = CliRunner().invoke(app, ["eval", "reverify", "--results", str(saved), "--out", str(out), "--mode", "none"])
    assert res.exit_code == 0, res.output
    assert "w2+none" in res.output and (out / "report.md").exists()
    bad = CliRunner().invoke(app, ["eval", "reverify", "--results", str(saved), "--mode", "maybe"])
    assert bad.exit_code != 0
