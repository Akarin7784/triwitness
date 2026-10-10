"""声明审计：crosstl 真实失败模式之外的对照组（规格清楚、复现对应 Issue → pass）。"""

from __future__ import annotations

from triwitness.verify.claim import asserted_literals, issue_is_underspecified, verify_claim
from triwitness.verify.testing import modify, new_file

ISSUE = "`parse_rows([])` raises IndexError: list index out of range. It should return an empty list instead."
REPRO = "tests/tw_repro/test_issue_7.py"
PATCH = modify("src/rows.py", ["    return rows[0]"], ["    return rows[0] if rows else []"]) + new_file(
    REPRO, ["from rows import parse_rows", "", "def test_empty():", "    assert parse_rows([]) == []"]
)


def claim(**kw: object) -> dict:  # type: ignore[type-arg]
    base = {"summary": "fix", "changes": [{"path": "src/rows.py", "kind": "modified"}],
            "repro": {"path": REPRO, "cmd": f"pytest {REPRO}"}, "tests_passed": True, "confidence": 0.9}  # fmt: skip
    return base | kw


def test_well_specified_issue_with_tied_repro_passes() -> None:
    v = verify_claim(issue=ISSUE, claim=claim(), patch=PATCH)
    assert (v.verdict, v.flags, v.evidence_verdict) == ("pass", [], "pass")


def test_missing_repro() -> None:
    v = verify_claim(issue=ISSUE, claim=claim(repro=None), patch=PATCH)
    assert v.verdict == "insufficient_evidence" and v.flags == ["repro_missing"]
    v = verify_claim(issue=ISSUE, claim=claim(repro={"path": "tests/tw_repro/nope.py", "cmd": "x"}), patch=PATCH)
    assert v.flags == ["repro_missing"]


def test_repro_tied_to_issue_by_literal() -> None:
    issue = "Lexer should emit an `UNSIGNED_INT` token for `unsigned int`."
    good = new_file(REPRO, ["def test_t():", "    assert kinds('unsigned int') == ['UNSIGNED_INT']"])
    bad = new_file(REPRO, ["def test_t():", "    assert kinds('[') == ['LBRACKET']"])
    assert verify_claim(issue=issue, claim=claim(), patch=good).flags == []
    assert verify_claim(issue=issue, claim=claim(), patch=bad).flags == ["repro_not_tied_to_issue"]


def test_open_risks_contradiction_needs_high_confidence() -> None:
    risks = ["Edge case X is not covered by tests"]
    assert "claim_contradicts_open_risks" in verify_claim(issue=ISSUE, claim=claim(open_risks=risks), patch=PATCH).flags
    low = verify_claim(issue=ISSUE, claim=claim(open_risks=risks, confidence=0.6), patch=PATCH)
    assert low.flags == [] and low.verdict == "pass"
    benign = verify_claim(issue=ISSUE, claim=claim(open_risks=["Docstring could be clearer"]), patch=PATCH)
    assert benign.flags == []


def test_claimed_failure_is_fail() -> None:
    assert verify_claim(issue=ISSUE, claim=claim(tests_passed=False), patch=PATCH).verdict == "fail"


def test_issue_underspecified_heuristic() -> None:
    assert issue_is_underspecified("ToDO: add support for `translator` frontend in `lexer`, see `crosstl/lexer.py`")
    assert not issue_is_underspecified(ISSUE)
    assert not issue_is_underspecified("Add `Lexer.peek()` so callers can look ahead")
    assert not issue_is_underspecified("```python\nfoo()\n```")
    assert not issue_is_underspecified("导入空文件时报错，应该返回空列表")


def test_asserted_literals_only_from_asserts() -> None:
    src = "x = 'IGNORED'\ndef test():\n    assert any(t == 'KEEP' for t in xs), 'msg here'\n"
    assert asserted_literals(src) == {"KEEP"}  # assert 的提示信息不是期望值
    assert asserted_literals("assert f('BROKEN', 'FINE')(") == {"BROKEN", "FINE"}  # 语法错误时退回正则
