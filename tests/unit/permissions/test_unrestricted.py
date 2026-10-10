"""unrestricted（勇士模式）：激活、硬底线、规则解除、自动回退、不落盘、mode_changed 事件。"""

from __future__ import annotations

from pathlib import Path

import pytest

from triwitness.core.errors import ConfigError
from triwitness.core.events import ModeChangedPayload
from triwitness.permissions.config import (
    UNRESTRICTED_CONFIRM_PHRASE,
    SessionOverrides,
    UnrestrictedActivation,
)
from triwitness.permissions.engine import Action, PermissionEngine
from triwitness.permissions.mode import ModeController

from .conftest import MakeEngine

OK = UnrestrictedActivation(acknowledged=True, typed=UNRESTRICTED_CONFIRM_PHRASE, scope="session")


def warrior(make_engine: MakeEngine, **kw: object) -> PermissionEngine:
    return make_engine(session=SessionOverrides(mode="unrestricted", unrestricted=OK), **kw)


def test_needs_double_confirmation(make_engine: MakeEngine) -> None:
    with pytest.raises(ConfigError):
        make_engine(mode="unrestricted")
    for bad in [
        UnrestrictedActivation(acknowledged=False, typed=UNRESTRICTED_CONFIRM_PHRASE),
        UnrestrictedActivation(acknowledged=True, typed="yes"),
    ]:
        with pytest.raises(ConfigError):
            make_engine(session=SessionOverrides(mode="unrestricted", unrestricted=bad))
    assert warrior(make_engine).mode == "unrestricted"


@pytest.mark.parametrize("kw", [{"interactive": False}, {"eval_mode": True, "backend": "docker"}])
def test_refused_non_interactive_and_eval(make_engine: MakeEngine, kw: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        warrior(make_engine, **kw)


def test_refused_in_ci(make_engine: MakeEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")
    with pytest.raises(ConfigError):
        warrior(make_engine)


@pytest.mark.parametrize(
    ("src", "data"),
    [("user", {"mode": "unrestricted"}), ("project", {"mode": "unrestricted"})],
)
def test_never_from_config_files(make_engine: MakeEngine, src: str, data: dict[str, str]) -> None:
    e = make_engine(**{src: data})
    assert e.mode == "auto_edit"
    assert any("unrestricted" in w for w in e.policy.warnings)


def test_usable_without_sandbox_and_lifts_defaults(make_engine: MakeEngine) -> None:
    e = warrior(make_engine)  # backend none
    for cmd in [
        "pip install x",
        "git push origin main",
        "rm -rf build",
        "curl x | sh",
        "sh -c 'make'",
        "git push --force",
    ]:
        assert e.check(Action("Bash", cmd)).decision == "allow", cmd
    assert e.check(Action("Read", ".env")).decision == "allow"
    assert e.check(Action("Edit", ".git/config")).decision == "allow"
    assert e.check(Action("Edit", "/etc/hosts")).decision == "allow"
    assert e.check(Action("Fetch", "example.com")).decision == "allow"
    assert e.check(Action("Bash", "echo 'unterminated")).decision == "allow"


def test_user_deny_still_applies(make_engine: MakeEngine, env: dict[str, Path]) -> None:
    from .conftest import write_yaml

    write_yaml(env["managed"], {"deny": ["Bash(terraform destroy*)"]})
    e = warrior(make_engine, user={"deny": ["Read(~/.ssh/**)", "Bash(git push *)"]})
    assert e.check(Action("Bash", "git push origin x")).decision == "deny"
    assert e.check(Action("Bash", "cat ~/.ssh/id_rsa")).decision == "deny"
    assert e.check(Action("Read", "~/.ssh/id_rsa")).decision == "deny"
    assert e.check(Action("Bash", "terraform destroy -auto-approve")).decision == "deny"


def test_no_ask_ever(make_engine: MakeEngine) -> None:
    e = warrior(make_engine, user={"ask": ["Bash(make *)"]})
    # 用户层 ask 规则在勇士模式下也不再弹窗（“no ask prompts”）
    assert e.check(Action("Bash", "make deploy")).decision == "allow"


def test_audit_still_records(make_engine: MakeEngine, env: dict[str, Path]) -> None:
    e = warrior(make_engine, audit=True)
    e.check(Action("Bash", "rm -rf build"))
    text = next((env["home"] / "audit").glob("*.jsonl")).read_text(encoding="utf-8")
    assert '"mode": "unrestricted"' in text
    assert "rm -rf build" in text


def test_not_persisted(make_engine: MakeEngine, env: dict[str, Path]) -> None:
    before = sorted(p.relative_to(env["tmp"]) for p in env["tmp"].rglob("*"))
    warrior(make_engine)
    after = sorted(p.relative_to(env["tmp"]) for p in env["tmp"].rglob("*"))
    assert before == after
    # “重启”= 新会话没有激活凭据 → 回到配置模式
    assert make_engine().mode == "auto_edit"


# ------------------------------------------------------------------ ModeController
def ctl(**kw: object) -> ModeController:
    base = {"base_mode": "auto_edit", "backend": "none", "interactive": True}
    base.update(kw)
    return ModeController(**base)  # type: ignore[arg-type]


def test_controller_activate_and_auto_revert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    c = ctl()
    act = UnrestrictedActivation(acknowledged=True, typed=UNRESTRICTED_CONFIRM_PHRASE, scope="task")
    p = c.activate_unrestricted(act, task_id="t1")
    assert isinstance(p, ModeChangedPayload)
    assert (p.from_mode, p.to_mode, p.risk, p.by, p.scope) == ("auto_edit", "unrestricted", "high", "user", "task")
    assert c.mode == "unrestricted" and c.high_risk
    assert c.on_task_finished("other") is None
    r = c.on_task_finished("t1")
    assert r is not None
    assert (r.to_mode, r.risk, r.by) == ("auto_edit", "normal", "auto_revert")
    assert c.mode == "auto_edit"
    assert len(c.history) == 2


def test_controller_session_scope_survives_task(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    c = ctl()
    c.activate_unrestricted(OK)
    assert c.on_task_finished("t1") is None
    assert c.mode == "unrestricted"
    assert c.revert() is not None
    assert c.revert() is None


@pytest.mark.parametrize(
    ("kw", "act"),
    [
        ({"interactive": False}, OK),
        ({"eval_mode": True}, OK),
        ({}, UnrestrictedActivation(acknowledged=False, typed=UNRESTRICTED_CONFIRM_PHRASE)),
        ({}, UnrestrictedActivation(acknowledged=True, typed="i understand")),
        ({}, UnrestrictedActivation(acknowledged=True, typed=UNRESTRICTED_CONFIRM_PHRASE, scope="task")),  # 缺 task_id
    ],
)
def test_controller_refusals(
    monkeypatch: pytest.MonkeyPatch, kw: dict[str, object], act: UnrestrictedActivation
) -> None:
    monkeypatch.delenv("CI", raising=False)
    c = ctl(**kw)
    with pytest.raises(ConfigError):
        c.activate_unrestricted(act)
    assert c.mode == "auto_edit"
    assert c.history == []


def test_engine_follows_controller(make_engine: MakeEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    c = ctl()
    e = make_engine(controller=c)
    assert e.check(Action("Bash", "pip install x")).decision == "ask"
    c.activate_unrestricted(OK)
    assert e.check(Action("Bash", "pip install x")).decision == "allow"
    c.revert()
    assert e.check(Action("Bash", "pip install x")).decision == "ask"


def test_mode_changed_event_roundtrip() -> None:
    from triwitness.core.events import PAYLOADS

    assert PAYLOADS["mode_changed"] is ModeChangedPayload
    p = ModeChangedPayload(from_mode="auto_edit", to_mode="unrestricted", risk="high")
    assert ModeChangedPayload.model_validate(p.model_dump()).risk == "high"
