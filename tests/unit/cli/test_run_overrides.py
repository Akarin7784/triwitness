"""桌面端设置 → `tw run` 本次任务覆盖（UI-21）：¥ 上限只能调低；权限模式走 session 层；勇士模式需交互 + 确认短语。"""

from __future__ import annotations

import pytest
import typer
from typer.testing import CliRunner

from triwitness.cli.main import _run_overrides, app
from triwitness.permissions.config import UNRESTRICTED_CONFIRM_PHRASE


def test_no_overrides() -> None:
    assert _run_overrides(None, None, None, interactive=True) == (None, None)


def test_max_cost_lower_only() -> None:
    budget, _ = _run_overrides(0.3, None, None, interactive=False)
    assert budget is not None and budget.max_cost_cny == 0.3 and budget.max_wall_seconds == 2700
    for bad in (0, -1, 1.5):
        with pytest.raises(typer.BadParameter):
            _run_overrides(bad, None, None, interactive=False)


def test_permission_mode_session_layer() -> None:
    _, s = _run_overrides(None, "plan", None, interactive=False)
    assert s is not None and s.mode == "plan" and s.unrestricted is None
    with pytest.raises(typer.BadParameter):
        _run_overrides(None, "god", None, interactive=True)


def test_unrestricted_needs_interactive_and_phrase() -> None:
    with pytest.raises(typer.BadParameter):
        _run_overrides(None, "unrestricted", UNRESTRICTED_CONFIRM_PHRASE, interactive=False)
    with pytest.raises(typer.BadParameter):
        _run_overrides(None, "unrestricted", None, interactive=True)
    with pytest.raises(typer.BadParameter):
        _run_overrides(None, None, UNRESTRICTED_CONFIRM_PHRASE, interactive=True)
    _, s = _run_overrides(None, "unrestricted", UNRESTRICTED_CONFIRM_PHRASE, interactive=True)
    assert s is not None and s.unrestricted is not None and s.unrestricted.valid() and s.unrestricted.scope == "task"
    _, s = _run_overrides(None, "unrestricted", "随便", interactive=True)
    assert s is not None and s.unrestricted is not None and not s.unrestricted.valid()  # load_policy 再拒


def test_cli_rejects_bad_cap(tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = CliRunner().invoke(app, ["run", "--repo", str(tmp_path), "--demo", "--max-cost", "9"])
    assert r.exit_code != 0
