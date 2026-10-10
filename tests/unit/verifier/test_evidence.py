"""W3-12：证据包组装 + PR 正文渲染（快照）。全部离线，模型结果用固定值代替。

快照更新：UPDATE_SNAPSHOTS=1 uv run pytest tests/unit/verifier/test_evidence.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from triwitness.core.models import (
    CostLine,
    CostReport,
    Evidence,
    Finding,
    FinishReport,
    ReproRef,
    TestRun,
    Usage,
)
from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.verify.claim import verify_claim
from triwitness.verify.evidence import build_evidence, render_pr
from triwitness.verify.rerun import RerunResult, regression, rerun_repro
from triwitness.verify.testing import make_patch, make_repo, modify, new_file

from .test_rerun_local import FIXED, PY, REPRO, CleanLocal, repro_test

SNAP = Path(__file__).resolve().parents[2] / "fixtures" / "verifier" / "snapshots"
FIX = "calc.py"
PATCH = modify(FIX, ["    return a - b"], ["    return a + b"], start=2) + new_file(
    REPRO, ["from calc import add", "", "", "def test_issue_1():", "    assert add(1, 2) == 3"]
)


def snapshot(name: str, text: str) -> None:
    path = SNAP / name
    if os.environ.get("UPDATE_SNAPSHOTS") or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    assert text == path.read_text(encoding="utf-8")


def cost() -> CostReport:
    lines = [
        CostLine(role="executor", vendor="deepseek", model="deepseek-flash", calls=12,
                 usage=Usage(input_tokens=1_200_000, cache_hit_tokens=1_056_000,
                             cache_miss_tokens=144_000, output_tokens=41_000), cost_cny=0.66),
        CostLine(role="verifier", vendor="deepseek", model="deepseek-flash", calls=1,
                 usage=Usage(input_tokens=48_000, cache_hit_tokens=34_080,
                             cache_miss_tokens=13_920, output_tokens=3_000), cost_cny=0.2),
    ]  # fmt: skip
    return CostReport.from_lines("t1", lines, budget_cny=5, pricing_version="2026-10")


def finish(**kw: object) -> FinishReport:
    base: dict[str, object] = dict(
        summary="修复了 #1 中 add() 把加法写成减法的问题。", changes=[{"path": FIX, "kind": "modified"}],
        repro=ReproRef(path=REPRO, cmd=f"pytest {REPRO}"), tests_run=["tests"], tests_passed=True,
        confidence=0.9, open_risks=[],
    )  # fmt: skip
    base.update(kw)
    return FinishReport.model_validate(base)


def runs(base_failed: int = 1, patched_failed: int = 0) -> list[TestRun]:
    return [
        TestRun(scope="repro_base", command="pytest", passed=1 - base_failed, failed=base_failed,
                skipped=0, duration_s=0.4, log_ref="verify/repro_base.xml"),
        TestRun(scope="repro_patched", command="pytest", passed=1 - patched_failed,
                failed=patched_failed, skipped=0, duration_s=0.4, log_ref="verify/repro_patched.xml"),
    ]  # fmt: skip


FULL = TestRun(scope="full", command="pytest", passed=809, failed=3, skipped=0, duration_s=61.0,
               log_ref="verify/full.xml")  # fmt: skip
ISSUE = "`add(1, 2)` returns `-1`, expected `3`.\n\n```python\n>>> add(1, 2)\n-1\n```"


def evidence(**kw: object) -> Evidence:
    args: dict[str, object] = dict(
        task_id="t1", finish=finish(), patch=PATCH, root_cause="`add()` 用了减号。",
        rerun=RerunResult(repro_status="reproduced", clean_env="verified", test_runs=runs()),
        regression=FULL, static_checks={"ruff": "pass", "pyright": "pass"}, verdict="pass",
        verifier_model="deepseek-flash", verifier_confidence=0.9,
        criteria_results={"add 返回和": "met"}, cost=cost(), config_hash="h:7f3a01",
        base_ref="abc1234def", review_model="deepseek-flash", review_variant="strict-reviewer",
        findings=[Finding(severity="minor", file=FIX, line=1, message="docstring 未更新", status="fixed")],
    )  # fmt: skip
    args.update(kw)
    ev, _ = build_evidence(**args)  # type: ignore[arg-type]
    return ev


def test_clean_pass_is_l0_and_matches_snapshot() -> None:
    ev = evidence()
    assert (ev.risk_level, ev.verdict, ev.clean_env) == ("L0", "pass", "verified")
    assert ev.diff_stats == {"files": 2, "added": 6, "removed": 1}
    assert ev.anticheat_flags == [] and ev.claim_flags == []
    md = render_pr(ev, issue_ref="#1", version="0.1.0")
    assert "3 个为基线已有失败" in md and "¥0.86" in md and "1.2M（88%）" in md
    snapshot("pr_clean_l0.md", md)


def test_no_sandbox_is_unverified_l2_with_banner() -> None:
    ev = evidence(rerun=RerunResult(repro_status="reproduced", clean_env="unverified",
                                    unverified_reason="no_sandbox", test_runs=runs()))  # fmt: skip
    assert ev.clean_env == "unverified" and ev.unverified_reason == "no_sandbox"
    assert ev.risk_level == "L2"
    md = render_pr(ev, issue_ref="#1")
    assert "干净环境未验证（未启用沙箱）" in md and "不自动合并" in md
    snapshot("pr_no_sandbox_l2.md", md)


def test_skip_added_needs_human_review_l2() -> None:
    """W3-15：单独新增 skip 从 L3 阻断降为 L2 人审——结论 inconclusive（不放行、也不判失败）。"""
    cheat = PATCH + modify("tests/test_calc.py", ["def test_old():"],
                           ["@pytest.mark.skip", "def test_old():"])  # fmt: skip
    ev = evidence(patch=cheat)
    assert ev.verdict == "inconclusive" and ev.risk_level == "L2"
    md = render_pr(ev)
    assert "无新增 skip ❌" in md


def test_crosstl_style_claim_downgrades_to_inconclusive() -> None:
    """crosstl-257 类：自写复现通过，但复现与 Issue 无关、Issue 本身欠明确 → 证据不足。"""
    case_patch = new_file("tests/tw_repro/test_issue_1.py", [
        "def test_issue_1():", '    assert render("foo") == "bar"'])  # fmt: skip
    f = finish(open_risks=["hidden test may expect a different function name"], confidence=0.9)
    claim = verify_claim(issue="Support the new syntax in the parser.", claim=f, patch=case_patch)
    ev = evidence(finish=f, patch=case_patch, claim=claim)
    assert ev.verdict == "inconclusive"
    assert {"repro_not_tied_to_issue", "issue_underspecified"} <= set(ev.claim_flags)
    assert ev.risk_level in ("L1", "L2", "L3")
    assert "声明审计" in render_pr(ev)


def test_open_major_finding_and_failed_repro_raise_risk() -> None:
    ev = evidence(
        rerun=RerunResult(repro_status="failed", clean_env="verified", test_runs=runs(1, 1)),
        findings=[Finding(severity="major", message="未处理负数")],
    )
    codes = {f.code for f in ev.risk_factors}
    assert {"review_major_open", "repro_not_reproduced"} <= codes
    md = render_pr(ev)
    assert "❌ 仍失败" in md and "[major][未处理] 未处理负数" in md


def test_evidence_roundtrips_json() -> None:
    ev = evidence()
    assert Evidence.model_validate_json(ev.model_dump_json()) == ev


@pytest.mark.parametrize("backend_cls", [LocalSandboxBackend, CleanLocal])
async def test_end_to_end_local(tmp_path: Path, backend_cls: type[LocalSandboxBackend]) -> None:
    """真实 none 后端跑复现 + 回归，再组装证据包：none → unverified/L2，干净后端 → verified/L0。"""
    repo = make_repo(tmp_path, {"calc.py": "def add(a, b):\n    return a - b\n",
                                "tests/__init__.py": "", "tests/tw_repro/__init__.py": ""})  # fmt: skip
    patch = make_patch(repo, {"calc.py": FIXED, REPRO: repro_test("assert add(1, 2) == 3")})
    backend, spec = backend_cls(home=tmp_path / "home"), SandboxSpec(repo=repo)
    rr = await rerun_repro(backend, spec, patch, ReproRef(path=REPRO, cmd=f"{PY} {REPRO}"))
    reg, _ = await regression(backend, spec, patch, f"{PY} tests")
    ev, risk = build_evidence(task_id="e2e", finish=finish(), patch=patch, rerun=rr, regression=reg,
                              verdict="pass", verifier_model="fake", cost=cost(), config_hash="h:0")  # fmt: skip
    assert ev.repro_status == "reproduced"
    if backend_cls is CleanLocal:
        assert (ev.clean_env, ev.risk_level, risk.needs_human) == ("verified", "L0", False)
    else:
        assert (ev.clean_env, ev.risk_level) == ("unverified", "L2")
    assert [r.scope for r in ev.test_runs] == ["repro_base", "repro_patched", "full"]
    assert "### 复现" in render_pr(ev)


def test_static_report_feeds_checks_and_risk() -> None:
    from triwitness.verify.static_checks import SecretHit, StaticReport

    st = StaticReport(checks={"ruff": "pass", "bandit": "fail", "secrets": "fail"}, bandit_medium_high=1,
                      secrets=[SecretHit(path="calc.py", line=1, kind="aws_access_key")])  # fmt: skip
    ev = evidence(static=st, static_checks=None)
    assert ev.static_checks == {"ruff": "pass", "bandit": "fail", "secrets": "fail"}
    assert ev.risk_level == "L3" and {"security_scan", "floor:secrets"} <= {f.code for f in ev.risk_factors}
    assert "secrets ❌" in render_pr(ev)
