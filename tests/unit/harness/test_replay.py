"""spec 011 §3.2：事件日志重放的边界（对话轮的模型调用不算 Executor 历史；产物缺失退回旧方式）。"""

from __future__ import annotations

from pathlib import Path

from triwitness.core.events import ModelCallPayload, TaskStartedPayload
from triwitness.core.models import Usage
from triwitness.harness.replay import replay_history, seal
from triwitness.llm.types import Message, ToolCallSpec
from triwitness.telemetry.trajectory import TrajectoryRecorder


def model_call(rec: TrajectoryRecorder, msgs: list[Message], reply: Message, role: str = "executor") -> None:
    seq = rec.next_seq
    req = rec.artifact(
        f"{seq}-request.json", {"messages": [m.model_dump(mode="json", exclude_none=True) for m in msgs]}
    )
    resp = rec.artifact(f"{seq}-response.json", {"message": reply.model_dump(mode="json", exclude_none=True)})
    rec.emit(ModelCallPayload(model="deepseek-flash", thinking=False, usage=Usage(), cost_cny=0, latency_ms=0,
                              request_ref=req, response_ref=resp), role=role)  # type: ignore[arg-type]  # fmt: skip


def test_chat_turn_call_before_task_start_is_not_replayed(tmp_path: Path) -> None:
    rec = TrajectoryRecorder("t", "r", run_dir=tmp_path)
    model_call(rec, [Message(role="user", content="你好")], Message(role="assistant", content="开始干活"))
    rec.emit(TaskStartedPayload(issue_title="x", repo="o/r", config_hash="c"))
    assert replay_history(tmp_path, upto_seq=rec.next_seq) is None


def test_missing_response_artifact_returns_none(tmp_path: Path) -> None:
    rec = TrajectoryRecorder("t", "r", run_dir=tmp_path)
    rec.emit(TaskStartedPayload(issue_title="x", repo="o/r", config_hash="c"))
    model_call(rec, [Message(role="system", content="s"), Message(role="user", content="u")],
               Message(role="assistant", content="a"))  # fmt: skip
    for f in (tmp_path / "artifacts").glob("*-response.json"):
        f.unlink()
    assert replay_history(tmp_path, upto_seq=rec.next_seq) is None
    assert replay_history(tmp_path / "nope", upto_seq=None) is None


def test_upto_seq_cuts_history_and_seals_dangling(tmp_path: Path) -> None:
    rec = TrajectoryRecorder("t", "r", run_dir=tmp_path)
    rec.emit(TaskStartedPayload(issue_title="x", repo="o/r", config_hash="c"))
    base = [Message(role="system", content="s"), Message(role="user", content="u")]
    a1 = Message(role="assistant", tool_calls=[ToolCallSpec(id="x1", name="read_file", arguments="{}"),
                                               ToolCallSpec(id="x2", name="bash", arguments="{}")])  # fmt: skip
    model_call(rec, base, a1)
    rp = replay_history(tmp_path, upto_seq=rec.next_seq)
    assert rp is not None and rp.model_calls == 1
    assert [m.role for m in rp.messages] == ["system", "user", "assistant", "tool", "tool"]
    assert all("未执行" in (m.content or "") for m in rp.messages[3:])
    assert replay_history(tmp_path, upto_seq=1) is None  # 检查点在第一次调用之前：没有可重放的


def test_seal_only_missing() -> None:
    a = Message(role="assistant", tool_calls=[ToolCallSpec(id="a", name="x", arguments="{}"),
                                              ToolCallSpec(id="b", name="y", arguments="{}")])  # fmt: skip
    msgs = [a, Message(role="tool", tool_call_id="a", name="x", content="ok")]
    assert seal(msgs, "r") == 1 and [m.tool_call_id for m in msgs[1:]] == ["a", "b"]
    assert seal(msgs, "r") == 0
