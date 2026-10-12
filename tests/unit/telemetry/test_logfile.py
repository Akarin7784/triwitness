"""0.5.0：核心日志落盘到 $TW_HOME/logs（轮转、脱敏）。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

from triwitness.telemetry import logfile


def test_setup_writes_rotating_redacted_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TW_NO_LOG_FILE", raising=False)
    monkeypatch.setattr(logfile, "_installed", None)
    old_err, root = sys.stderr, logging.getLogger()
    target = logfile.setup_file_logging(tmp_path, tee_stderr=True)
    try:
        assert target is not None and target == tmp_path / "logs" / "core.log"
        logging.getLogger("triwitness.x").warning("key=sk-%s", "a" * 40)
        print("stderr 一行", file=sys.stderr)
        h = logfile._installed
        assert h is not None
        h.flush()
        text = target.read_text(encoding="utf-8")
        assert "stderr 一行" in text and "core 启动" in text
        assert "a" * 40 not in text
        assert logfile._namer(str(tmp_path / "core.log.2")) == str(tmp_path / "core.2.log")
    finally:
        sys.stderr = old_err
        if logfile._installed is not None:
            root.removeHandler(logfile._installed)
            logging.getLogger("tw.stderr").removeHandler(logfile._installed)
            logfile._installed.close()
        monkeypatch.setattr(logfile, "_installed", None)


def test_disabled_by_env(tmp_path: Path) -> None:
    assert logfile.setup_file_logging(tmp_path) is None
