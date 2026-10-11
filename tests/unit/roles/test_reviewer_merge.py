"""spec 010 §6.3：单评审 / 共识模式的阻断判定。"""

from __future__ import annotations

from triwitness.harness.loop import LoopOutcome
from triwitness.roles.contracts import Review
from triwitness.roles.reviewer import VariantReview, merge

B = {"severity": "blocker", "file": "a.py", "line": 1, "message": "错", "suggestion": "改"}
M = {"severity": "minor", "file": "a.py", "line": 3, "message": "小问题"}


def vr(variant: str, *findings: dict) -> VariantReview:  # type: ignore[type-arg]
    verdict = "request_changes" if any(f["severity"] == "blocker" for f in findings) else "approve"
    r = Review.model_validate({"verdict": verdict, "findings": list(findings)})
    return VariantReview(variant, r, LoopOutcome(status="finished", steps=1), "tool_call", "deepseek-flash")


def test_single_reviewer_blocker_blocks() -> None:
    res = merge([vr("adversarial", B, M)], consensus=False)
    assert res.blocking and [f.severity for f in res.findings] == ["blocker", "minor"]
    assert "a.py:1" in res.feedback() and "小问题" not in res.feedback()


def test_consensus_needs_both() -> None:
    split = merge([vr("adversarial", B), vr("checklist", M)], consensus=True)
    assert not split.blocking and split.consensus
    assert [f.severity for f in split.findings] == ["major", "minor"]
    assert split.findings[0].message.startswith("[仅 adversarial 判为阻断]")
    both = merge([vr("adversarial", B), vr("checklist", B)], consensus=True)
    assert both.blocking and [f.severity for f in both.findings] == ["blocker", "blocker"]
    assert both.variant == "adversarial+checklist"


def test_missing_review_never_blocks() -> None:
    none = VariantReview("adversarial", None, LoopOutcome(status="stuck", steps=3), "没有提交", "?")
    res = merge([none], consensus=False)
    assert not res.blocking and not res.concluded
    assert not merge([none, vr("checklist", B)], consensus=True).blocking  # 一方没结论 → 不算共识
