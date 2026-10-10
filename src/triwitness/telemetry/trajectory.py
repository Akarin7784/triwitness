"""TrajectoryRecorder 与 Trajectory.load（spec 005 §5.1/5.2，W1-24）。

- 事件 = UI↔core 契约 `tw-events/1`：追加写 `trajectory.jsonl`，每条立即 flush（可选 fsync），seq 单调；
- payload 的 `role_hint` 缺省按事件角色补齐，`display` 一律先脱敏、截到 200 字；
- 完整请求 / 响应写到 `artifacts/<seq>-request.json`、`<seq>-response.json`；工具原文 `artifacts/<seq>-output.txt`，
  回给模型的工具消息 `artifacts/<seq>-tool.json`。所有产物写盘前脱敏；
- 没有 run_dir 时只在内存里记录（单测、评测前的干跑）。
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from triwitness.core.events import DISPLAY_MAX, Payload, TrajectoryEvent, make_event, parse_event_line
from triwitness.core.models import Role
from triwitness.core.redact import redact_text
from triwitness.llm.types import Message

_HINTS = ("planner", "executor", "verifier", "reviewer")


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TrajectoryRecorder:
    def __init__(
        self,
        task_id: str,
        run_id: str,
        *,
        run_dir: Path | None = None,
        fsync: bool = False,
        clock: Callable[[], datetime] = _utc_now,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.task_id = task_id
        self.run_id = run_id
        self.run_dir = run_dir
        self.fsync = fsync
        self.clock = clock
        self.monotonic = monotonic
        self.events: list[TrajectoryEvent] = []
        self._seq = 0
        if run_dir is not None:
            run_dir.mkdir(parents=True, exist_ok=True)
            if self.path is not None and self.path.exists():  # 断点续跑：接着已有 seq 写
                self._seq = len(Trajectory.read_events(self.path))

    @property
    def path(self) -> Path | None:
        return self.run_dir / "trajectory.jsonl" if self.run_dir is not None else None

    @property
    def next_seq(self) -> int:
        return self._seq

    def emit(self, payload: Payload, role: Role | None = None) -> TrajectoryEvent:
        if payload.role_hint is None:
            payload.role_hint = role if role in _HINTS else "system"  # type: ignore[assignment]
        if payload.display:
            payload.display = redact_text(" ".join(payload.display.split()), max_len=DISPLAY_MAX)
        ev = make_event(seq=self._seq, ts=self.clock(), task_id=self.task_id, run_id=self.run_id, role=role,
                        payload=payload)  # fmt: skip
        self._seq += 1
        self.events.append(ev)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(ev.to_json_line() + "\n")
                f.flush()
                if self.fsync:
                    os.fsync(f.fileno())
        return ev

    def artifact(self, name: str, data: str | bytes | dict[str, Any] | list[Any]) -> str | None:
        """写一个脱敏后的产物，返回相对引用 `artifacts/<name>`；内存模式返回 None。"""
        if self.run_dir is None:
            return None
        if isinstance(data, bytes):
            text = data.decode("utf-8", errors="replace")
        elif isinstance(data, str):
            text = data
        else:
            text = json.dumps(data, ensure_ascii=False, indent=1)
        target = self.run_dir / "artifacts" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(redact_text(text), encoding="utf-8", newline="\n")
        return f"artifacts/{name}"

    def kinds(self) -> list[str]:
        return [e.kind for e in self.events]


@dataclass
class Trajectory:
    events: list[TrajectoryEvent]
    messages: list[Message] = field(default_factory=list)
    truncated_tail: bool = False

    @staticmethod
    def read_events(path: Path) -> list[TrajectoryEvent]:
        out: list[TrajectoryEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                out.append(parse_event_line(line))
            except ValueError:
                break  # 最后一行写到一半（进程被杀）：之前的都完整
        return out

    @classmethod
    def load(cls, path: Path) -> Trajectory:
        """读轨迹并重建消息历史：最后一次模型请求的消息 + 其响应 + 之后的工具消息。"""
        run_dir = path.parent
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        events = cls.read_events(path)
        messages: list[Message] = []
        last = max((i for i, e in enumerate(events) if e.kind == "model_call" and e.payload.get("request_ref")),
                   default=None)  # fmt: skip
        if last is not None:
            ev = events[last]
            req = json.loads((run_dir / ev.payload["request_ref"]).read_text(encoding="utf-8"))
            messages = [Message.model_validate(m) for m in req["messages"]]
            resp_ref = ev.payload.get("response_ref")
            if resp_ref and (run_dir / resp_ref).exists():
                resp = json.loads((run_dir / resp_ref).read_text(encoding="utf-8"))
                messages.append(Message.model_validate(resp["message"]))
            for e in events[last + 1 :]:
                ref = e.payload.get("message_ref") if e.kind == "tool_call" else None
                if ref and (run_dir / ref).exists():
                    messages.append(Message.model_validate_json((run_dir / ref).read_text(encoding="utf-8")))
        return cls(events=events, messages=messages, truncated_tail=len(lines) > len(events))


__all__ = ["Trajectory", "TrajectoryRecorder"]
