"""DeltaWriter：增量按时间 / 字数合并，换类型先落盘，脱敏，index 连续。"""

from __future__ import annotations

from pathlib import Path

from triwitness.harness.deltas import FLUSH_CHARS, DeltaWriter
from triwitness.telemetry.trajectory import TrajectoryRecorder


def test_coalesce_and_switch(tmp_path: Path) -> None:
    rec = TrajectoryRecorder("t", "r", run_dir=tmp_path)
    now = [0.0]
    w = DeltaWriter(rec, "executor", "c0", clock=lambda: now[0])
    for ch in "想一想":
        w("reasoning", ch)
    assert rec.next_seq == 0  # 还没到 50ms、也没到字数：先攒着
    w("content", "好")  # 换类型：先把推理写掉
    now[0] = 0.2
    w("content", "的")
    w("content", "x" * FLUSH_CHARS)
    w.flush()
    lines = (tmp_path / "trajectory.jsonl").read_text(encoding="utf-8").splitlines()
    import json

    ev = [json.loads(x) for x in lines]
    assert [e["kind"] for e in ev] == ["reasoning_delta", "model_delta", "model_delta"]
    assert [e["payload"]["index"] for e in ev] == [0, 1, 2]
    assert ev[0]["payload"]["text"] == "想一想" and ev[1]["payload"]["text"] == "好的"


def test_secrets_are_redacted(tmp_path: Path) -> None:
    rec = TrajectoryRecorder("t", "r", run_dir=tmp_path)
    w = DeltaWriter(rec, "executor", "c0")
    w("content", "key sk-abcdefghijklmnopqrstuvwxyz0123456789")
    w.flush()
    assert "sk-abcdefghijklmnop" not in (tmp_path / "trajectory.jsonl").read_text(encoding="utf-8")
