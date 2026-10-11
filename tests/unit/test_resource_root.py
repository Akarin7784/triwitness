"""打包后（PyInstaller，sys.frozen）资源根指向解包目录，configs/ 跟着走；源码运行时是仓库根。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from triwitness.config import config_dir, resource_root


def test_source_tree_root() -> None:
    assert (resource_root() / "configs" / "models.yaml").exists()


def test_frozen_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TW_CONFIG_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resource_root() == tmp_path
    assert config_dir() == tmp_path / "configs"
