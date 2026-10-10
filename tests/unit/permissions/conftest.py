from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from triwitness.permissions.audit import AuditLog
from triwitness.permissions.config import SessionOverrides, load_policy
from triwitness.permissions.engine import PermissionEngine

MakeEngine = Callable[..., PermissionEngine]


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.delenv("CI", raising=False)
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    home = tmp_path / "twhome"
    home.mkdir()
    return {"repo": repo, "home": home, "managed": tmp_path / "managed.yaml", "tmp": tmp_path}


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


@pytest.fixture
def make_engine(env: dict[str, Path]) -> MakeEngine:
    def _make(
        *,
        backend: str = "none",
        interactive: bool = True,
        mode: str | None = None,
        user: dict[str, Any] | None = None,
        project: dict[str, Any] | None = None,
        session: SessionOverrides | None = None,
        eval_mode: bool = False,
        audit: bool = False,
        **kw: Any,
    ) -> PermissionEngine:
        if user is not None:
            write_yaml(env["home"] / "permissions.yaml", user)
        if project is not None:
            write_yaml(env["repo"] / ".triwitness" / "permissions.yaml", project)
        sess = session or SessionOverrides()
        if mode is not None:
            sess.mode = mode  # type: ignore[assignment]
        pol = load_policy(
            env["repo"],
            backend=backend,
            interactive=interactive,
            eval_mode=eval_mode,
            session=sess,
            home=env["home"],
            managed_path=env["managed"],
        )
        kw.setdefault("windows", False)
        kw.setdefault("workspace", str(env["repo"]))
        kw.setdefault("home", "/home/eva")
        return PermissionEngine(pol, audit=AuditLog(env["home"] / "audit") if audit else None, **kw)

    return _make
