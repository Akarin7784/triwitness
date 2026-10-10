"""W2-24：报告 v1（bootstrap CI、失败分类、infra_error 不计分母）+ 按历史估算。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from triwitness.cli.main import app
from triwitness.eval.report import bootstrap_ci, build_report, classify, render_markdown
from triwitness.eval.runner import AttemptResult, historical_usage


def result(task: str, *, config: str = "cfg", attempt: int = 1, **kw: Any) -> AttemptResult:
    base: dict[str, Any] = dict(
        task_id=task, config=config, agent="llm", attempt=attempt, resolved=False, reward=0.0,
        agent_status="finished", agent_claimed_success=False, false_success=False,
        trajectory_id=f"{config}/{task}/{attempt}/trajectory.jsonl",
    )  # fmt: skip
    base.update(kw)
    return AttemptResult.model_validate(base)


def write(run: Path, rs: list[AttemptResult]) -> None:
    for r in rs:
        d = run / r.config / r.task_id / str(r.attempt)
        d.mkdir(parents=True, exist_ok=True)
        (d / "result.json").write_text(r.model_dump_json(), encoding="utf-8")


def test_classify_priority() -> None:
    assert classify(result("a", resolved=True, reward=1.0)) == "resolved"
    assert classify(result("a", reward=None)) == "infra_error"
    assert classify(result("a", reward=None, patch_applied=False)) == "patch_not_applied"
    assert classify(result("a", agent_claimed_success=True, false_success=True)) == "false_success"
    assert classify(result("a", agent_status="budget_exceeded")) == "agent_error"
    assert classify(result("a")) == "unresolved"


def test_bootstrap_ci_is_deterministic_and_brackets_mean() -> None:
    xs = [True] * 6 + [False] * 4
    ci = bootstrap_ci(xs)
    assert ci is not None and ci == bootstrap_ci(xs)
    assert ci[0] < 0.6 < ci[1] and ci[0] >= 0.2 and ci[1] <= 0.95
    assert bootstrap_ci([True] * 5) == (1.0, 1.0)
    assert bootstrap_ci([]) is None
    wide, narrow = bootstrap_ci([True, False] * 5), bootstrap_ci([True, False] * 50)
    assert wide and narrow and (wide[1] - wide[0]) > (narrow[1] - narrow[0])


def test_infra_errors_excluded_from_denominator(tmp_path: Path) -> None:
    write(tmp_path, [
        result("t1", resolved=True, reward=1.0),
        result("t2"),
        result("t3", reward=None, error="docker: no space left"),
        result("t4", agent_claimed_success=True, false_success=True),
    ])  # fmt: skip
    (tmp_path / "errors.json").write_text(json.dumps({"cfg/t5/1": "SandboxError: boom"}), encoding="utf-8")
    rep = build_report(tmp_path)
    row = rep.rows[0]
    assert (row.solved, row.graded, row.resolved_at_1) == (1, 3, pytest.approx(1 / 3))
    assert row.failure_categories == {"resolved": 1, "infra_error": 1, "false_success": 1, "unresolved": 1}
    assert set(rep.infra_errors) == {"cfg/t3/1", "cfg/t5/1"}
    assert row.ci95 is not None
    md = render_markdown(rep)
    assert "1/3" in md and "## 失败分类" in md and "基础设施错误（不计入分母）" in md and "cfg/t5/1" in md
    assert "Resolved@1（95% CI）" in md and "33%（" in md


def test_historical_usage_and_cli_estimate(tmp_path: Path) -> None:
    root = tmp_path / "results"
    write(root / "ts", [
        result("a", live=True, tokens_in=100_000, tokens_cached=90_000, tokens_out=4_000, cost_cny=0.02),
        result("b", live=True, tokens_in=300_000, tokens_cached=290_000, tokens_out=6_000, cost_cny=0.04),
        result("c", live=False, tokens_in=999_999),  # 回放不算
        result("d", agent="null"),
    ])  # fmt: skip
    h = historical_usage(root)
    assert h is not None
    assert (h.n, h.avg_input_tokens, h.avg_output_tokens, h.cache_hit_rate) == (2, 200_000, 5_000, 0.95)
    assert h.avg_cost_cny == pytest.approx(0.03)
    assert historical_usage(tmp_path / "none") is None

    cli = CliRunner()
    out = cli.invoke(app, ["eval", "estimate", "--tasks", "10", "--results", str(root)]).output
    assert "历史：2 次" in out and "输入 2,000,000" in out and "命中率 95%" in out
    out2 = cli.invoke(app, ["eval", "estimate", "--tasks", "10", "--results", str(root), "--no-history"]).output
    assert "W1 先验" in out2 and "输入 8,000,000" in out2


def test_stale_errors_json_entry_with_result_is_not_infra(tmp_path: Path) -> None:
    """errors.json 里的 attempt 若续跑后已有 result.json，以 result 为准（不重复计为基础设施错误）。"""
    write(tmp_path, [result("t1", resolved=True, reward=1.0), result("t2")])
    (tmp_path / "errors.json").write_text(json.dumps({"cfg/t2/1": "BuildError: apt", "cfg/t9/1": "x"}),
                                          encoding="utf-8")  # fmt: skip
    rep = build_report(tmp_path)
    assert set(rep.infra_errors) == {"cfg/t9/1"} and rep.rows[0].graded == 2


def test_test_edits_counted_separately_from_tamper(tmp_path: Path) -> None:
    write(tmp_path, [
        result("t1", resolved=True, reward=1.0, edited_paths=["tests/test_a.py"]),
        result("t2", tamper_paths=["conftest.py"], edited_paths=["tests/test_b.py"]),
    ])  # fmt: skip
    row = build_report(tmp_path).rows[0]
    assert row.tampered == 1 and row.test_edited == 1
