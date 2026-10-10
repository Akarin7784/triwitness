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
    assert t.tw.fail_to_pass == ["tests/test_parse.py::test_blank_line_skipped"]
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
        ('fail_to_pass = ["tests/test_parse.py::test_blank_line_skipped"]', "fail_to_pass = []", "fail_to_pass"),
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
