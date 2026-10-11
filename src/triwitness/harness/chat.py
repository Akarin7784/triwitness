"""对话轮（0.3.1）：每条用户消息先走一次对话调用，由模型决定直接回复还是开始仓库工作。

- 不调工具：直接回复，本轮结束（没有 finish / 验证 / 证据 / 补丁）；`turn_finished.kind = chat`。
- 调用 `start_repo_work{goal}`：已选仓库就在同一个 run 里接着跑常规任务（run_local，共用 recorder）；
  没选仓库就直接回复请用户先选仓库（不再调模型）。
- 多轮历史：每个 run 目录写 `turn.json`（parent / user / assistant / kind），下一轮带 `--parent-run`
  沿 parent 链取最近若干轮作为对话历史；从同一个 parent 分叉即重试 / 编辑。
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from triwitness.core.events import ModelCallPayload, TurnFinishedPayload, UserMessagePayload, billing
from triwitness.core.models import Budget
from triwitness.core.redact import redact_text
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.harness.deltas import DeltaWriter
from triwitness.harness.local_run import LocalRunOutcome
from triwitness.llm.stream import streaming
from triwitness.llm.types import LLMRequest, Message
from triwitness.prompts import load_prompt
from triwitness.telemetry.trajectory import TrajectoryRecorder

RUN_ID_RE = re.compile(r"^r_[0-9A-Za-z]{8,40}$")
MAX_TURNS = 20
TURN_TEXT_MAX = 4000
WORK_TOOL = "start_repo_work"
NO_REPO_REPLY = "要在仓库里动手，需要先在输入框下方选一个本地仓库（git 仓库），选好后把要求再发一次。"

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": WORK_TOOL,
            "description": "用户明确要求在已选仓库里修改 / 修复 / 实现 / 排查时调用；其余情况不要调用。",
            "parameters": {
                "type": "object",
                "properties": {"goal": {"type": "string", "description": "一两句话写清这次要做什么"}},
                "required": ["goal"],
            },
        },
    }
]

Work = Callable[[str, TrajectoryRecorder], Awaitable[LocalRunOutcome]]


@dataclass
class TurnOutcome:
    kind: str  # chat / task
    run_id: str
    run_dir: Path
    reply: str | None
    cost_cny: float
    task: LocalRunOutcome | None = None
    nominal_cost_cny: float = 0.0  # 名义价（含本地缓存命中）；实付见 cost_cny


def nominal_total(events: Any) -> float:
    """本轮所有 model_call 的名义价之和（没写名义价的就是实付）。"""
    total = 0.0
    for e in events:
        if e.kind == "model_call":
            p = e.payload
            total += float(p.get("nominal_cost_cny") if p.get("nominal_cost_cny") is not None else p["cost_cny"])
    return total


def valid_run_id(run_id: str) -> bool:
    return bool(RUN_ID_RE.match(run_id))


def load_history(home: Path, parent: str | None, *, limit: int = MAX_TURNS) -> list[Message]:
    """沿 parent 链读 turn.json，返回按时间顺序的 user / assistant 消息（最多 limit 轮）。"""
    turns: list[dict[str, Any]] = []
    seen: set[str] = set()
    while parent and valid_run_id(parent) and parent not in seen and len(turns) < limit:
        seen.add(parent)
        f = home / "runs" / parent / "turn.json"
        try:
            t = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            break
        turns.append(t)
        parent = t.get("parent")
    out: list[Message] = []
    for t in reversed(turns):
        user, assistant = str(t.get("user") or ""), str(t.get("assistant") or "")
        if user:
            out.append(Message(role="user", content=user[:TURN_TEXT_MAX]))
        out.append(Message(role="assistant", content=(assistant or "（无回复）")[:TURN_TEXT_MAX]))
    return out


def write_turn(run_dir: Path, *, parent: str | None, user: str, assistant: str | None, kind: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    data = {"v": 1, "parent": parent, "user": redact_text(user)[:TURN_TEXT_MAX],
            "assistant": redact_text(assistant or "")[:TURN_TEXT_MAX], "kind": kind}  # fmt: skip
    (run_dir / "turn.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def context_note(repo: Path | None) -> str:
    return f"当前已选仓库：{repo}" if repo is not None else "当前未选择仓库"


def work_issue(text: str, goal: str, history: list[Message]) -> str:
    """转成仓库任务时的任务描述：用户原话 + 模型归纳的目标 + 最近几轮上下文。"""
    parts = [text.strip()]
    if goal.strip() and goal.strip() != text.strip():
        parts.append(f"目标：{goal.strip()}")
    recent = [m for m in history if m.content][-4:]
    if recent:
        ctx = "\n".join(f"- {'用户' if m.role == 'user' else '助手'}：{(m.content or '')[:300]}" for m in recent)
        parts.append(f"前面的对话：\n{ctx}")
    return "\n\n".join(parts)


def _goal(args: str) -> str:
    try:
        v = json.loads(args or "{}")
    except ValueError:
        return ""
    return str(v.get("goal") or "") if isinstance(v, dict) else ""


async def run_turn(
    text: str,
    *,
    router: Any,
    rec: TrajectoryRecorder,
    run_dir: Path,
    home: Path,
    repo: Path | None,
    parent: str | None,
    work: Work,
    budget: Budget | None = None,
) -> TurnOutcome:
    rec.emit(UserMessagePayload(text=text[:2000], repo=str(repo) if repo else None, parent_run=parent,
                                display=text[:120] or None))  # fmt: skip
    history = load_history(home, parent)
    prompt = load_prompt("chat")
    system = f"{prompt.text}\n\n{context_note(repo)}"
    messages = [Message(role="system", content=system), *history, Message(role="user", content=text)]
    req = LLMRequest(role="executor", messages=messages, tools=TOOLS)
    guard = TaskBudgetGuard(budget=budget or Budget.for_run())
    call_id = f"c{rec.next_seq}"
    writer = DeltaWriter(rec, "executor", call_id)
    try:
        with streaming(writer):
            resp = await router.complete(req, guard=guard, task_id=rec.task_id, mode="background", category="chat")
    finally:
        writer.flush()
    seq = rec.next_seq
    req_ref = rec.artifact(f"{seq}-request.json", {"role": "chat", "prompt": prompt.tag, "tools": [WORK_TOOL],
                                                   "messages": [m.model_dump(mode="json", exclude_none=True)
                                                                for m in messages]})  # fmt: skip
    resp_ref = rec.artifact(f"{seq}-response.json", {"message": resp.message.model_dump(mode="json", exclude_none=True),
                                                     "usage": resp.usage.model_dump(mode="json")})  # fmt: skip
    rec.emit(
        ModelCallPayload(call_id=call_id, model=resp.model or resp.served_model or "?", served_model=resp.served_model,
                         thinking=req.thinking, usage=resp.usage, **billing(resp), peak=resp.peak,
                         latency_ms=resp.latency_ms, finish_reason=resp.finish_reason, request_ref=req_ref,
                         response_ref=resp_ref, display="对话"),
        role="executor",
    )  # fmt: skip
    reply = (resp.message.content or "").strip()
    chat_cost = resp.cost_cny
    calls = [c for c in resp.message.tool_calls or [] if c.name == WORK_TOOL]
    if not calls or repo is None:
        if calls:  # 要动手但没选仓库：不再调模型，直接请用户选仓库
            reply = NO_REPO_REPLY
        reply = reply or "（模型没有给出回复）"
        rec.emit(TurnFinishedPayload(kind="chat", status="replied", reply=reply[:2000], cost_cny=chat_cost))
        write_turn(run_dir, parent=parent, user=text, assistant=reply, kind="chat")
        return TurnOutcome(kind="chat", run_id=rec.run_id, run_dir=run_dir, reply=reply, cost_cny=chat_cost,
                           nominal_cost_cny=nominal_total(rec.events))  # fmt: skip
    issue = work_issue(text, _goal(calls[0].arguments), history)
    out = await work(issue, rec)
    r = out.result
    summary = (r.finish.summary if r.finish else None) or r.outcome.reason or r.status
    total = chat_cost + r.cost.total_cny
    rec.emit(TurnFinishedPayload(kind="task", status=r.status, reply=reply[:2000] or None, cost_cny=round(total, 6)))
    write_turn(run_dir, parent=parent, user=text, assistant=f"{reply}\n\n[任务 {r.status}] {summary}".strip(),
               kind="task")  # fmt: skip
    return TurnOutcome(kind="task", run_id=rec.run_id, run_dir=run_dir, reply=reply or None, cost_cny=total, task=out,
                       nominal_cost_cny=nominal_total(rec.events))  # fmt: skip


RESUME_TEXT = "继续"


async def run_resume(
    state: Any,
    *,
    rec: TrajectoryRecorder,
    run_dir: Path,
    repo: Path,
    work: Callable[[str, TrajectoryRecorder, Any], Awaitable[LocalRunOutcome]],
) -> TurnOutcome:
    """断点续跑（harness/resume.py）：新的一轮直接是任务，不过对话模型；轮次挂在被续跑的那一轮后面。"""
    rec.emit(UserMessagePayload(text=RESUME_TEXT, repo=str(repo), parent_run=state.from_run,
                                display=f"继续 · 从 {state.from_run} 的进度"))  # fmt: skip
    out = await work(state.issue, rec, state)
    r = out.result
    summary = (r.finish.summary if r.finish else None) or r.outcome.reason or r.status
    total = r.cost.total_cny
    rec.emit(TurnFinishedPayload(kind="task", status=r.status, reply=None, cost_cny=round(total, 6)))
    write_turn(run_dir, parent=state.from_run, user=RESUME_TEXT, assistant=f"[任务 {r.status}] {summary}", kind="task")
    return TurnOutcome(kind="task", run_id=rec.run_id, run_dir=run_dir, reply=None, cost_cny=total, task=out,
                       nominal_cost_cny=nominal_total(rec.events))  # fmt: skip


__all__ = [
    "NO_REPO_REPLY",
    "RESUME_TEXT",
    "TOOLS",
    "TurnOutcome",
    "load_history",
    "run_resume",
    "run_turn",
    "valid_run_id",
    "write_turn",
]
