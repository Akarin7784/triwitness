"""UI-19 / UI-21 桌面端调用的 CLI：doctor --json、sandbox install（必须确认）、permissions 规则编辑器。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from triwitness.cli.main import app
from triwitness.permissions.config import load_policy

R = CliRunner()


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    h = tmp_path / "home"
    monkeypatch.setenv("TW_HOME", str(h))
    return h


def _j(args: list[str]) -> tuple[int, dict]:  # type: ignore[type-arg]
    r = R.invoke(app, args)
    return r.exit_code, json.loads(r.stdout.splitlines()[0])


def test_doctor_json() -> None:
    code, d = _j(["doctor", "--json"])
    assert code == 0 and {"docker", "wsl", "winget", "recommended", "sandbox_ready"} <= d.keys()


def test_sandbox_install_needs_yes() -> None:
    r = R.invoke(app, ["sandbox", "install", "docker"])
    assert r.exit_code == 2
    code, plan = _j(["sandbox", "install", "wsl", "--plan"])
    assert code == 0 and plan["target"] == "wsl"
    assert R.invoke(app, ["sandbox", "install", "kernel", "--plan"]).exit_code != 0


def test_rules_crud_and_policy_picks_them_up(home: Path, tmp_path: Path) -> None:
    code, d = _j(["permissions", "validate", "--kind", "allow", "--rule", "Bash(npm test"])
    assert code == 2 and not d["ok"] and "语法" in d["error"]
    assert _j(["permissions", "add", "--kind", "allow", "--rule", "Bash(npm test)"])[0] == 0
    assert _j(["permissions", "add", "--kind", "deny", "--rule", "Read(./secrets/**)"])[0] == 0
    code, d = _j(["permissions", "add", "--kind", "allow", "--rule", "Bash(npm run lint)", "--replace",
                  "Bash(npm test)"])  # fmt: skip
    assert code == 0
    _, d = _j(["permissions", "list"])
    assert d["layers"]["user"]["allow"] == ["Bash(npm run lint)"] and d["layers"]["user"]["deny"]
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    pol = load_policy(repo, backend="none", interactive=True, home=home)
    assert any(r.raw == "Bash(npm run lint)" and r.kind == "allow" for r in pol.rules)
    assert _j(["permissions", "remove", "--kind", "deny", "--rule", "Read(./secrets/**)"])[1]["removed"]
    assert not _j(["permissions", "remove", "--kind", "deny", "--rule", "nope"])[1]["removed"]
    # 仓库本地层（审批卡“总是允许”写的那一层）
    assert _j(["permissions", "add", "--kind", "allow", "--rule", "Bash(make)", "--layer", "local", "--repo",
               str(repo)])[0] == 0  # fmt: skip
    _, d = _j(["permissions", "list", "--repo", str(repo)])
    assert d["layers"]["local"]["allow"] == ["Bash(make)"]
    assert "/.triwitness/permissions.local.yaml" in (repo / ".git/info/exclude").read_text()
    assert _j(["permissions", "add", "--kind", "allow", "--rule", "x", "--layer", "local"])[0] == 2
