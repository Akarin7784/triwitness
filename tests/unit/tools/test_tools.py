"""spec 003 AC2–AC4、AC7 与各工具单测（W1-18～W1-20）。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from triwitness.harness.testing import FakeSandbox, call
from triwitness.sandbox.base import ExecResult, SandboxSpec
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.tools import ToolContext, ToolRegistry, default_tools
from triwitness.tools.shell import parse_pytest


def reg() -> ToolRegistry:
    return ToolRegistry(default_tools())


def ctx(sb: object = None, **kw: object) -> ToolContext:
    return ToolContext(sandbox=sb or FakeSandbox(), **kw)  # type: ignore[arg-type]


async def run(r: ToolRegistry, c: ToolContext, name: str, **args: object):  # type: ignore[no-untyped-def]
    result, _ = await r.dispatch(call(name, **args), c)
    return result


# ------------------------------------------------------------------ AC2 / AC3
def test_ac2_schemas_stable_and_valid() -> None:
    a = json.dumps(reg().schemas(), ensure_ascii=False, sort_keys=False)
    b = json.dumps(reg().schemas(), ensure_ascii=False, sort_keys=False)
    assert a == b
    schemas = reg().schemas()
    names = [s["function"]["name"] for s in schemas]
    assert names == sorted(names)
    assert set(names) == {"bash", "edit_file", "finish", "grep", "list_files", "read_file", "run_tests", "write_file"}
    for s in schemas:
        jsonschema.Draft202012Validator.check_schema(s["function"]["parameters"])
        assert s["function"]["description"]
        assert "title" not in json.dumps(s["function"]["parameters"])


def test_powershell_replaces_bash() -> None:
    names = ToolRegistry(default_tools(shell="powershell")).names
    assert "powershell" in names and "bash" not in names


async def test_ac3_bad_args_name_field_and_type() -> None:
    r = reg()
    res = await run(r, ctx(), "read_file", path=123, start_line="x")
    assert not res.ok and res.error_code == "bad_args"
    assert "path" in res.content and "string" in res.content
    assert "start_line" in res.content and "integer" in res.content
    res2, _ = await r.dispatch(call("read_file").model_copy(update={"arguments": "{bad"}), ctx())
    assert res2.error_code == "bad_args" and "JSON" in res2.content
    res3 = await run(r, ctx(), "nope")
    assert res3.error_code == "unknown_tool"
    res4 = await run(r, ctx(), "bash", command="ls", timeout_s=9999)
    assert res4.error_code == "bad_args" and "timeout_s" in res4.content


# ------------------------------------------------------------------ 文件工具
async def test_read_file_line_numbers_and_paging() -> None:
    sb = FakeSandbox({"big.py": "\n".join(f"line{i}" for i in range(1, 1001))})
    res = await run(reg(), ctx(sb), "read_file", path="big.py")
    assert res.ok
    assert res.content.splitlines()[0] == "     1\tline1"
    assert "   400\tline400" in res.content and "line401" not in res.content
    assert "start_line=401" in res.content
    res2 = await run(reg(), ctx(sb), "read_file", path="big.py", start_line=990, end_line=2000)
    assert "  1000\tline1000" in res2.content and "继续" not in res2.content
    assert (await run(reg(), ctx(sb), "read_file", path="missing.py")).error_code == "not_found"
    sb.files["bin"] = b"\x00\x01"
    assert (await run(reg(), ctx(sb), "read_file", path="bin")).error_code == "binary"


async def test_write_file_only_new() -> None:
    sb = FakeSandbox({"a.py": "x"})
    res = await run(reg(), ctx(sb), "write_file", path="a.py", content="y")
    assert not res.ok and "edit_file" in res.content
    res2 = await run(reg(), ctx(sb), "write_file", path="b.py", content="y\n")
    assert res2.ok and sb.files["b.py"] == b"y\n"


async def test_ac4_edit_file_hints() -> None:
    sb = FakeSandbox({"m.py": "def f():\n    return 1\n\ndef g():\n    return 1\n"})
    r = reg()
    zero = await run(r, ctx(sb), "edit_file", path="m.py", old_str="def  f():", new_str="x")
    assert not zero.ok and zero.error_code == "no_match"
    assert "0 次" in zero.content and "第 1 行" in zero.content  # 给出最相近的行
    two = await run(r, ctx(sb), "edit_file", path="m.py", old_str="    return 1", new_str="    return 2")
    assert not two.ok and two.error_code == "multiple_matches"
    assert "2 次" in two.content and "第 2, 5 行" in two.content
    ok = await run(
        r, ctx(sb), "edit_file", path="m.py", old_str="def g():\n    return 1", new_str="def g():\n    return 2"
    )
    assert ok.ok and sb.files["m.py"].decode().endswith("return 2\n")


# ------------------------------------------------------------------ bash / run_tests / finish
async def test_bash_rejects_interactive() -> None:
    sb = FakeSandbox()
    for cmd in ["vim a.py", "git log | less", "top", "python", "git rebase -i HEAD~2"]:
        res = await run(reg(), ctx(sb), "bash", command=cmd)
        assert res.error_code == "interactive", cmd
    assert sb.commands == []
    res = await run(reg(), ctx(sb), "bash", command="python -c 'print(1)'")
    assert res.ok


async def test_bash_reports_exit_and_timeout() -> None:
    def handler(cmd: str, sb: FakeSandbox) -> ExecResult:
        if "slow" in cmd:
            return ExecResult(exit_code=124, stdout="", stderr="", duration_ms=1000, timed_out=True)
        return ExecResult(exit_code=2, stdout="out", stderr="err", duration_ms=1, timed_out=False)

    sb = FakeSandbox(exec_handler=handler)
    res = await run(reg(), ctx(sb), "bash", command="false")
    assert not res.ok and res.exit_code == 2 and "out" in res.content and "[stderr]" in res.content
    slow = await run(reg(), ctx(sb), "bash", command="slow", timeout_s=1)
    assert slow.error_code == "timeout" and "超时" in slow.content


PYTEST_FAIL = """
tests/test_a.py .F                                                     [100%]
FAILED tests/test_a.py::test_two - assert 1 == 2
========================= 1 failed, 1 passed in 0.02s =========================
"""
PYTEST_OK = "========================= 2 passed, 1 skipped in 0.02s ========================="


def test_parse_pytest() -> None:
    p = parse_pytest(PYTEST_FAIL)
    assert (p["passed"], p["failed"]) == (1, 1)
    assert p["failures"] == ["tests/test_a.py::test_two"]
    assert parse_pytest(PYTEST_OK)["skipped"] == 1


def _fake_tests(results: list[tuple[int, str]]):  # type: ignore[no-untyped-def]
    it = iter(results)

    def handler(cmd: str, sb: FakeSandbox) -> ExecResult:
        code, out = next(it)
        return ExecResult(exit_code=code, stdout=out, stderr="", duration_ms=5, timed_out=False)

    return handler


FINISH = {
    "summary": "修好了",
    "changes": [{"path": "a.py", "kind": "modified"}],
    "tests_passed": True,
    "confidence": 0.8,
}


async def test_ac7_finish_rejected_after_failed_tests() -> None:
    sb = FakeSandbox(exec_handler=_fake_tests([(1, PYTEST_FAIL), (0, PYTEST_OK)]))
    c = ctx(sb, test_command="pytest -q")
    r = reg()
    t1 = await run(r, c, "run_tests", selector="tests/test_a.py")
    assert not t1.ok and t1.data and t1.data["failed"] == 1
    assert sb.commands[-1] == "pytest -q tests/test_a.py"
    bad = await run(r, c, "finish", **FINISH)
    assert not bad.ok and bad.error_code == "tests_failed" and "test_two" in bad.content
    honest = await run(r, c, "finish", **{**FINISH, "tests_passed": False})
    assert honest.ok
    t2 = await run(r, c, "run_tests")
    assert t2.ok
    good = await run(r, c, "finish", **FINISH)
    assert good.ok and good.data and good.data["finish_report"]["summary"] == "修好了"


async def test_finish_missing_fields_named() -> None:
    res = await run(reg(), ctx(), "finish", summary="x")
    assert res.error_code == "bad_args"
    for f in ("changes", "tests_passed", "confidence"):
        assert f in res.content


async def test_run_tests_without_command() -> None:
    assert (await run(reg(), ctx(), "run_tests")).error_code == "no_test_command"


async def test_internal_errors_wrapped() -> None:
    class Boom(FakeSandbox):
        async def read_file(self, path: str) -> bytes:
            raise RuntimeError("kaboom")

    res = await run(reg(), ctx(Boom()), "read_file", path="a")
    assert res.error_code == "internal" and "kaboom" in res.content


# ------------------------------------------------------------------ list_files / grep：none 后端（宿主）与 exec 路径
@pytest.fixture
async def local_ctx(tmp_path: Path):  # type: ignore[no-untyped-def]
    repo = tmp_path / "repo"
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "src" / "pkg" / "a.py").write_bytes(b"def alpha():\n    return 'TODO'\n")
    (repo / "src" / "b.txt").write_bytes(b"todo lower\n")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "x.js").write_text("TODO")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "core.autocrlf", "false"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"], check=True
    )
    sb = await LocalSandboxBackend(home=tmp_path / "h").create(SandboxSpec(repo=repo, run_id="t1"))
    yield ToolContext(sandbox=sb)
    await sb.finish("discard")  # type: ignore[attr-defined]


async def test_list_and_grep_host(local_ctx: ToolContext) -> None:
    r = reg()
    ls = await run(r, local_ctx, "list_files")
    assert "src/pkg/a.py" in ls.content and "node_modules" not in ls.content and ".git" not in ls.content
    ls2 = await run(r, local_ctx, "list_files", glob="*.py")
    assert ls2.content.strip() == "src/pkg/a.py"
    g = await run(r, local_ctx, "grep", pattern="TODO")
    assert g.content.strip() == "src/pkg/a.py:2:    return 'TODO'"
    g2 = await run(r, local_ctx, "grep", pattern="(?i)todo", glob="*.txt")
    assert g2.content.strip() == "src/b.txt:1:todo lower"
    bad = await run(r, local_ctx, "grep", pattern="(")
    assert bad.error_code == "bad_regex"
    out = await run(r, local_ctx, "list_files", path="../..")
    assert not out.ok


async def test_list_and_grep_exec_path() -> None:
    seen: list[str] = []

    def handler(cmd: str, sb: FakeSandbox) -> ExecResult:
        seen.append(cmd)
        out = "src/a.py\nsrc/b.txt\n" if cmd.startswith("find") else "src/a.py:3:hit\n"
        return ExecResult(exit_code=0, stdout=out, stderr="", duration_ms=1, timed_out=False)

    c = ctx(FakeSandbox(exec_handler=handler))
    ls = await run(reg(), c, "list_files", glob="*.py")
    assert ls.content == "src/a.py"
    g = await run(reg(), c, "grep", pattern="it's", path="src")
    assert g.content == "src/a.py:3:hit"
    assert "'it'\"'\"'s'" in seen[-1]  # 参数经 shlex.quote


async def test_edit_file_crlf() -> None:
    sb = FakeSandbox({"w.py": b"def f():\r\n    return 1\r\n"})
    ok = await run(
        reg(), ctx(sb), "edit_file", path="w.py", old_str="def f():\n    return 1", new_str="def f():\n    return 2"
    )
    assert ok.ok and sb.files["w.py"] == b"def f():\r\n    return 2\r\n"
