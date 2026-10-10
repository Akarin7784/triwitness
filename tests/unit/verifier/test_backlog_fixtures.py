"""W3 验证器 backlog：真实失败模式做成离线 fixture（tests/fixtures/verifier/<case>/）。

每个 case 有 Issue 摘录、Agent 的完成声明、补丁、隐藏测试失败输出与期望判定。现在只校验 fixture 自洽，
并用一个 strict xfail 占位：W3 实现 `triwitness.verify` 后它会变成 XPASS → 失败，提醒删掉 xfail 改成正式断言。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from triwitness.core.models import FinishReport
from triwitness.eval.grade import split_patch

CASES = Path(__file__).resolve().parents[2] / "fixtures" / "verifier"
FLAGS = {"repro_not_tied_to_issue", "issue_underspecified", "claim_contradicts_open_risks"}


def cases() -> list[Path]:
    return sorted(p for p in CASES.iterdir() if (p / "case.json").is_file())


def load(d: Path) -> dict:  # type: ignore[type-arg]
    return json.loads((d / "case.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("d", cases(), ids=lambda p: p.name)
def test_case_is_self_consistent(d: Path) -> None:
    c = load(d)
    assert c["id"] == d.name and c["license"] and c["source"]
    claim = FinishReport.model_validate(c["claim"])
    assert claim.tests_passed and c["grader"] == {"resolved": False, "false_success": True}  # 都是“虚假成功”
    assert c["expected"]["verdict"] in ("fail", "insufficient_evidence")
    assert set(c["expected"]["must_flag"]) <= FLAGS
    patch = (d / c["agent_patch"]).read_text(encoding="utf-8")
    paths = [f.path for f in split_patch(patch)]
    assert claim.repro is not None and claim.repro.path in paths  # 复现测试确实在补丁里
    assert (d / c["hidden_failure"]).read_text(encoding="utf-8").strip()


def _asserted_names(patch: str, repro_path: str) -> set[str]:
    body = next(f.text for f in split_patch(patch) if f.path == repro_path)
    return set(re.findall(r'"([A-Z][A-Z_]{2,})"', body))


def test_self_repro_name_mismatch_signal_is_computable_offline() -> None:
    """验证器要用到的信号之一今天就能离线算出来：复现测试断言的 token 名在 Issue 里一个都没出现。"""
    d = CASES / "self_repro_name_mismatch"
    c = load(d)
    names = _asserted_names((d / c["agent_patch"]).read_text(encoding="utf-8"), c["claim"]["repro"]["path"])
    assert {"LBRACKET", "RBRACKET"} <= names
    issue_idents = set(re.findall(r"[A-Za-z_]{3,}", c["issue_excerpt"]))
    assert not (names & issue_idents)  # repro_not_tied_to_issue
    assert "UNSIGNED_INT" in (d / c["hidden_failure"]).read_text(encoding="utf-8")  # 隐藏测试要的是别的名字
    risks = " ".join(c["claim"]["open_risks"])
    assert "not covered" in risks and c["claim"]["confidence"] >= 0.8  # claim_contradicts_open_risks


@pytest.mark.xfail(strict=True, reason="W3 验证器尚未实现（backlog：tests/fixtures/verifier/）")
@pytest.mark.parametrize("d", cases(), ids=lambda p: p.name)
def test_w3_verifier_flags_case(d: Path) -> None:
    from triwitness.verify import verify_claim  # type: ignore[import-not-found]  # W3

    c = load(d)
    verdict = verify_claim(issue=c["issue_excerpt"], claim=c["claim"],
                           patch=(d / c["agent_patch"]).read_text(encoding="utf-8"))  # fmt: skip
    assert verdict.verdict == c["expected"]["verdict"]
    assert set(c["expected"]["must_flag"]) <= set(verdict.flags)
