"""`tw eval reverify`：在已保存的 W2 结果上只重跑验证阶段（不重跑 Executor、不重新判分）。离线。"""

from __future__ import annotations

from pathlib import Path

import pytest

from triwitness.core.errors import ConfigError
from triwitness.eval.report import build_report, render_markdown
from triwitness.eval.reverify import load_saved, reverify
from triwitness.eval.runner import EstimateTooHigh, EvalRunner, RunConfig
from triwitness.eval.task import EvalTask, discover, load_task
from triwitness.llm.gate import PeakGate

from .test_eval_verifier import DEV, VerifyingGrader, scripted, verdict_router
from .test_runner import OFF_PEAK


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


# ---------------------------------------------------------------- W3-14：每个补丁判多次 + 复用确定性证据 + 硬上限


class CountingGrader(VerifyingGrader):
    def __init__(self) -> None:
        super().__init__()
        self.sandboxes = 0

    async def new_sandbox(self, task: EvalTask):  # type: ignore[no-untyped-def, override]
        self.sandboxes += 1
        return await super().new_sandbox(task)


def test_majority_ties_are_conservative() -> None:
    from triwitness.eval.verification import majority

    assert majority(["pass", "pass", "fail"]) == "pass"
    assert majority(["pass", "fail", "inconclusive"]) == "fail"
    assert majority(["pass", "inconclusive"]) == "inconclusive"
    assert majority(["fail"]) == "fail"


def split_router():  # type: ignore[no-untyped-def]
    from triwitness.harness.testing import FakeRouter, call, say

    verdicts = ["pass", "fail", "pass"]  # 三次里一次翻转：多数票 pass
    return FakeRouter([say(call("submit_verdict", verdict=v, confidence=c, rationale="x"))
                       for v, c in zip(verdicts, (0.9, 0.6, 0.7), strict=True)])  # fmt: skip


async def test_model_repeats_reuse_deterministic_evidence(saved: Path, tmp_path: Path, tasks: list[EvalTask]) -> None:
    g = CountingGrader()
    out = tmp_path / "rep"
    s = await reverify(saved, out, tasks=by_id(tasks), grader=g, modes=("deterministic", "model"),
                       router_factory=split_router, configs=["w2"], model_repeats=3)  # fmt: skip
    n = len(tasks)
    det_boxes = g.sandboxes
    assert det_boxes > 0 and s.reused_deterministic == n and not s.errors
    import json

    t = tasks[0].id
    v = json.loads((out / "w2+model" / t / "1" / "verification.json").read_text(encoding="utf-8"))
    det = json.loads((out / "w2+deterministic" / t / "1" / "verification.json").read_text(encoding="utf-8"))
    assert [j["verdict"] for j in v["model_judgments"]] == ["pass", "fail", "pass"]
    assert v["model_verdict"] == "pass" and v["model_confidence"] == 0.8  # 多数一方的平均置信度
    assert v["test_runs"] == det["test_runs"] and v["repro_status"] == det["repro_status"]  # 同一份复跑证据
    assert abs(v["cost_cny"] - 0.003) < 1e-9  # 三次判读的花费都记上
    # 只有 deterministic 档建了沙箱：model 档完全复用
    g2 = CountingGrader()
    await reverify(saved, tmp_path / "rep2", tasks=by_id(tasks), grader=g2, modes=("deterministic",), configs=["w2"])
    assert g2.sandboxes == det_boxes


async def test_hard_cap_stops_dispatch(saved: Path, tmp_path: Path, tasks: list[EvalTask]) -> None:
    s = await reverify(saved, tmp_path / "cap", tasks=by_id(tasks), grader=VerifyingGrader(),
                       modes=("deterministic", "model"), router_factory=split_router, configs=["w2"],
                       model_repeats=3, max_total_cny=0.004, concurrency=1)  # fmt: skip
    # 每个 attempt ¥0.003：第一个之后“已花 + 1.5×均值” = 0.0075 > 0.004，后面都不派发
    assert s.model_judged == 1 and len(s.capped) == len(tasks) - 1
    assert s.verifier_cost_cny <= 0.004


async def test_default_policy_skips_model_on_non_pass(saved: Path, tmp_path: Path, tasks: list[EvalTask]) -> None:
    """默认 thin_pass：确定性不是 pass（篡改 Agent）就不调模型；always 才每个都判。"""
    calls: list[int] = []

    def router():  # type: ignore[no-untyped-def]
        calls.append(1)
        return verdict_router()

    s = await reverify(saved, tmp_path / "thin", tasks=by_id(tasks), grader=VerifyingGrader(),
                       modes=("deterministic", "model"), router_factory=router, configs=["tamp"])  # fmt: skip
    assert s.verifier_cost_cny == 0.0
    import json

    t = tasks[0].id
    v = json.loads((tmp_path / "thin" / "tamp+model" / t / "1" / "verification.json").read_text(encoding="utf-8"))
    assert v["model_judgments"] == [] and v["model_skipped"] and v["verdict"] != "pass"
    s2 = await reverify(saved, tmp_path / "always", tasks=by_id(tasks), grader=VerifyingGrader(),
                        modes=("deterministic", "model"), router_factory=router, configs=["tamp"],
                        model_policy="always")  # fmt: skip
    assert s2.model_judged == len(tasks)
