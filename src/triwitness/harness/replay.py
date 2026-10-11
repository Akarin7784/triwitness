"""事件日志重放（spec 011 §3，W4-09）：从上一次运行的轨迹重建 Executor 的消息历史。

- 检查点 = 每一步结束时（全部工具结果写完）记下的事件序号 `event_seq`（resume.json）。工作区快照与它同时落盘，
  所以“历史截到检查点”与“工作区恢复到检查点”是一致的。
- 重建：检查点之后如果还有 Executor 的模型调用，它的请求就是检查点时刻模型看到的完整消息（含提醒、清理 / 压缩后的
  形态）；否则用检查点之前最后一次调用的请求 + 响应 + 这一步的工具消息。
- **不重复执行有副作用的工具**：检查点之后的调用一律不重放、不自动重跑。工作区里的副作用随快照回滚；
  对外的副作用（side_effects=external，如 ask_human）由工具日志 `tool-journal.jsonl` 查出来，写进续跑说明，
  让模型先确认现状再决定。
- 续跑的新 run 把重建的历史原样作为第一次请求的前缀（DeepSeek 前缀缓存可以命中），再追加一条续跑说明。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from triwitness.llm.types import Message
from triwitness.telemetry.trajectory import Trajectory

JOURNAL = "tool-journal.jsonl"


@dataclass
class Replay:
    messages: list[Message]
    upto_seq: int | None  # 截止的事件序号（不含）；None = 没有检查点信息，取到日志末尾
    model_calls: int  # 截止前 Executor 的模型调用次数（= 重放的步数）
    after_checkpoint: list[dict[str, Any]] = field(default_factory=list)  # 检查点之后发起过的有副作用工具（不重跑）


def journal_path(run_dir: Path) -> Path:
    return run_dir / JOURNAL


def journal_write(run_dir: Path | None, entry: dict[str, Any]) -> None:
    """有副作用的工具：开始前写 start、结束后写 end（预写日志；进程被杀时能知道哪一个正在执行）。"""
    if run_dir is None:
        return
    with journal_path(run_dir).open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()


def read_journal(run_dir: Path) -> list[dict[str, Any]]:
    p = journal_path(run_dir)
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            break  # 最后一行写到一半
    return out


def _load_msgs(run_dir: Path, ref: str | None) -> list[Message] | None:
    if not ref or not (run_dir / ref).is_file():
        return None
    try:
        doc = json.loads((run_dir / ref).read_text(encoding="utf-8"))
        return [Message.model_validate(m) for m in doc["messages"]]
    except (OSError, ValueError, KeyError):
        return None


def replay_history(run_dir: Path, *, upto_seq: int | None, role: str = "executor") -> Replay | None:
    """重建 role 的消息历史，截到 upto_seq（不含）。没有可用的请求产物时返回 None（退回旧的续跑说明方式）。"""
    path = run_dir / "trajectory.jsonl"
    if not path.is_file():
        return None
    events = Trajectory.read_events(path)
    # 只看最后一次 task_started 之后：之前的是对话轮（chat）的模型调用，不属于 Executor 的历史
    start = max((e.seq for e in events if e.kind == "task_started"), default=-1)
    events = [e for e in events if e.seq > start]
    calls = [e for e in events if e.kind == "model_call" and e.role == role and e.payload.get("request_ref")]
    before = [e for e in calls if upto_seq is None or e.seq < upto_seq]
    if not before:
        return None
    later = [e for e in calls if upto_seq is not None and e.seq >= upto_seq]
    messages: list[Message] | None = None
    if later:  # 下一次请求 = 检查点时刻的完整历史
        messages = _load_msgs(run_dir, later[0].payload.get("request_ref"))
    if messages is None:
        last = before[-1]
        messages = _load_msgs(run_dir, last.payload.get("request_ref"))
        if messages is None:
            return None
        ref = last.payload.get("response_ref")
        if not ref or not (run_dir / ref).is_file():
            return None
        try:
            resp = json.loads((run_dir / ref).read_text(encoding="utf-8"))
            messages.append(Message.model_validate(resp["message"]))
        except (OSError, ValueError, KeyError):
            return None
        for e in events:
            if e.seq <= last.seq or (upto_seq is not None and e.seq >= upto_seq):
                continue
            mref = e.payload.get("message_ref") if e.kind == "tool_call" and e.role == role else None
            if mref and (run_dir / mref).is_file():
                messages.append(Message.model_validate_json((run_dir / mref).read_text(encoding="utf-8")))
    seal(messages, "进程在此中断，没有执行；工作区已恢复到上一个检查点，如仍需要请重新调用")
    return Replay(messages=messages, upto_seq=upto_seq, model_calls=len(before),
                  after_checkpoint=_after_checkpoint(run_dir, upto_seq))  # fmt: skip


def seal(messages: list[Message], reason: str) -> int:
    """最后一条 assistant 里没有结果的 tool_call 补错误结果（与 AgentLoop.seal_dangling 相同的规则）。"""
    idx = next((i for i in range(len(messages) - 1, -1, -1) if messages[i].role == "assistant"), None)
    if idx is None or not messages[idx].tool_calls:
        return 0
    answered = {m.tool_call_id for m in messages[idx + 1 :] if m.role == "tool"}
    missing = [c for c in messages[idx].tool_calls or [] if c.id not in answered]
    insert_at = idx + 1 + sum(1 for m in messages[idx + 1 :] if m.role == "tool")
    messages[insert_at:insert_at] = [Message(role="tool", tool_call_id=c.id, name=c.name, content=f"[未执行：{reason}]")
                                     for c in missing]  # fmt: skip
    return len(missing)


def _after_checkpoint(run_dir: Path, upto_seq: int | None) -> list[dict[str, Any]]:
    """检查点之后开始过的有副作用工具（start 时的事件序号 ≥ upto_seq）；finished=False 表示执行中被打断。"""
    if upto_seq is None:
        return []
    started: dict[str, dict[str, Any]] = {}
    for e in read_journal(run_dir):
        cid = str(e.get("call_id"))
        if e.get("phase") == "start" and int(e.get("seq", -1)) >= upto_seq:
            started[cid] = {"tool": e.get("tool"), "side_effects": e.get("side_effects"),
                            "summary": e.get("summary", ""), "finished": False, "ok": None}  # fmt: skip
        elif e.get("phase") == "end" and cid in started:
            started[cid].update(finished=True, ok=e.get("ok"))
    return list(started.values())


def replay_note(rp: Replay, *, from_run: str, applied: list[str], held: list[str], skipped: list[str],
                repro: dict[str, Any] | None) -> str:  # fmt: skip
    """重放之后追加的一条 user 消息：说明是续跑、工作区状态、检查点之后哪些副作用没有重放。"""
    lines = [f"<resume from_run=\"{from_run}\" replayed_steps=\"{rp.model_calls}\">",
             "进程中断后续跑：上面的对话历史是从事件日志重放的，截到最后一个完整步骤的检查点；工作区也恢复到了这个检查点。"
             "不要从头开始。"]  # fmt: skip
    if applied:
        lines.append("工作区里已恢复的改动：" + "、".join(applied[:30]) + ("…" if len(applied) > 30 else ""))
    if held:
        lines.append("复现还没被接受，这些源码改动暂未恢复（先提交复现再改）：" + "、".join(held[:30]))
    if skipped:
        lines.append("这些文件太大没有保存，需要重新修改：" + "、".join(skipped[:10]))
    ext = [a for a in rp.after_checkpoint if a.get("side_effects") == "external"]
    ws = [a for a in rp.after_checkpoint if a.get("side_effects") != "external"]
    if ws:
        lines.append("检查点之后还执行过这些修改工作区的工具，效果已随工作区回滚，没有自动重跑："
                     + "；".join(_fmt(a) for a in ws[:10]))  # fmt: skip
    if ext:
        lines.append("注意：检查点之后这些对外的操作已经发起过（可能已经生效），不会自动重做；需要的话先确认再决定："
                     + "；".join(_fmt(a) for a in ext[:10]))  # fmt: skip
    if repro:
        if repro.get("status") == "reproduced":
            lines.append(f"复现已提交并被接受：{repro.get('path')}（命令 {repro.get('cmd')}），不需要再提交。")
        else:
            lines.append(f"复现已声明无法做（{repro.get('reason', '')}），不需要再提交。")
    lines.append("先用 git diff 确认现状，再从中断的地方继续。")
    lines.append("</resume>")
    return "\n".join(lines)


def _fmt(a: dict[str, Any]) -> str:
    state = "执行中被打断" if not a.get("finished") else ("已完成" if a.get("ok") else "已失败")
    s = str(a.get("summary") or "")
    return f"{a.get('tool')}（{state}）" + (f" {s}" if s else "")


__all__ = ["JOURNAL", "Replay", "journal_write", "read_journal", "replay_history", "replay_note", "seal"]  # fmt: skip
