"""W2-10：run_tests 的 mode（full / related / selected）、rerun_failed、junit 解析与只保留失败段。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from triwitness.harness.testing import FakeSandbox, call
from triwitness.sandbox.base import ExecResult
from triwitness.tools import ToolContext, ToolRegistry, default_tools
from triwitness.tools.pytest_report import nodeid, parse_junit, related_tests, render_failures

JUNIT = "/workspace/.tw/junit.xml"
XML_FAIL = b"""<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="0" failures="1"
skipped="1" tests="4"><testcase classname="tests.test_a" name="test_ok" file="tests/test_a.py"/>
<testcase classname="tests.test_a.TestX" name="test_bad[1]" file="tests/test_a.py"><failure message="assert 1 == 2">"""
XML_FAIL += b"x = 1\n" * 2000 + b"""E       assert 1 == 2
tests/test_a.py:9: AssertionError</failure></testcase>
<testcase classname="tests.test_b" name="test_skip" file="tests/test_b.py"><skipped message="s"/></testcase>
<testcase classname="tests.test_b" name="test_ok2" file="tests/test_b.py"/></testsuite></testsuites>"""
NOISE = "collected 4 items\n" + "tests/test_a.py ....\n" * 3000 + "FAILED tests/test_a.py::TestX::test_bad[1]\n"


def tool_ctx(sb: FakeSandbox, **kw: object) -> ToolContext:
    return ToolContext(sandbox=sb, test_command="python -m pytest -q", **kw)  # type: ignore[arg-type]


def sandbox(xml: bytes | None, code: int = 1, files: dict[str, str] | None = None) -> FakeSandbox:
    def handler(cmd: str, sb: FakeSandbox) -> ExecResult:
        if cmd.startswith("find "):  # collect_files 在沙箱里用 find 列文件
            out = "\n".join(sorted(k for k in sb.files if not k.startswith("/")))
            return ExecResult(exit_code=0, stdout=out, stderr="", duration_ms=1, timed_out=False)
        if xml is not None:
            sb.files[sb._key(JUNIT)] = xml
        return ExecResult(exit_code=code, stdout=NOISE, stderr="", duration_ms=5, timed_out=False)

    return FakeSandbox(files=files or {}, exec_handler=handler)


async def run(c: ToolContext, **args: object):  # type: ignore[no-untyped-def]
    result, _ = await ToolRegistry(default_tools()).dispatch(call("run_tests", **args), c)
    return result


async def test_failure_only_output_from_junit() -> None:
    sb = sandbox(XML_FAIL)
    r = await run(tool_ctx(sb))
    assert not r.ok and r.data["failures"] == ["tests/test_a.py::TestX::test_bad[1]"]
    assert r.data["passed"] == 2 and r.data["skipped"] == 1 and r.data["failed"] == 1
    assert "FAILED tests/test_a.py::TestX::test_bad[1]" in r.content and "assert 1 == 2" in r.content
    assert "tests/test_a.py ...." not in r.content  # 通过用例的噪音不进上下文
    assert len(r.content) < 2500  # 栈被截到头尾
    assert sb.commands[-1] == f"python -m pytest -q --junitxml={JUNIT}"


async def test_rerun_failed_uses_last_failures() -> None:
    sb = sandbox(XML_FAIL)
    c = tool_ctx(sb)
    await run(c)
    r = await run(c, rerun_failed=True)
    assert sb.commands[-1] == f"python -m pytest -q 'tests/test_a.py::TestX::test_bad[1]' --junitxml={JUNIT}"
    assert "只重跑上次失败的 1 个用例" in r.content


async def test_selected_and_full_modes() -> None:
    sb = sandbox(XML_FAIL)
    c = tool_ctx(sb)
    await run(c, mode="selected", selector="-k bad")
    assert sb.commands[-1] == f"python -m pytest -q -k bad --junitxml={JUNIT}"
    await run(c)
    assert sb.commands[-1] == f"python -m pytest -q --junitxml={JUNIT}"


async def test_related_mode_infers_tests_from_changes() -> None:
    files = {"src/pkg/slug.py": "x = 1\n", "tests/test_slug.py": "", "tests/test_other.py": ""}
    sb = sandbox(XML_FAIL, files=files)
    c = tool_ctx(sb)
    r = await run(c, mode="related")
    assert "还没有改动" in r.content and sb.commands[-1] == f"python -m pytest -q --junitxml={JUNIT}"
    await sb.write_file("src/pkg/slug.py", b"x = 2\n")
    r = await run(c, mode="related")
    assert sb.commands[-1] == f"python -m pytest -q tests/test_slug.py --junitxml={JUNIT}"  # junit 不算改动
    assert "相关测试 1 个文件" in r.content


async def test_non_pytest_or_missing_report_falls_back_to_raw_output() -> None:
    sb = sandbox(None, code=0)
    r = await run(tool_ctx(sb))
    assert r.ok and "collected 4 items" in r.content
    c = ToolContext(sandbox=sandbox(None, code=0), test_command="make test")  # type: ignore[arg-type]
    await run(c)
    assert c.sandbox.commands[-1] == "make test"  # type: ignore[attr-defined]


def test_parse_junit_rejects_entities_and_garbage() -> None:
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><testsuite><testcase name="&a;"/></testsuite>'
    assert parse_junit(bomb) is None
    assert parse_junit(b"not xml") is None and parse_junit(b"") is None


def test_related_tests_naming_rules() -> None:
    files = ["src/a/slug.py", "tests/test_slug.py", "tests/slug_test.py", "tests/test_x.py", "pkg/__init__.py",
             "tests/test_pkg.py"]  # fmt: skip
    assert related_tests(["src/a/slug.py"], files) == ["tests/slug_test.py", "tests/test_slug.py"]
    assert related_tests(["tests/test_x.py"], files) == ["tests/test_x.py"]
    assert related_tests(["pkg/__init__.py"], files) == ["tests/test_pkg.py"]
    assert related_tests(["README.md"], files) == []


def test_nodeid_mapping_matches_real_pytest(tmp_path: Path) -> None:
    """真实 pytest 生成的 junit → 节点 id 与 pytest 自己的写法一致（rerun_failed 依赖这一点）。"""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_m.py").write_text(
        "import pytest\nclass TestK:\n    @pytest.mark.parametrize('v', [1, 2])\n    def test_p(self, v):\n"
        "        assert v == 1\ndef test_top():\n    assert False, 'boom'\n"
    )
    xml = tmp_path / "j.xml"
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", "tests"],
                   cwd=tmp_path, capture_output=True)  # fmt: skip
    rep = parse_junit(xml.read_bytes())
    assert rep is not None and rep.tests == 3 and rep.failed == 2
    assert sorted(f.nodeid for f in rep.failures) == ["tests/test_m.py::TestK::test_p[2]", "tests/test_m.py::test_top"]
    assert "boom" in render_failures(rep)
    assert nodeid("tests.test_m.TestK", "test_p[2]", None) == "tests/test_m.py::TestK::test_p[2]"
