"""W3-11：每个因子、等级边界 14/15、39/40、69/70、硬下限（阻断 / 无沙箱复跑 / 无复现）。"""

from __future__ import annotations

import pytest

from triwitness.verify.anticheat import check
from triwitness.verify.risk import RiskInputs, RiskPolicy, assess, level_of, load_policy, public_api_changes
from triwitness.verify.testing import modify, new_file

FIX = modify("src/calc.py", ["    return a - b"], ["    return a + b"])
POLICY = load_policy()


def factor_codes(**kw: object) -> list[str]:
    return [f.code for f in assess(RiskInputs(**kw)).factors]  # type: ignore[arg-type]


@pytest.mark.parametrize(("score", "level"), [(0, "L0"), (14, "L0"), (15, "L1"), (39, "L1"), (40, "L2"), (69, "L2"),
                                              (70, "L3"), (100, "L3")])  # fmt: skip
def test_level_boundaries(score: int, level: str) -> None:
    assert level_of(score, POLICY) == level


def test_small_clean_fix_is_l0_with_no_factors() -> None:
    r = assess(RiskInputs(patch=FIX))
    assert (r.score, r.level, r.factors) == (0, "L0", [])


def test_each_factor() -> None:
    big = new_file("src/big.py", [f"x{i} = {i}" for i in range(250)])
    huge = new_file("src/big.py", [f"x{i} = {i}" for i in range(600)])
    assert factor_codes(patch=big) == ["lines_over_200"]
    assert factor_codes(patch=huge) == ["lines_over_500"]
    assert factor_codes(patch=modify("src/auth/session.py", ["a"], ["b"])) == ["sensitive_path"]
    assert factor_codes(patch=modify("pyproject.toml", ["a"], ["b"])) == ["ci_build_deps"]
    t = modify("tests/test_calc.py", ["    assert x == 1"], ["    assert x == 2"])
    assert "existing_test_modified" in factor_codes(patch=t, anticheat=check(t))
    assert factor_codes(patch=FIX, coverage_changed=0.4) == ["low_coverage"]
    assert factor_codes(patch=FIX, coverage_changed=0.5) == []
    assert factor_codes(patch=FIX, coverage_changed=None) == []
    assert "repro_not_reproduced" in factor_codes(patch=FIX, repro_status="not_applicable")
    assert factor_codes(patch=FIX, verdict="inconclusive") == ["verifier_uncertain"]
    assert factor_codes(patch=FIX, verifier_confidence=0.59) == ["verifier_uncertain"]
    assert factor_codes(patch=FIX, verifier_confidence=0.6) == []
    assert factor_codes(patch=FIX, review_major_open=1) == ["review_major_open"]
    api = modify("src/calc.py", ["def add(a, b):"], ["def add(a, b, c=0):"])
    assert factor_codes(patch=api) == ["public_api_changed"]
    assert factor_codes(patch=FIX, bandit_medium_high=2) == ["security_scan"]
    assert factor_codes(patch=FIX, claim_flags=["repro_not_tied_to_issue"]) == ["claim_audit"]


def test_public_api_ignores_private_tests_and_body_changes() -> None:
    assert public_api_changes(modify("src/calc.py", ["def _helper(a):"], ["def _helper(a, b):"])) == []
    assert public_api_changes(modify("tests/test_calc.py", ["def test_a():"], ["def test_a(tmp_path):"])) == []
    assert public_api_changes(modify("src/calc.py", ["def add(a, b):"], ["def add(a, b):"])) == []
    assert public_api_changes(modify("src/calc.py", ["class Calc:"], [])) == ["src/calc.py:Calc"]


def test_every_factor_writes_points_and_reason() -> None:
    r = assess(RiskInputs(patch=modify("src/auth/x.py", ["a"], ["b"]), verdict="inconclusive", review_major_open=1))
    assert r.score == 25 + 20 + 25 and r.level == "L3"
    assert all(f.points > 0 and f.detail for f in r.factors)


def test_floor_anticheat_block_forces_l3() -> None:
    p = modify("src/calc.py", [], ["if 'pytest' in sys.modules:", "    return 3"])  # 针对测试特判
    r = assess(RiskInputs(patch=p, anticheat=check(p)))
    assert r.level == "L3" and r.needs_human and r.factors[-1].code == "floor:anticheat_block"


def test_skip_alone_is_l2_review_not_l3() -> None:
    p = modify("tests/test_calc.py", [], ["@pytest.mark.skip"])
    r = assess(RiskInputs(patch=p, anticheat=check(p)))
    assert r.level == "L2" and not r.needs_human and any(f.code == "floor:anticheat_review" for f in r.factors)


def test_floor_anticheat_review_forces_l2() -> None:
    p = modify("conftest.py", [], ["x = 1"])
    r = assess(RiskInputs(patch=p, anticheat=check(p)))
    assert r.level == "L2" and any(f.code == "floor:anticheat_review" for f in r.factors)


def test_floor_clean_env_unverified_is_at_least_l2() -> None:
    r = assess(RiskInputs(patch=FIX, clean_env="unverified"))
    assert r.score == 0 and r.level == "L2"
    assert [f.code for f in r.factors] == ["floor:clean_env_unverified"]


def test_floor_not_reproduced_is_at_least_l1_and_floors_never_lower() -> None:
    assert assess(RiskInputs(patch=FIX, repro_status="not_applicable")).level == "L1"
    high = assess(RiskInputs(patch=modify("src/auth/x.py", ["a"], ["b"]), clean_env="unverified", review_major_open=1,
                             verdict="inconclusive"))  # fmt: skip
    assert high.level == "L3" and not any(f.code.startswith("floor:") for f in high.factors)


def test_policy_is_configurable() -> None:
    p = RiskPolicy.model_validate(POLICY.model_dump() | {"levels": {"L1": 5, "L2": 10, "L3": 20}})
    assert assess(RiskInputs(patch=FIX, coverage_changed=0.1), p).level == "L2"
