"""发布说明从 CHANGELOG 取整节（release.yml）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("release_notes", ROOT / "packaging" / "release_notes.py")
assert spec and spec.loader
rn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rn)

CL = """# 更新记录

## [0.3.0-preview] - 2026-10-11

### 新增
- 核心打包

## [0.2.1] - 2026-10-10

- 旧
"""


def test_section_strips_v_and_stops_at_next_version() -> None:
    assert rn.section(CL, "v0.3.0-preview") == "### 新增\n- 核心打包"
    assert rn.section(CL, "0.2.1") == "- 旧"
    assert rn.section(CL, "v9.9.9") is None


def test_repo_changelog_has_current_desktop_version() -> None:
    import json

    v = json.loads((ROOT / "apps" / "desktop" / "package.json").read_text(encoding="utf-8"))["version"]
    assert rn.section((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), v)
