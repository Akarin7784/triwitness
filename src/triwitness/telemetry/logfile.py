"""核心日志落盘（0.5.0）：`$TW_HOME/logs/core.log`（按大小轮转）+ stderr 同步写一份。

以前桌面端拉起的核心进程没有日志文件，卡住时只能看轨迹猜。现在：
- logging（WARNING 及以上 + triwitness.* 的 INFO）写 `core.log`，2 MB 一份，保留 5 份（core.1.log … core.5.log）；
- sys.stderr 照常输出，同时把内容逐行写进同一个日志；
- 写入前统一脱敏（redact_text），`tw diag export` 会把 logs/ 打进诊断包；
- 用 TW_LOG_DIR 可改目录，TW_NO_LOG_FILE=1 关闭（测试用）。日志写失败绝不影响任务。
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import TextIO

from triwitness.core.redact import redact_text

LOG_NAME = "core.log"
MAX_BYTES = 2 * 1024 * 1024
BACKUPS = 5
_FMT = "%(asctime)s %(levelname)s %(process)d %(name)s: %(message)s"
_installed: logging.Handler | None = None


class _RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_text(record.getMessage())
            record.args = None
        except Exception:
            pass
        return True


def _namer(name: str) -> str:
    # core.log.1 → core.1.log（诊断包按 .log 后缀当文本收）
    base, _, n = name.rpartition(".log.")
    return f"{base}.{n}.log" if n.isdigit() else name


class _StderrTee:
    """包住 sys.stderr：原样输出，同时按行写进日志（logger tw.stderr）。"""

    def __init__(self, inner: TextIO, logger: logging.Logger) -> None:
        self._inner = inner
        self._log = logger
        self._buf = ""

    def write(self, s: str) -> int:
        n = self._inner.write(s)
        try:
            self._buf += s
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                if line.strip():
                    self._log.info(line)
        except Exception:
            pass
        return n

    def flush(self) -> None:
        self._inner.flush()

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(self._inner, name)


def log_dir(home: Path | None = None) -> Path:
    env = os.environ.get("TW_LOG_DIR")
    if env:
        return Path(env)
    if home is None:
        from triwitness.config import tw_home

        home = tw_home()
    return home / "logs"


def setup_file_logging(home: Path | None = None, *, tee_stderr: bool = True) -> Path | None:
    """装一次；返回日志文件路径，关闭或失败返回 None。"""
    global _installed
    if os.environ.get("TW_NO_LOG_FILE") == "1":
        return None
    target = log_dir(home) / LOG_NAME
    if _installed is not None:
        return target
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        h = logging.handlers.RotatingFileHandler(target, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8",
                                                 delay=True)  # fmt: skip
    except OSError:
        return None
    h.namer = _namer
    h.setFormatter(logging.Formatter(_FMT))
    h.addFilter(_RedactFilter())
    h.setLevel(logging.INFO)
    root = logging.getLogger()
    root.addHandler(h)
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)
    # 第三方库只要 WARNING 以上，自家模块留 INFO
    for noisy in ("urllib3", "docker", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _installed = h
    if tee_stderr and not isinstance(sys.stderr, _StderrTee) and sys.stderr is not None:
        err = logging.getLogger("tw.stderr")
        err.propagate = False
        err.addHandler(h)
        err.setLevel(logging.INFO)
        sys.stderr = _StderrTee(sys.stderr, err)  # type: ignore[assignment]
    logging.getLogger("triwitness").info("core 启动 pid=%s argv=%s", os.getpid(), " ".join(sys.argv[1:])[:300])
    return target


__all__ = ["LOG_NAME", "log_dir", "setup_file_logging"]
