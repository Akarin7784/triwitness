from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from triwitness.core import models as m

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
U = m.Usage(input_tokens=100, cache_hit_tokens=90, cache_miss_tokens=10, output_tokens=5)


def _cost_report() -> m.CostReport:
    line = m.CostLine(role="executor", vendor="deepseek", model="deepseek-flash", calls=2, usage=U, cost_cny=0.01)
    return m.CostReport.from_lines("t_x", [line], budget_cny=0.8, pricing_version="2026-10-10")


def _samples() -> list[BaseModel]:
    repo = m.RepoRef(full_name="o/r", base_commit="abc")
    fr = m.FinishReport(
        summary="fix",
        changes=[m.FileChange(path="a.py", kind="modified")],
        repro=m.ReproRef(path="tests/tw_repro/test_issue_1.py", cmd="pytest -q tests/tw_repro/test_issue_1.py"),
        tests_passed=True,
        confidence=0.7,
    )
    mc = m.ModelCall(
        vendor="deepseek",
        model="deepseek-flash",
        role="executor",
        thinking=True,
        usage=U,
        cost_cny=0.001,
        latency_ms=10,
        prompt_version="p1",
    )
    tc = m.ToolCall(id="c1", name="read_file", arguments={"path": "a.py"}, started_at=NOW)
    step = m.Step(index=0, agent="executor", kind="model_call", model_call=mc, ts=NOW)
    ev = m.Evidence(
        task_id="t_x",
        summary="s",
        root_cause="r",
        repro_status="reproduced",
        test_runs=[m.TestRun(scope="full", command="pytest", passed=1, failed=0, skipped=0, duration_s=1, log_ref="l")],
        static_checks={"ruff": "pass"},
        verdict="pass",
        verifier_model="deepseek-flash",
        criteria_results={"AC1": "met"},
        findings=[m.Finding(severity="nit", message="m")],
        risk_score=3,
        risk_level="L1",
        risk_factors=[m.RiskFactor(code="c", points=3, detail="d")],
        diff_stats={"files": 1},
        cost=_cost_report(),
        config_hash="h",
    )
    plan = m.Plan(
        task_id="t_x",
        root_cause_hypothesis="h",
        affected_files=["a.py"],
        repro_strategy="test",
        acceptance_criteria=[m.AcceptanceCriterion(id="AC1", description="d", check="test", detail="t")],
        steps=[m.PlanStep(id="s1", goal="g")],
        estimated_risk="L1",
        model="deepseek-flash",
    )
    task = m.Task(
        id="t_x",
        source="cli",
        repo=repo,
        title="t",
        body="b",
        harness_config="baseline",
        config_hash="h",
        created_at=NOW,
    )
    traj = m.Trajectory(
        task_id="t_x",
        run_id="r_x",
        config_hash="h",
        harness_config="baseline",
        prompt_versions={"executor": "p1"},
        model_routing={"executor": "deepseek-flash"},
        steps=[step, m.Step(index=1, agent="executor", kind="tool_call", tool_call=tc, ts=NOW)],
        final_state=m.TaskState.DONE,
        evidence=ev,
        started_at=NOW,
    )
    return [m.Budget(), repo, task, plan, fr, mc, tc, step, ev, traj, _cost_report()]


@pytest.mark.parametrize("obj", _samples(), ids=lambda o: type(o).__name__)
def test_json_round_trip(obj: BaseModel) -> None:
    again = type(obj).model_validate_json(obj.model_dump_json())
    assert again == obj


def test_budget_defaults_match_adr_0002() -> None:
    b = m.Budget()
    # 1M 档：输入两项由工作预算（≈951,582）推导：≈60M / ≈2.85M（原 6M / 400K）
    assert (b.max_cost_cny, b.max_input_tokens, b.max_output_tokens) == (None, 59_949_666, 100_000)
    assert b.max_uncached_input_tokens == 2_854_746
    assert (b.max_turns, b.max_wall_seconds, b.warn_ratio) == (100, 1800, 0.8)
    r = m.Budget.for_run()
    assert (r.max_cost_cny, r.max_wall_seconds) == (None, 2700)
    assert m.Budget(max_cost_cny=1.0).max_cost_cny == 1.0  # 旧配置仍可读入（随后忽略）


@pytest.mark.parametrize("bad", [-0.1, 1.01])
def test_finish_confidence_bounds(bad: float) -> None:
    with pytest.raises(ValidationError):
        m.FinishReport(summary="s", changes=[], tests_passed=False, confidence=bad)


def test_usage_split_must_add_up() -> None:
    with pytest.raises(ValidationError):
        m.Usage(input_tokens=10, cache_hit_tokens=5, cache_miss_tokens=4)


def test_usage_add_and_hit_rate() -> None:
    total = U + U
    assert total.input_tokens == 200 and total.cache_hit_rate == pytest.approx(0.9)
    assert total.reasoning_tokens is None


def test_cost_report_from_lines_and_flat() -> None:
    cr = _cost_report()
    assert cr.total_cny == pytest.approx(0.01)
    assert cr.cache_hit_rate == pytest.approx(0.9)
    flat = cr.to_flat()
    assert flat["calls"] == 2 and flat["cache_hit_tokens"] == 90 and flat["peak_calls"] == 0


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValidationError):
        m.Step(index=0, agent="executor", kind="human", ts=datetime(2026, 10, 10, 12, 0))


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        m.Budget.model_validate({"max_steps": 60})
