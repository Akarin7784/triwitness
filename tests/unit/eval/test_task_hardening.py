"""W5-12 防作弊加固：匿名 ID、Issue 清洗、任务审计、沙箱屏蔽代码托管站。"""

from __future__ import annotations

from pathlib import Path

import pytest

from triwitness.eval.task_hardening import (
    CODE_HOSTS,
    GIT_ENV,
    HOOKS_OFF,
    anon_task_id,
    audit_task,
    sanitize_instruction,
)

ROOT = Path(__file__).resolve().parents[3]


def test_anon_id_stable_and_opaque() -> None:
    a = anon_task_id("owner__repo-123")
    assert a == anon_task_id("owner__repo-123")
    assert a != anon_task_id("owner__repo-124")
    assert a.startswith("t-") and len(a) == 12
    assert "repo" not in a and "123" not in a


def test_sanitize_removes_commit_links_and_shas_keeps_issue_links() -> None:
    sha = "0123456789abcdef0123456789abcdef01234567"
    text = (
        "Broken since https://github.com/o/r/commit/abc123 and https://github.com/o/r/pull/42/files.\n"
        f"Bisected to {sha}. See https://github.com/o/r/issues/7 and https://gitlab.com/g/p/-/merge_requests/3"
    )
    out, removed = sanitize_instruction(text)
    assert "commit/abc123" not in out and "pull/42" not in out and sha not in out and "merge_requests" not in out
    assert "https://github.com/o/r/issues/7" in out  # 指向 Issue 的链接不是答案
    assert len(removed) == 4


def test_audit_flags(tmp_path: Path) -> None:
    good = tmp_path / "dev" / anon_task_id("x__y-1")
    (good / "environment").mkdir(parents=True)
    (good / "task.toml").write_text('[metadata]\nbase_commit = "deadbeefcafe0000"\n[environment]\n')
    (good / "instruction.md").write_text("It crashes.\n")
    (good / "environment" / "Dockerfile").write_text(f"FROM python:3.12\nRUN apt-get install git\n{HOOKS_OFF}\n")
    assert audit_task(good) == []

    bad = tmp_path / "dev" / "swe-y-1"
    (bad / "environment").mkdir(parents=True)
    (bad / "task.toml").write_text(
        '[metadata]\nbase_commit = "deadbeefcafe0000"\n[environment]\nnetwork_mode = "public"\n'
    )
    (bad / "instruction.md").write_text("Regressed at deadbeefcafe, see https://github.com/x/y/commit/1\n")
    (bad / "environment" / "Dockerfile").write_text("FROM python\nRUN git clone https://x/y\nCOPY tests /t\n")
    codes = {(f.level, f.code) for f in audit_task(bad)}
    assert codes == {
        ("warn", "id_not_anonymized"),
        ("warn", "instruction_links"),
        ("error", "instruction_base_sha"),
        ("error", "git_clone"),
        ("error", "hidden_in_image"),
        ("warn", "git_hooks"),
        ("error", "network"),
    }


def test_existing_tasks_have_no_audit_errors() -> None:
    """旧任务只报告 warn（不改隐藏测试）；不能有 error（git 历史 / 测试进镜像 / 出网）。"""
    dirs = [d for d in (ROOT / "evals" / "tasks").glob("*/*") if (d / "task.toml").exists()]
    if not dirs:
        pytest.skip("没有任务目录")
    errors = [(d.name, f.code) for d in dirs for f in audit_task(d) if f.level == "error"]
    assert errors == []


def test_importer_harden_dockerfile() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("import_swe_rebench", ROOT / "scripts" / "import_swe_rebench.py")
    assert spec and spec.loader
    imp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imp)

    row = {
        "instance_id": "own__proj-77",
        "repo": "own/proj",
        "base_commit": "a" * 40,
        "_harden": True,
        "_install": "pip install -e .",
    }
    df = imp.dockerfile(row, "3.12")
    assert HOOKS_OFF in df and "rm -rf /workspace/repo/.git" in df
    assert HOOKS_OFF not in imp.dockerfile(dict(row, _harden=False), "3.12")


def test_docker_backend_blocks_code_hosts_only_with_network() -> None:
    from triwitness.sandbox.base import SandboxSpec
    from triwitness.sandbox.docker import container_kwargs

    assert "github.com" in CODE_HOSTS and "pypi.org" not in CODE_HOSTS
    assert GIT_ENV["GIT_ALLOW_PROTOCOL"] == "file"
    on = container_kwargs(SandboxSpec(network="host", block_code_hosts=True))
    assert on["network_mode"] == "bridge" and on["extra_hosts"]["github.com"] == "0.0.0.0"
    assert "extra_hosts" not in container_kwargs(SandboxSpec(network="none", block_code_hosts=True))
    assert "extra_hosts" not in container_kwargs(SandboxSpec(network="host"))
