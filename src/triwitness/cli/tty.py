"""终端审批（spec 010 §11 Q5）：`tw run` 在交互终端（stdin 是 TTY）里用 y/N 提示审批。

- 权限审批：y = 允许一次，s = 本次任务内允许，其余（含直接回车）= 拒绝；
- 计划确认（tool=Plan）：y = 批准计划，其余 = 拒绝；
- ask_human（tool=AskHuman）：输入回答文字；n / no = 否；直接回车 = 不回答（等同拒绝）；
- stdin 关闭（EOF）→ 返回 None，任务进入 needs_human（与没有审批通道一致）。
非 TTY（管道 / CI）不使用本模块：沿用“非交互运行，需要确认的操作一律拒绝”。
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable

from triwitness.core.events import ApprovalRequestedPayload
from triwitness.harness.approvals import ApprovalDecision, Approver

ACTION_SHOWN = 1200


def _block(req: ApprovalRequestedPayload) -> str:
    action = req.action if len(req.action) <= ACTION_SHOWN else req.action[:ACTION_SHOWN] + "…"
    lines = ["", "── 需要你确认 ──", f"  {req.display or req.tool}", f"  原因：{req.reason}  ·  风险 {req.risk}"]
    lines += ["  " + ln for ln in action.splitlines() or [""]]
    return "\n".join(lines) + "\n"


def make_tty_approver(
    read: Callable[[str], str] | None = None, write: Callable[[str], object] | None = None
) -> Approver:
    """read(prompt) 返回一行输入（EOFError = 没有人）；write 输出到 stderr。测试里注入假的 read / write。"""
    read_line = read or input
    out = write or (lambda s: sys.stderr.write(s) and sys.stderr.flush())
    lock = asyncio.Lock()  # 并发的审批请求排队问，避免提示交错

    async def approve(req: ApprovalRequestedPayload) -> ApprovalDecision | None:
        async with lock:
            out(_block(req))
            if req.tool == "AskHuman":
                prompt = "回答（n = 否；直接回车 = 不回答）："
            elif req.tool == "Plan":
                prompt = "批准这个计划？[y/N] "
            elif req.tool == "OpenPR":
                prompt = "推送分支并开这个 PR？[y/N] "
            elif "allow_session" in req.options:
                prompt = "允许？[y] 一次 / [s] 本次任务 / [N] 拒绝："
            else:
                prompt = "允许？[y/N] "
            try:
                raw = await asyncio.to_thread(read_line, prompt)
            except (EOFError, KeyboardInterrupt):
                return None
            ans = raw.strip()
            if req.tool == "AskHuman":
                if not ans or ans.lower() in ("n", "no", "否"):
                    return ApprovalDecision("deny", comment=None if not ans else "否")
                return ApprovalDecision("allow", comment=ans)
            low = ans.lower()
            if low in ("y", "yes", "是"):
                return ApprovalDecision("allow", "once")
            if low in ("s", "session") and "allow_session" in req.options:
                return ApprovalDecision("allow", "session")
            return ApprovalDecision("deny", comment="终端拒绝" if ans else None)

    return approve


__all__ = ["make_tty_approver"]
