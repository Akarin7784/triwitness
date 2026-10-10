"""最小事件发射器（tw-events/1）。完整的 TrajectoryRecorder 在 W1-24。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from triwitness.core.events import Payload, TrajectoryEvent, make_event
from triwitness.core.models import Role


class EventEmitter:
    def __init__(
        self,
        task_id: str,
        run_id: str,
        *,
        path: Path | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.task_id = task_id
        self.run_id = run_id
        self.path = path
        self.clock = clock
        self.events: list[TrajectoryEvent] = []

    def emit(self, payload: Payload, role: Role | None = None) -> TrajectoryEvent:
        ev = make_event(seq=len(self.events), ts=self.clock(), task_id=self.task_id, run_id=self.run_id, role=role,
                        payload=payload)  # fmt: skip
        self.events.append(ev)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(ev.to_json_line() + "\n")
        return ev

    def kinds(self) -> list[str]:
        return [e.kind for e in self.events]
