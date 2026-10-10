"""权限审计日志（spec 006 §10）：每次判定一行 JSONL，按月分文件；所有模式（含 unrestricted）都记录，不可关闭。"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from triwitness.core.redact import redact_text

BJ = ZoneInfo("Asia/Shanghai")
ACTION_MAX = 2000


class AuditLog:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._lock = threading.Lock()

    def path_for(self, ts: datetime) -> Path:
        return self.directory / f"permissions-{ts.astimezone(BJ):%Y%m}.jsonl"

    def record(self, entry: dict[str, Any], *, now: datetime | None = None) -> Path:
        ts = now or datetime.now(BJ)
        row = {"ts": ts.astimezone(BJ).isoformat(timespec="milliseconds"), **entry}
        if isinstance(row.get("action"), str):
            row["action"] = redact_text(row["action"], max_len=ACTION_MAX)
        if isinstance(row.get("reason"), str):
            row["reason"] = redact_text(row["reason"], max_len=500)
        path = self.path_for(ts)
        line = json.dumps(row, ensure_ascii=False, sort_keys=True)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
        return path
