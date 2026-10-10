"""W2-07 / W2-08：notes、git、grep 上下文 / 正则建议、list_files 遵守 .gitignore、repo_map。"""

from __future__ import annotations

import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from triwitness.harness.testing import FakeSandbox, call
from triwitness.sandbox.base import ExecResult, SandboxSpec
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.tools import ToolContext, ToolRegistry, ToolResult, default_tools
from triwitness.tools.files import GitIgnore
from triwitness.tools.repo_map import build_map, pagerank, parse_symbols
from triwitness.tools.workspace import replace_section

ROOT = Path(__file__).resolve().parents[3]
ALL = ["bash", "edit_file", "finish", "git", "grep", "list_files", "notes", "read_file", "repo_map", "run_tests",
       "write_file"]  # fmt: skip


def reg() -> ToolRegistry:
    return ToolRegistry(default_tools(names=ALL))


async def run(c: ToolContext, name: str, **args: object) -> ToolResult:
    result, _ = await reg().dispatch(call(name, **args), c)
    return result


def test_schemas_valid_and_described() -> None:
    import jsonschema

    for s in reg().schemas():
        jsonschema.Draft202012Validator.check_schema(s["function"]["parameters"])
        assert s["function"]["description"].strip()


# ---------------------------------------------------------------- notes
async def test_notes_read_append_replace_section() -> None:
    c = ToolContext(sandbox=FakeSandbox(), tw_dir="/workspace/.tw")
    assert "空" in (await run(c, "notes", op="read")).content
    assert (await run(c, "notes", op="append", text="## 计划\n1. 读代码")).ok
    assert (await run(c, "notes", op="replace_section", section="失败尝试", text="- edit 失败：缩进")).ok
    assert (await run(c, "notes", op="replace_section", section="计划", text="1. 改 slug.py\n2. 跑测试")).ok
    doc = (await run(c, "notes", op="read")).content
    assert doc.index("## 计划") < doc.index("## 失败尝试")
    assert "2. 跑测试" in doc and "1. 读代码" not in doc and "缩进" in doc
    bad = await run(c, "notes", op="append")
    assert not bad.ok and bad.error_code == "bad_args"
    big = await run(c, "notes", op="append", text="x" * 25_000)
    assert big.error_code == "too_long"


def test_replace_section_edges() -> None:
    assert replace_section("", "A", "a") == "## A\na\n"
    doc = "## A\nold\n\n## B\nb\n"
    assert replace_section(doc, "A", "new") == "## A\nnew\n\n## B\nb\n"
    assert replace_section(doc, "## B", "bb") == "## A\nold\n\n## B\nbb\n"


# ---------------------------------------------------------------- git
async def test_git_diff_status_on_any_backend() -> None:
    sb = FakeSandbox({"a.py": "x = 1\n", "b.py": "y = 1\n"})
    c = ToolContext(sandbox=sb)
    assert (await run(c, "git", op="status")).content == "（没有改动）"
    await sb.write_file("a.py", b"x = 2\n")
    await sb.write_file("new.py", b"z\n")
    st = await run(c, "git", op="status")
    assert st.content.splitlines() == ["M a.py", "A new.py"]
    d = await run(c, "git", op="diff", path="a.py")
    assert "+x = 2" in d.content and "new.py" not in d.content


async def test_git_log_without_git_gives_hint() -> None:
    def no_git(cmd: str, s: FakeSandbox) -> ExecResult:
        return ExecResult(exit_code=127, stdout="", stderr="git: command not found", duration_ms=1, timed_out=False)

    c = ToolContext(sandbox=FakeSandbox(exec_handler=no_git))
    r = await run(c, "git", op="log")
    assert r.error_code == "no_git" and "op=diff" in r.content
    bad = await run(c, "git", op="show", rev="--output=/etc/passwd")
    assert bad.error_code == "bad_args"


# ---------------------------------------------------------------- 宿主后端：gitignore / grep 上下文 / git log
@pytest.fixture
async def repo_ctx(tmp_path: Path) -> AsyncIterator[ToolContext]:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "build").mkdir()
    (repo / "src" / "a.py").write_text("one\ntwo\nTARGET here\nfour\nfive\nTARGET again\n", encoding="utf-8")
    (repo / "src" / "gen.log").write_text("TARGET in log\n", encoding="utf-8")
    (repo / "build" / "out.py").write_text("TARGET built\n", encoding="utf-8")
    (repo / "keep.log").write_text("x\n", encoding="utf-8")
    (repo / ".gitignore").write_text("# 产物\nbuild/\n*.log\n!keep.log\n", encoding="utf-8")
    for cmd in (["init", "-q", "-b", "main"], ["config", "core.autocrlf", "false"], ["add", "-A"],
                ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"]):  # fmt: skip
        subprocess.run(["git", "-C", str(repo), *cmd], check=True, capture_output=True)
    (repo / "build" / "out.py").write_text("TARGET built\n", encoding="utf-8")  # 被忽略，不进提交
    sb = await LocalSandboxBackend(home=tmp_path / "h").create(SandboxSpec(repo=repo, run_id="t1"))
    yield ToolContext(sandbox=sb)
    await sb.finish("discard")  # type: ignore[attr-defined]


async def test_list_files_respects_gitignore(repo_ctx: ToolContext) -> None:
    files = (await run(repo_ctx, "list_files")).content.splitlines()
    assert "src/a.py" in files and "keep.log" in files
    assert not any(f.startswith("build/") or f == "src/gen.log" for f in files)


async def test_grep_context_max_and_gitignore(repo_ctx: ToolContext) -> None:
    g = await run(repo_ctx, "grep", pattern="TARGET")
    assert g.content.splitlines() == ["src/a.py:3:TARGET here", "src/a.py:6:TARGET again"]
    g1 = await run(repo_ctx, "grep", pattern="TARGET", context=1)
    assert g1.content.splitlines() == ["src/a.py-2-two", "src/a.py:3:TARGET here", "src/a.py-4-four",
                                       "src/a.py-5-five", "src/a.py:6:TARGET again"]  # fmt: skip
    g0 = await run(repo_ctx, "grep", pattern="one|five", context=0)
    assert g0.content.splitlines() == ["src/a.py:1:one", "src/a.py:5:five"]
    g3 = await run(repo_ctx, "grep", pattern="^one$|^TARGET again$", context=1)
    assert "--" in g3.content.splitlines()  # 不相邻的块用 -- 分隔
    g2 = await run(repo_ctx, "grep", pattern="TARGET", max_matches=1)
    assert g2.content.splitlines()[0] == "src/a.py:3:TARGET here" and "超过 1 处" in g2.content
    bad = await run(repo_ctx, "grep", pattern="foo(")
    assert bad.error_code == "bad_regex" and "foo\\(" in bad.content


async def test_git_log_and_show_on_host(repo_ctx: ToolContext) -> None:
    log = await run(repo_ctx, "git", op="log", n=5)
    assert log.ok and "init" in log.content
    show = await run(repo_ctx, "git", op="show", rev="HEAD", path="src/a.py")
    assert show.ok and "TARGET here" in show.content


def test_gitignore_rules() -> None:
    g = GitIgnore("*.pyc\n/dist\ndocs/_build/\n!important.pyc\n")
    assert g.ignored("a/b.pyc") and not g.ignored("important.pyc")
    assert g.ignored("dist/x.js") and not g.ignored("src/dist/x.js")
    assert g.ignored("docs/_build/index.html") and not g.ignored("docs/_build")
    assert not GitIgnore().ignored("anything")


# ---------------------------------------------------------------- repo_map
def test_repo_map_ranks_referenced_core_first() -> None:
    core = parse_symbols(
        "pkg/core.py", "class Engine:\n    def run(self, job):\n        pass\n\ndef helper(x):\n    pass\n"
    )
    users = [parse_symbols(f"pkg/u{i}.py", "from pkg.core import Engine\nEngine().run(1)\n") for i in range(3)]
    lonely = parse_symbols("pkg/lonely.py", "def lonely_fn(a, *args, k=1, **kw):\n    pass\n")
    text = build_map([lonely, *users, core], max_tokens=500)
    assert text.splitlines()[0] == "pkg/core.py:"
    assert "  class Engine:" in text and "    def run(self, job)" in text
    assert "def lonely_fn(a, *args, k, **kw)" in text
    focused = build_map([lonely, *users, core], focus=["pkg/lonely.py"], max_tokens=500)
    assert focused.splitlines()[0] == "pkg/lonely.py:"
    mentioned = build_map([lonely, *users, core], mentions={"lonely_fn"}, max_tokens=500)
    assert mentioned.splitlines()[0] == "pkg/lonely.py:"


def test_pagerank_sums_to_one_and_handles_empty() -> None:
    from collections import Counter

    r = pagerank(["a", "b", "c"], {"a": Counter({"b": 1}), "c": Counter({"b": 2})}, {})
    assert abs(sum(r.values()) - 1) < 1e-6 and max(r, key=r.__getitem__) == "b"
    assert pagerank([], {}, {}) == {}


def test_repo_map_respects_token_budget_and_bad_syntax() -> None:
    files = [parse_symbols(f"m{i}.py", "\n".join(f"def f{i}_{j}(a, b): pass" for j in range(40))) for i in range(20)]
    files.append(parse_symbols("broken.py", "def (:"))
    text = build_map(files, max_tokens=200)
    assert len(text) <= 200 * 3 and text.endswith("…")
    assert build_map(files, max_tokens=200) == text  # 确定性


async def test_repo_map_on_dev_task_repo(tmp_path: Path) -> None:
    """DoD（W2-08）：在一个 dev 任务仓库上输出 ≤ 2000 token 的摘要。"""
    src = ROOT / "evals" / "tasks" / "dev" / "slugify-edges" / "environment" / "repo"
    files: dict[str, str | bytes] = {p.relative_to(src).as_posix(): p.read_bytes() for p in src.rglob("*.py")}

    def find(cmd: str, s: FakeSandbox) -> ExecResult:
        return ExecResult(exit_code=0, stdout="\n".join(sorted(s.files)), stderr="", duration_ms=1, timed_out=False)

    c = ToolContext(sandbox=FakeSandbox(files, exec_handler=find))
    r = await run(c, "repo_map", mentions=["slugify"])
    assert r.ok and r.data and r.data["files"] >= 2
    assert r.content.splitlines()[0] == "textkit/slug.py:" and "def slugify(" in r.content
    assert len(r.content) / 3 <= 2000
