"""W3-08：静态检查（ruff / pyright / bandit / 密钥扫描），只把新增问题算失败；工具缺失 → skipped。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from triwitness.harness.testing import FakeSandbox
from triwitness.sandbox.base import ExecResult, SandboxSpec
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.verify.risk import RiskInputs, assess
from triwitness.verify.static_checks import changed_python, run_static_checks, scan_secrets
from triwitness.verify.testing import delete, make_patch, make_repo, modify, new_file

PATCH = modify("pkg/a.py", ["x = 1"], ["x = 2"]) + new_file("pkg/b.py", ["import os"]) + delete("pkg/c.py", ["y"])


def ok(out: object, code: int = 0) -> ExecResult:
    return ExecResult(exit_code=code, stdout=json.dumps(out), stderr="", duration_ms=1, timed_out=False)


MISSING = ExecResult(exit_code=1, stdout="", stderr="/usr/bin/python: No module named ruff", duration_ms=1,
                     timed_out=False)  # fmt: skip


def handler(ruff: list[dict], bandit: list[dict], pyright_missing: bool = True):  # type: ignore[no-untyped-def]
    def h(cmd: str, sb: FakeSandbox) -> ExecResult:
        if "ruff" in cmd:
            return ok(ruff)
        if "bandit" in cmd:
            return ok({"results": bandit}, 1 if bandit else 0)
        if pyright_missing:
            return ExecResult(exit_code=127, stdout="", stderr="pyright: command not found", duration_ms=1,
                              timed_out=False)  # fmt: skip
        return ok({"generalDiagnostics": [], "summary": {"errorCount": 0}})

    return h


R1 = {"filename": "/w/pkg/a.py", "code": "F401", "message": "unused"}
R2 = {"filename": "/w/pkg/b.py", "code": "F401", "message": "`os` imported but unused"}
B1 = {"filename": "pkg/b.py", "test_id": "B602", "issue_severity": "HIGH", "code": "subprocess(shell=True)"}
B_LOW = {"filename": "pkg/b.py", "test_id": "B101", "issue_severity": "LOW", "code": "assert x"}


def test_changed_python_skips_deleted() -> None:
    assert changed_python(PATCH) == ["pkg/a.py", "pkg/b.py"]


async def test_only_new_issues_fail_and_missing_tools_skip() -> None:
    patched = FakeSandbox(exec_handler=handler([R1, R2], [B1, B_LOW]))
    base = FakeSandbox(exec_handler=handler([R1], []))
    rep = await run_static_checks(patched, PATCH, base=base)
    assert rep.checks == {"ruff": "fail", "pyright": "skipped", "bandit": "fail", "secrets": "pass"}
    assert "新增 1 条" in rep.details["ruff"] and "b.py:F401" in rep.details["ruff"]
    assert "不可用" in rep.details["pyright"] and rep.bandit_medium_high == 1
    assert all("pkg/b.py" not in c for c in base.commands)  # 新文件不在基线上跑


async def test_preexisting_issues_pass() -> None:
    same = handler([R1], [])
    rep = await run_static_checks(FakeSandbox(exec_handler=same), PATCH, base=FakeSandbox(exec_handler=same),
                                  tools=("ruff",))  # fmt: skip
    assert rep.checks["ruff"] == "pass" and "基线已有 1 条" in rep.details["ruff"]


async def test_tool_missing_and_no_python_changes() -> None:
    rep = await run_static_checks(FakeSandbox(exec_handler=lambda c, s: MISSING), PATCH, tools=("ruff",))
    assert rep.checks["ruff"] == "skipped"
    rep2 = await run_static_checks(FakeSandbox(), new_file("README.md", ["hi"]))
    assert rep2.checks == {"ruff": "skipped", "pyright": "skipped", "bandit": "skipped", "secrets": "pass"}


def test_secret_scan_and_risk_floor() -> None:
    key = "sk-" + "a1B2" * 6
    patch = new_file("app/config.py", [f'OPENAI = "{key}"', 'API_TOKEN = "abcdefghijklmnop"', 'name = "token"',
                                       "-----BEGIN RSA PRIVATE KEY-----"])  # fmt: skip
    hits = scan_secrets(patch)
    assert [(h.line, h.kind) for h in hits] == [(1, "openai_style_key"), (2, "assigned_secret"), (4, "private_key")]
    assert scan_secrets(new_file("a.py", ['password = input("pw")', "TOKEN_URL = BASE + '/t'"])) == []
    r = assess(RiskInputs(patch=patch, secrets_found=len(hits)))
    assert r.level == "L3" and any(f.code == "floor:secrets" for f in r.factors)


async def test_real_ruff_in_local_sandbox(tmp_path: Path) -> None:
    """真实 ruff（开发环境里有）：基线已有的 F401 不算，新增的 F401 算。"""
    repo = make_repo(tmp_path, {"pkg/__init__.py": "", "pkg/a.py": "import sys\n"})
    patch = make_patch(repo, {"pkg/a.py": "import os\nimport sys\n"})
    be = LocalSandboxBackend(home=tmp_path / "home")
    py = f'"{Path(sys.executable).as_posix()}"'
    sb, base = await be.create(SandboxSpec(repo=repo)), await be.create(SandboxSpec(repo=repo))
    try:
        await sb.write_file("pkg/a.py", b"import os\nimport sys\n")
        rep = await run_static_checks(sb, patch, base=base, python=py, tools=("ruff",))
    finally:
        await sb.close()
        await base.close()
    assert rep.checks["ruff"] == "fail", rep.details
    assert "新增 1 条" in rep.details["ruff"] and "os" in rep.details["ruff"]
