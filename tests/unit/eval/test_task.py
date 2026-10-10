"""spec 004 任务格式（W1-26）：Harbor task.toml 1.x + [tw] 扩展的解析与结构检查。"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from triwitness.cli.main import app
from triwitness.eval.task import TaskFormatError, context_hash, discover, load_task

ROOT = Path(__file__).resolve().parents[3]
DEV = ROOT / "evals" / "tasks" / "dev"
EXAMPLE = DEV / "csv-blank-line"


@pytest.fixture
def task_dir(tmp_path: Path) -> Path:
    d = tmp_path / "csv-blank-line"
    shutil.copytree(EXAMPLE, d)
    return d


def _edit(d: Path, old: str, new: str) -> None:
    p = d / "task.toml"
    text = p.read_text(encoding="utf-8")
    assert old in text
    p.write_text(text.replace(old, new), encoding="utf-8")


def test_example_parses() -> None:
    t = load_task(EXAMPLE)
    assert t.id == "csv-blank-line"
    assert t.config.schema_version == "1.3"
    assert t.config.environment.network_mode == "no-network"
    assert t.tw.fail_to_pass[0] == "tests/test_parse_hidden.py::test_blank_line_skipped"
    assert t.meta.created_at == "2026-10-10"
    assert t.agent_timeout_sec == 900
    assert t.verifier_timeout_sec == 120
    assert "IndexError" in t.instruction
    assert t.image_tag().startswith("tw-task/csv-blank-line:")


def test_all_dev_tasks_valid() -> None:
    dirs = discover(DEV)
    assert dirs
    for d in dirs:
        load_task(d)


def test_unknown_harbor_fields_tolerated(task_dir: Path) -> None:
    _edit(task_dir, "[agent]\n", '[agent]\nuser = "agent"\nfuture_field = 1\n')
    _edit(task_dir, "[metadata]\n", '[metadata]\nauthor_note = "x"\n')
    load_task(task_dir)


@pytest.mark.parametrize(
    ("old", "new", "msg"),
    [
        ('schema_version = "1.3"', 'schema_version = "2.0"', "schema_version"),
        ('network_mode = "no-network"', 'network_mode = "public"', "no-network"),
        ('network_mode = "no-network"', 'network_mode = "none"', "network_mode"),
        ('name = "triwitness/csv-blank-line"', 'name = "triwitness/other"', "目录名"),
        ("fail_to_pass = [", "fail_to_pass = [] #", "fail_to_pass"),
        ("test_blank_line_skipped", "test_not_in_script", "test.sh 没有运行"),
        ('created_at = "2026-10-10"\n', "", "created_at"),
        ("max_cost_cny = 0.3", 'max_cost_cny = 0.3\nunknown = "x"', "unknown"),
    ],
)
def test_bad_fields(task_dir: Path, old: str, new: str, msg: str) -> None:
    _edit(task_dir, old, new)
    with pytest.raises(TaskFormatError, match=msg):
        load_task(task_dir)


@pytest.mark.parametrize(
    ("rel", "msg"),
    [("tests/test.sh", "test.sh"), ("solution/solve.sh", "solve.sh"), ("environment/Dockerfile", "Dockerfile")],
)
def test_missing_files(task_dir: Path, rel: str, msg: str) -> None:
    (task_dir / rel).unlink()
    with pytest.raises(TaskFormatError, match=msg):
        load_task(task_dir)


def test_reports_all_problems_at_once(task_dir: Path) -> None:
    (task_dir / "tests" / "test.sh").unlink()
    (task_dir / "instruction.md").write_text("  \n", encoding="utf-8")
    with pytest.raises(TaskFormatError) as e:
        load_task(task_dir)
    assert "test.sh" in str(e.value) and "instruction.md" in str(e.value)


def test_hidden_test_file_must_exist(task_dir: Path) -> None:
    (task_dir / "tests" / "test_parse_hidden.py").unlink()
    with pytest.raises(TaskFormatError, match=r"缺少 test_parse_hidden\.py"):
        load_task(task_dir)


def test_ac1_dev_suite_has_ten_distinct_tasks() -> None:
    tasks = [load_task(d) for d in discover(DEV)]
    assert len(tasks) == 10
    assert len({t.image_tag() for t in tasks}) == len(tasks)
    kinds = {t.meta.source for t in tasks}
    assert kinds == {"synthetic", "swe-rebench"}
    for t in tasks:
        assert t.tw.fail_to_pass and not set(t.tw.fail_to_pass) & set(t.tw.pass_to_pass)
        assert t.meta.license and t.meta.created_at
        hidden = [p for p in t.tests_dir.rglob("*") if p.is_file() and p.name != "test.sh"]
        assert hidden
        # 隐藏测试不进镜像构建上下文（同名文件内容也不同）
        env_files = {p.name: p.read_bytes() for p in t.environment_dir.rglob("*") if p.is_file()}
        assert all(env_files.get(h.name) != h.read_bytes() for h in hidden)
        if t.meta.source == "swe-rebench":
            assert t.meta.base_commit and t.meta.repo and "CC-BY-4.0" in (t.meta.license or "")
            assert t.meta.base_commit in (t.environment_dir / "Dockerfile").read_text(encoding="utf-8")


def test_bad_toml(task_dir: Path) -> None:
    (task_dir / "task.toml").write_text("[task\n", encoding="utf-8")
    with pytest.raises(TaskFormatError, match="TOML"):
        load_task(task_dir)


def test_docker_image_instead_of_dockerfile(task_dir: Path) -> None:
    (task_dir / "environment" / "Dockerfile").unlink()
    _edit(task_dir, "workdir =", 'docker_image = "python:3.12-slim"\nworkdir =')
    assert load_task(task_dir).image_tag() == "python:3.12-slim"


def test_context_hash_tracks_content_not_line_endings(task_dir: Path) -> None:
    env = task_dir / "environment"
    h = context_hash(env)
    f = env / "repo" / "csvkit_lite" / "parse.py"
    f.write_bytes(f.read_bytes().replace(b"\n", b"\r\n"))
    assert context_hash(env) == h
    f.write_text("x = 1\n", encoding="utf-8")
    assert context_hash(env) != h
    assert context_hash(EXAMPLE / "environment") == h


def test_cli_static(task_dir: Path) -> None:
    r = CliRunner().invoke(app, ["task", "validate", "--static", str(task_dir.parent)])
    assert r.exit_code == 0, r.output
    assert "✓ csv-blank-line" in r.output
    (task_dir / "tests" / "test.sh").unlink()
    r = CliRunner().invoke(app, ["task", "validate", "--static", str(task_dir)])
    assert r.exit_code == 1
    assert "✗ csv-blank-line" in r.output
