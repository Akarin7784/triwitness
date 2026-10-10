"""把模型流式增量写成 model_delta / reasoning_delta 事件（UI-20）。

片段按约 50ms 或 48 字合并后再写，避免一字一事件；换类型（推理 → 正文）时先把手上的写掉。
"""

from __future__ import annotations

import time
from collections.abc import Callable

from triwitness.core.events import DELTA_MAX, ModelDeltaPayload, ReasoningDeltaPayload
from triwitness.core.models import Role
from triwitness.core.redact import redact_text
from triwitness.llm.stream import DeltaKind
from triwitness.telemetry.trajectory import TrajectoryRecorder

FLUSH_S = 0.05
FLUSH_CHARS = 48


class DeltaWriter:
    def __init__(
        self,
        rec: TrajectoryRecorder,
        role: Role,
        call_id: str,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.rec = rec
        self.role: Role = role
        self.call_id = call_id
        self.clock = clock
        self.kind: DeltaKind | None = None
        self.buf = ""
        self.index = 0
        self.last = clock()
        self.chars = {"reasoning": 0, "content": 0}

    def __call__(self, kind: DeltaKind, text: str) -> None:
        if not text:
            return
        if self.kind is not None and kind != self.kind:
            self.flush()
        self.kind = kind
        self.buf += text
        self.chars[kind] += len(text)
        if len(self.buf) >= FLUSH_CHARS or self.clock() - self.last >= FLUSH_S:
            self.flush()

    def flush(self) -> None:
        if not self.buf or self.kind is None:
            return
        text = redact_text(self.buf)
        while text:
            part, text = text[:DELTA_MAX], text[DELTA_MAX:]
            cls = ReasoningDeltaPayload if self.kind == "reasoning" else ModelDeltaPayload
            self.rec.emit(cls(call_id=self.call_id, index=self.index, text=part), role=self.role)
            self.index += 1
        self.buf = ""
        self.last = self.clock()
