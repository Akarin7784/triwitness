"""tw-bridge/1：桌面端（Tauri 后端 / Vite 开发桥）与 Python 核心之间的逐行 JSON 协议。

stdout（核心 → 桌面），每行一个 JSON：
- tw-events/1 事件原样输出（带 `"v": 1`）；
- 控制消息带 `"bridge"` 字段：
  `hello`（protocol、mode）→ `run`（run_id、run_dir，首个事件时）→ … → `result` 或 `error`（message、code）；
  对命令回 `ack`。`result.kind`：`chat`（直接回复：reply、cost_cny、run_dir，没有补丁 / 证据）或 `task`
  （status、verdict、risk_level、clean_env、branch、run_dir、cost_cny、summary、pr_md，以及对话轮的 reply）。
stdin（桌面 → 核心），每行一个 JSON 命令：
- `{"cmd": "approve", "request_id": "...", "decision": "allow"|"deny", "scope": "once"|"session"|"always"}`
- `{"cmd": "cancel"}`
人读的日志一律走 stderr；stdout 只有协议行。
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from triwitness.core.errors import BudgetExceeded
from triwitness.harness.approvals import ApprovalBroker, Approver
from triwitness.harness.chat import TurnOutcome
from triwitness.harness.local_run import LocalRunOutcome
from triwitness.telemetry.trajectory import TrajectoryEvent

PROTOCOL = "tw-bridge/1"
PR_MD_MAX = 20_000

Write = Callable[[str], None]
Outcome = LocalRunOutcome | TurnOutcome
Start = Callable[[Approver, Callable[[TrajectoryEvent], None]], Awaitable[Outcome]]


def _line(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def result_message(out: LocalRunOutcome) -> dict[str, Any]:
    r = out.result
    ev = r.verification.evidence if r.verification else None
    pr = out.run_dir / "pr.md"
    pr_md = pr.read_text(encoding="utf-8")[:PR_MD_MAX] if pr.is_file() else None
    return {
        "bridge": "result", "status": r.status, "run_dir": str(out.run_dir), "branch": out.branch,
        "backend": out.backend, "cost_cny": round(r.cost.total_cny, 6), "steps": r.outcome.steps,
        "reason": r.outcome.reason, "summary": r.finish.summary if r.finish else None,
        "verdict": ev.verdict if ev else None, "risk_level": ev.risk_level if ev else None,
        "clean_env": ev.clean_env if ev else None, "pr_md": pr_md,
    }  # fmt: skip


def turn_message(out: Outcome) -> dict[str, Any]:
    """对话轮结果：`kind=chat` 只有回复（没有补丁 / 证据 / 结果卡）；`kind=task` 带上任务结果字段。"""
    if isinstance(out, LocalRunOutcome):
        return {**result_message(out), "kind": "task"}
    if out.task is not None:
        return {**result_message(out.task), "kind": "task", "reply": out.reply, "cost_cny": round(out.cost_cny, 6),
                "nominal_cost_cny": round(out.nominal_cost_cny, 6)}  # fmt: skip
    return {"bridge": "result", "kind": "chat", "status": "replied", "reply": out.reply, "run_dir": str(out.run_dir),
            "run_id": out.run_id, "cost_cny": round(out.cost_cny, 6),
            "nominal_cost_cny": round(out.nominal_cost_cny, 6)}  # fmt: skip


def error_message(e: BaseException) -> dict[str, Any]:
    """桌面端按 code 给出提示（budget = 触及非金钱安全上限：轮数 / 时间 / token 兜底）。"""
    if isinstance(e, BudgetExceeded):
        return {"bridge": "error", "code": "budget", "message": str(e)}
    return {"bridge": "error", "message": f"{type(e).__name__}: {e}"}


class Bridge:
    """一次任务的桥：把事件写出去，把 stdin 命令转成审批决定 / 取消。可注入 IO，便于测试。"""

    def __init__(self, write: Write, *, mode: str, home: Path) -> None:
        self.write = write
        self.mode = mode
        self.home = home
        self.broker = ApprovalBroker()
        self.task: asyncio.Task[Outcome] | None = None
        self._announced = False

    def send(self, obj: dict[str, Any]) -> None:
        self.write(_line(obj))

    def on_event(self, ev: TrajectoryEvent) -> None:
        if not self._announced:
            self._announced = True
            self.send({"bridge": "run", "run_id": ev.run_id, "task_id": ev.task_id,
                       "run_dir": str(self.home / "runs" / ev.run_id)})  # fmt: skip
        self.write(ev.to_json_line())

    def handle(self, raw: str) -> None:
        raw = raw.strip()
        if not raw:
            return
        try:
            cmd = json.loads(raw)
            kind = cmd["cmd"]
        except (ValueError, KeyError, TypeError):
            self.send({"bridge": "ack", "cmd": None, "ok": False, "error": "无法解析的命令"})
            return
        if kind == "approve":
            decision, scope = cmd.get("decision"), cmd.get("scope", "once")
            rid = str(cmd.get("request_id"))
            valid = decision in ("allow", "deny") and scope in ("once", "session", "always")
            ok = valid and self.broker.resolve_approval(rid, decision, scope, cmd.get("comment"))
            self.send({"bridge": "ack", "cmd": "approve", "request_id": cmd.get("request_id"), "ok": bool(ok)})
        elif kind == "cancel":
            ok = self.task is not None and not self.task.done()
            if ok and self.task is not None:
                self.task.cancel()
            self.send({"bridge": "ack", "cmd": "cancel", "ok": ok})
        else:
            self.send({"bridge": "ack", "cmd": kind, "ok": False, "error": "未知命令"})

    async def run(self, start: Start, commands: asyncio.Queue[str | None]) -> int:
        self.send({"bridge": "hello", "protocol": PROTOCOL, "mode": self.mode})
        self.task = asyncio.ensure_future(start(self.broker.wait, self.on_event))

        async def pump() -> None:
            while True:
                raw = await commands.get()
                if raw is None:
                    return
                self.handle(raw)

        reader = asyncio.ensure_future(pump())
        try:
            out = await self.task
        except Exception as e:  # 核心报错：告诉桌面端，退出码 2
            self.send(error_message(e))
            return 2
        finally:
            reader.cancel()
        self.send(turn_message(out))
        return 0


def stdin_queue(loop: asyncio.AbstractEventLoop) -> asyncio.Queue[str | None]:
    """后台线程读 stdin（Windows 管道也可用），逐行投递到事件循环；EOF 投递 None。"""
    q: asyncio.Queue[str | None] = asyncio.Queue()

    def reader() -> None:
        for raw in sys.stdin:
            loop.call_soon_threadsafe(q.put_nowait, raw)
        loop.call_soon_threadsafe(q.put_nowait, None)

    threading.Thread(target=reader, name="tw-bridge-stdin", daemon=True).start()
    return q


def stdout_writer() -> Write:
    out = sys.stdout
    if hasattr(out, "reconfigure"):
        out.reconfigure(encoding="utf-8", newline="\n")  # type: ignore[union-attr]
    lock = threading.Lock()

    def write(line: str) -> None:
        with lock:
            out.write(line + "\n")
            out.flush()

    return write


__all__ = ["PROTOCOL", "Bridge", "error_message", "result_message", "stdin_queue", "stdout_writer", "turn_message"]
