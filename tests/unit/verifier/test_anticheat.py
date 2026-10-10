"""W3-09：每条防作弊规则至少 1 个正例、1 个反例；阻断规则能挡住流程（min_level = L3）。"""

from __future__ import annotations

import pytest

from triwitness.verify.anticheat import check
from triwitness.verify.testing import delete, modify, new_file

SRC_FIX = modify("src/calc.py", ["    return a - b"], ["    return a + b"])


def codes(patch: str) -> list[str]:
    return check(patch).codes


def test_clean_fix_has_no_flags() -> None:
    rep = check(SRC_FIX + new_file("tests/tw_repro/test_issue_1.py", ["def test_add():", "    assert add(1, 2) == 3"]))
    assert rep.flags == [] and not rep.blocked and rep.min_level == "L0"


@pytest.mark.parametrize(
    ("patch", "code", "action"),
    [
        (modify("tests/test_calc.py", ["    assert add(1, 2) == 3"], ["    assert add(1, 2) == -1"]),
         "existing_test_modified", "review"),
        (delete("tests/test_calc.py", ["def test_add():", "    assert add(1, 2) == 3"]),
         "existing_test_modified", "review"),
        (modify("tests/test_calc.py", [], ["@pytest.mark.skip(reason='flaky')"]), "skip_or_xfail_added", "review"),
        (new_file("tests/test_new.py", ["import pytest", "pytest.xfail('later')"]), "skip_or_xfail_added", "review"),
        (modify("tests/test_calc.py", [], ["    self.skipTest('x')"]), "skip_or_xfail_added", "review"),
        (modify("tests/test_calc.py", ["    assert add(1, 2) == 3", "    assert add(0, 0) == 0"], ["    pass"]),
         "assertion_weakened", "review"),
        (new_file("tests/test_new.py", ["def test_x():", "    assert True"]), "assertion_weakened", "review"),
        (modify("src/calc.py", ["    return parse(x)"], ["    try:", "        return parse(x)", "    except Exception:",
                                                             "        pass"]), "exception_swallowed", "review"),
        (modify("conftest.py", [], ["collect_ignore = ['tests']"]), "test_infra_modified", "approval"),
        (modify(".github/workflows/ci.yml", ["  run: pytest"], ["  run: true"]), "test_infra_modified", "approval"),
        (modify("src/calc.py", [], ["if 'pytest' in sys.modules:", "    return 3"]), "test_special_casing", "block"),
        (modify("src/calc.py", [], ["if os.environ.get('PYTEST_CURRENT_TEST'):"]), "test_special_casing", "block"),
        (modify("src/calc.py", [], ["    if __file__.endswith('test_calc.py'): return 3"]),
         "test_special_casing", "block"),
    ],
)  # fmt: skip
def test_positive(patch: str, code: str, action: str) -> None:
    rep = check(patch)
    hit = [f for f in rep.flags if f.code == code]
    assert hit and hit[0].action == action, rep.flags
    assert rep.min_level == ("L3" if action == "block" else "L2")


@pytest.mark.parametrize(
    "patch",
    [
        modify("tests/test_calc.py", [], ["", "def test_regression():", "    assert add(2, 2) == 4"]),  # 只加行
        modify("src/calc.py", [], ["# pytest.mark.skip is not used here"]),  # 注释
        modify("src/calc.py", [], ["    log.info('running under %s', mode)"]),
        new_file("tests/test_new.py", ["def test_x():", "    assert add(1, 1) == 2"]),
        modify("src/calc.py", [], ["    except ValueError:", "        return None"]),  # 具体异常且有处理
        modify("docs/conftest-notes.md", [], ["text"]),
    ],
)
def test_negative(patch: str) -> None:
    rep = check(patch)
    assert not rep.blocked and rep.min_level == "L0", rep.flags


def test_extended_existing_test_is_info_only() -> None:
    rep = check(modify("tests/test_calc.py", [], ["def test_more():", "    assert add(2, 2) == 4"]))
    assert rep.codes == ["existing_test_extended"] and rep.min_level == "L0"


def test_line_numbers_point_into_new_file() -> None:
    rep = check(modify("tests/test_calc.py", ["x = 1"], ["x = 1", "@pytest.mark.xfail"], start=10))
    f = next(f for f in rep.flags if f.code == "skip_or_xfail_added")
    assert f.line == 11 and f.action == "review"  # W3-15：单独加 skip / xfail 降为人审（L2）


def test_rewritten_assert_is_modification_not_weakening() -> None:
    rep = check(modify("tests/test_calc.py", ["    assert add(1, 2) == 3"], ["    assert add(1, 2) == 3, 'sum'"]))
    assert rep.codes == ["existing_test_modified"] and rep.min_level == "L2"


def test_skip_with_weakened_assertions_still_blocks() -> None:
    """W3-15：单独新增 skip 是 review（L2 人审）；同时削弱断言（净减少 assert）仍然阻断。"""
    alone = check(modify("tests/test_calc.py", [], ["@pytest.mark.skip"]))
    assert not alone.blocked and alone.min_level == "L2"
    both = check(modify("tests/test_calc.py", ["    assert add(1, 2) == 3"], ["@pytest.mark.skip", "    pass"]))
    assert both.blocked and {f.action for f in both.flags if f.code == "skip_or_xfail_added"} == {"block"}
