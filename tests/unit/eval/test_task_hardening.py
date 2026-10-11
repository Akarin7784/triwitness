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


# —— 预签名链接与密钥（2026-10-12 secret scanning 告警 #1）——
# 测试里的假密钥都在运行时拼出来，避免源码本身触发仓库扫描 / GitHub secret scanning。
_AWS_ID = "AS" + "IA" + "QVFQEXAMPLE0" + "ABCD"
_AMZ = "X-Amz-"


def test_redact_presigned_urls_keep_host_and_path() -> None:
    s3 = (
        "https://bucket.s3.us-east-1.amazonaws.com/a/junit.xml?"
        f"{_AMZ}Algorithm=AWS4-HMAC-SHA256&{_AMZ}Credential={_AWS_ID}%2F20250101%2Fus-east-1%2Fs3&{_AMZ}Signature=bf17"
    )
    gcs = "https://storage.googleapis.com/b/o.txt?" + "X-Goog" + "-Signature=abcd&X-Goog-Expires=60"
    sas = "https://acct.blob.core.windows.net/c/f.zip?sv=2021&se=2026-01-01&sp=r&" + "sig=AbCd%2Bef"
    tok = "https://example.com/dl/file?" + "token=abc123&x=1"
    plain = "https://example.com/search?q=angle&page=2"
    text = f"see [junit]({s3}) and {gcs}, {sas} or {tok}; docs {plain}"
    out, removed = sanitize_instruction(text)
    assert removed.count("signed_url") == 4
    assert _AWS_ID not in out and "Signature" not in out and "sig=" not in out and "token=" not in out
    assert "https://bucket.s3.us-east-1.amazonaws.com/a/junit.xml?[已移除签名链接])" in out  # markdown 括号保留
    assert plain in out  # 普通查询串不动


def test_redact_bare_secrets_records_kind_not_value() -> None:
    from triwitness.eval.task_hardening import SECRET_MARK, redact_secrets

    ghp = "gh" + "p_" + "a1B2" * 9
    pat = "github" + "_pat_" + "11ABCDEFG0" + "x" * 30
    xox = "xo" + "xb-" + "1234567890-abcdef"
    sk = "s" + "k-" + "Z" * 32
    pem_body = "\n".join(["MIIEvQIBADANBgkqhkiG9w0BAQEFAASC"] * 3)
    pem = "-----BEGIN " + f"PRIVATE KEY-----\n{pem_body}\n-----END " + "PRIVATE KEY-----"
    text = f"id {_AWS_ID} gh {ghp} pat {pat} slack {xox} key {sk}\n{pem}\nok"
    out, removed = redact_secrets(text)
    assert sorted(removed) == sorted(
        ["aws_access_key_id", "github_token", "github_token", "slack_token", "openai_style_key", "private_key"]
    )
    for v in (_AWS_ID, ghp, pat, xox, sk, "MIIEvQ"):
        assert v not in out and v not in removed
    assert out.count(SECRET_MARK) == 6 and out.endswith("\nok")
    # 只提到格式、没有密钥正文的文档不算；普通单词里的 sk- 也不算
    doc = 'feed {"private_key": "...-----BEGIN ' + 'PRIVATE KEY-----... in PEM"} and sk-construction'
    assert redact_secrets(doc) == (doc, [])


def test_audit_flags_secret_in_instruction(tmp_path: Path) -> None:
    d = tmp_path / "ext" / anon_task_id("x__z-2")
    d.mkdir(parents=True)
    (d / "instruction.md").write_text(f"see https://s3.amazonaws.com/b/k?{_AMZ}Credential={_AWS_ID}\n")
    codes = {f.code: f for f in audit_task(d)}
    assert codes["instruction_secret"].level == "error"
    assert _AWS_ID not in codes["instruction_secret"].message
    assert "instruction_links" not in codes  # 签名链接不重复算成上游链接


def test_committed_task_instructions_have_no_secrets() -> None:
    from triwitness.eval.task_hardening import redact_secrets

    hits = [
        (p.relative_to(ROOT).as_posix(), r)
        for p in sorted((ROOT / "evals" / "tasks").glob("*/*/instruction.md"))
        if not p.parent.parent.name.startswith("_")
        for r in [redact_secrets(p.read_text(encoding="utf-8"))[1]]
        if r
    ]
    assert hits == []
