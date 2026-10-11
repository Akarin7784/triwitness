"""scripts/secret_scan.py：仓库级密钥扫描（CI 在 pytest 前也跑一次）。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("secret_scan", ROOT / "scripts" / "secret_scan.py")
assert spec and spec.loader
ss = importlib.util.module_from_spec(spec)
sys.modules["secret_scan"] = ss
spec.loader.exec_module(ss)

_AWS_ID = "AK" + "IA" + "Z" * 16


def test_scan_reports_line_and_kind_not_value(tmp_path: Path) -> None:
    (tmp_path / "evals").mkdir()
    (tmp_path / "evals" / "a.md").write_text(f"ok\nkey {_AWS_ID}\n", encoding="utf-8")
    (tmp_path / "evals" / "b.bin").write_bytes(b"\0" + _AWS_ID.encode())
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "fix.py").write_text(f'K = "{_AWS_ID}"\n', encoding="utf-8")
    allow = [("tests/*", "aws_access_key_id")]
    probs = ss.scan(["evals/a.md", "evals/b.bin", "tests/fix.py"], root=tmp_path, allow=allow)
    assert probs == ["evals/a.md:2: aws_access_key_id"]


def test_scan_multiline_private_key(tmp_path: Path) -> None:
    body = "\n".join(["MIIEvQIBADANBgkqhkiG9w0BAQEFAASC"] * 3)
    (tmp_path / "k.pem").write_text("x\n-----BEGIN " + f"RSA PRIVATE KEY-----\n{body}\n", encoding="utf-8")
    assert ss.scan(["k.pem"], root=tmp_path, allow=[]) == ["k.pem:2: private_key"]


def test_allowlist_never_covers_eval_data() -> None:
    for glob, _kind in ss.load_allow():
        assert not glob.startswith("evals"), glob


def test_repo_is_clean() -> None:
    assert ss.scan(ss.tracked()) == []
