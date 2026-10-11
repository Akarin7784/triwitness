"""scripts/windows/*.ps1 在 Windows PowerShell 5.1 下能解析（BOM + CRLF；语法错误在 CI 里就暴露）。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = sorted((ROOT / "scripts" / "windows").glob("*.ps1"))


@pytest.mark.parametrize("script", SCRIPTS, ids=[p.name for p in SCRIPTS])
def test_ps1_has_bom_and_crlf(script: Path) -> None:
    raw = script.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "PowerShell 5.1 需要 UTF-8 BOM 才能正确读中文"
    assert b"\n" not in raw.replace(b"\r\n", b""), "应为 CRLF 行尾"


@pytest.mark.skipif(sys.platform != "win32" or not shutil.which("powershell"), reason="需要 Windows PowerShell")
@pytest.mark.parametrize("script", SCRIPTS, ids=[p.name for p in SCRIPTS])
def test_ps1_parses(script: Path) -> None:
    ps = (
        "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{script}', [ref]$null, [ref]$e) | Out-Null; "
        "if ($e.Count) { $e | ForEach-Object { $_.ToString() }; exit 1 }"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
