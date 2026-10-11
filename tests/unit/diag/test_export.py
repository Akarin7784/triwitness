from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from triwitness.diag.export import export_diagnostics

RUN = "r_01M4NC1X0VD310ZTH6WGQB8MJ2"
KEY = "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2"
GH = "github_pat_" + "Z" * 30
ODD = "not-a-known-shape-secret-value-123"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    h = tmp_path / "home"
    rd = h / "runs" / RUN
    (rd / "resume").mkdir(parents=True)
    (rd / "tree").mkdir()
    (rd / "tree" / "big.py").write_text("x = 1\n")
    (rd / "trajectory.jsonl").write_text(
        json.dumps({"tool": "bash", "out": f"export DEEPSEEK_API_KEY={KEY}; token {GH}; odd {ODD}"}) + "\n"
    )
    (rd / "summary.json").write_text(json.dumps({"status": "done", "repo": str(Path.home() / "src" / "verses")}))
    (rd / "owner.pid").write_text("123")
    (rd / "blob.bin").write_bytes(b"\x00\x01\x02")
    (rd / "huge.log").write_text("y" * (2 * 1024 * 1024 + 10))
    (h / "logs").mkdir()
    (h / "logs" / "core.log").write_text(f"Authorization: Bearer {ODD}\n")
    (h / "llm-cache").mkdir()
    (h / "llm-cache" / "c.json").write_text("{}")
    monkeypatch.setenv("TW_HOME", str(h))
    return h


def _read(p: Path) -> dict[str, str]:
    with zipfile.ZipFile(p) as zf:
        return {n: zf.read(n).decode() for n in zf.namelist()}


def test_export_collects_and_redacts(home: Path) -> None:
    env = {"DEEPSEEK_API_KEY": KEY, "TW_ODD_SECRET": ODD, "TW_HOME": str(home)}
    res = export_diagnostics(home, env=env)
    files = _read(res.path)
    assert res.runs == [RUN]
    assert {"system.json", "usage.json", "MANIFEST.json", "logs/core.log", f"runs/{RUN}/trajectory.jsonl"} <= set(files)
    blob = "\n".join(files.values())
    for secret in (KEY, GH, ODD):
        assert secret not in blob
    assert str(Path.home()) not in files[f"runs/{RUN}/summary.json"]
    assert not any("/tree/" in n or "llm-cache" in n or n.endswith(".pid") for n in files)
    man = json.loads(files["MANIFEST.json"])
    assert any("blob.bin" in s for s in man["skipped"]) and any("huge.log" in s for s in man["skipped"])
    sysinfo = json.loads(files["system.json"])
    assert sysinfo["secrets_configured"]["DEEPSEEK_API_KEY"] is True
    assert sysinfo["env"]["TW_ODD_SECRET"] == "***"
    assert res.redactions >= 2


def test_export_rejects_bad_run_ids(home: Path) -> None:
    with pytest.raises(ValueError):
        export_diagnostics(home, run_ids=["../etc"], env={})
    with pytest.raises(FileNotFoundError):
        export_diagnostics(home, run_ids=["r_0000000000"], env={})


def test_cli_diag_export_json(home: Path, tmp_path: Path) -> None:
    from triwitness.cli.main import app

    out = tmp_path / "d.zip"
    r = CliRunner().invoke(app, ["diag", "export", "--run", RUN, "--out", str(out), "--json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["ok"] and data["path"] == str(out) and out.is_file() and data["runs"] == [RUN]
    bad = CliRunner().invoke(app, ["diag", "export", "--run", "nope"])
    assert bad.exit_code == 2 and json.loads(bad.output)["ok"] is False
