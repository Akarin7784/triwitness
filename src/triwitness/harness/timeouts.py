"""超时循环守卫 + 墙钟提示（W5-13 第三轮；TB2 r2 发现）。

TB2 r2 里 overfull-hbox 的 Agent 在命令超时后一再重跑同类长命令
（`timeout 590 perl search5.pl …` 却用默认 120s 工具超时），最后被 Harbor 的 750s Agent 超时取消。
这里做四件事，都可配置（HarnessConfig.timeout_guard）；默认关，外部 / Harbor 任务由 harbor_agent 打开，
仓库模式 SWE 的默认行为不变：

1. 记录超时的命令；超时后在下一轮注入提醒（后台运行 + 轮询、缩小规模、更短的 timeout_s、更便宜的做法）。
2. 再次发出与已超时命令几乎相同的命令（数字归一后 token Jaccard ≥ similarity）：
   block = 不执行、直接返回说明；warn = 照常执行、结果后附警告。
   显式把 timeout_s 调得比上次超时更长（且剩余时间够）算正当重试，放行。
3. 有墙钟预算时，把单条命令的 timeout_s 压到剩余时间以内（留 reserve_s 收尾），避免一条命令跨过取消线。
4. 墙钟用到 wall_notes 的比例时注入“已用 / 剩余”提示，让 Agent 在被取消前收尾。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

SHELL_TOOLS = frozenset({"bash", "powershell"})
_NUM = re.compile(r"\d+(?:\.\d+)?")
_TOKEN = re.compile(r"[A-Za-z_][\w.-]*|\S")


class TimeoutGuardConfig(BaseModel):
    enabled: bool = False
    action: Literal["block", "warn"] = "block"  # 重复已超时的命令：block 不执行 / warn 执行并警告
    similarity: float = Field(default=0.8, gt=0, le=1)  # 数字归一后的 token Jaccard 阈值
    remind: bool = True  # 超时后注入提醒
    cap_to_remaining: bool = True  # 有墙钟预算时把 timeout_s 压到剩余时间以内
    reserve_s: int = Field(default=45, ge=0)  # 留给 finish / 收尾的秒数
    wall_notes: list[float] = Field(default_factory=lambda: [0.5, 0.75, 0.9])  # 墙钟比例提示


def normalize_command(cmd: str) -> list[str]:
    """数字一律换成 N（ITERS=2000 / timeout 590 / sol_5 这类参数变化不算“新做法”），去掉多余空白后切 token。"""
    return _TOKEN.findall(_NUM.sub("N", " ".join(cmd.split())))


def similarity(a: str, b: str) -> float:
    ta, tb = normalize_command(a), normalize_command(b)
    if ta == tb:
        return 1.0
    sa, sb = set(ta), set(tb)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _args(arguments: str) -> dict[str, Any]:
    try:
        v = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {}
    return v if isinstance(v, dict) else {}


@dataclass
class TimedOut:
    command: str
    timeout_s: int
    step: int


@dataclass
class TimeoutGuard:
    cfg: TimeoutGuardConfig
    default_timeout_s: int = 120
    timed_out: list[TimedOut] = field(default_factory=list)
    blocked: int = 0
    notes_sent: set[float] = field(default_factory=set)

    def match(self, command: str) -> TimedOut | None:
        best: tuple[float, TimedOut] | None = None
        for t in self.timed_out:
            s = similarity(command, t.command)
            if s >= self.cfg.similarity and (best is None or s > best[0]):
                best = (s, t)
        return best[1] if best else None

    def check(self, name: str, arguments: str, *, remaining_s: float | None) -> tuple[str, TimedOut | None]:
        """执行前：返回 ("run" | "block" | "warn", 命中的超时记录)。"""
        if not self.cfg.enabled or name not in SHELL_TOOLS:
            return "run", None
        a = _args(arguments)
        cmd = str(a.get("command") or "")
        hit = self.match(cmd) if cmd else None
        if hit is None:
            return "run", None
        asked = int(a.get("timeout_s") or self.default_timeout_s)
        longer_ok = asked > hit.timeout_s and (remaining_s is None or asked <= remaining_s)
        if longer_ok:  # 显式要了更长的时间、且剩余时间够：正当重试
            return "run", hit
        return self.cfg.action, hit

    def capped_arguments(self, name: str, arguments: str, remaining_s: float | None) -> tuple[str, int | None]:
        """把 timeout_s 压到 remaining_s − reserve_s 以内；返回（新参数, 压到的秒数 or None）。"""
        if not self.cfg.enabled or not self.cfg.cap_to_remaining or name not in SHELL_TOOLS or remaining_s is None:
            return arguments, None
        a = _args(arguments)
        if not a.get("command"):
            return arguments, None
        asked = int(a.get("timeout_s") or self.default_timeout_s)
        allow = max(5, int(remaining_s - self.cfg.reserve_s))
        if asked <= allow:
            return arguments, None
        a["timeout_s"] = allow
        return json.dumps(a, ensure_ascii=False), allow

    def record(self, name: str, arguments: str, result: Any, step: int) -> TimedOut | None:
        if not self.cfg.enabled or name not in SHELL_TOOLS or getattr(result, "error_code", None) != "timeout":
            return None
        a = _args(arguments)
        t = TimedOut(str(a.get("command") or ""), int(a.get("timeout_s") or self.default_timeout_s), step)
        self.timed_out.append(t)
        return t

    def wall_note(self, elapsed_s: float, budget_s: float | None) -> float | None:
        """墙钟比例跨过某个 wall_notes 阈值（每个只提示一次）→ 返回该比例。"""
        if not self.cfg.enabled or not budget_s:
            return None
        frac = elapsed_s / budget_s
        hit = [f for f in sorted(self.cfg.wall_notes) if frac >= f and f not in self.notes_sent]
        if not hit:
            return None
        self.notes_sent.update(hit)
        return hit[-1]


def timeout_reminder(t: TimedOut, remaining_s: float | None) -> str:
    left = f"本任务剩余约 {int(remaining_s)} 秒。" if remaining_s is not None else ""
    tips = [
        f"上一条命令在 {t.timeout_s} 秒后超时被终止（输出不完整）。{left}",
        "不要原样或换几个参数重跑同一条长命令：",
        "①真需要长时间运行就放后台（`nohup … > /tmp/x.log 2>&1 &`），之后用短命令轮询日志；",
        "②先用更小的输入 / 更少的迭代确认思路和耗时；",
        "③给探索性命令设更短的 timeout_s；",
        "④考虑更便宜的做法（直接推理、换算法、读文档）。",
        "与已超时命令几乎相同的命令会被拦截，除非你显式把 timeout_s 调大且剩余时间够。",
    ]
    return "".join(tips)


def blocked_message(t: TimedOut, action: str) -> str:
    head = "已拦截（未执行）" if action == "block" else "警告"
    return (
        f"[{head}] 这条命令与第 {t.step} 步已超时（{t.timeout_s} 秒）的命令几乎相同。"
        "请换做法：放后台运行并轮询、缩小规模、或改用更便宜的方法；确需更多时间就显式调大 timeout_s。"
    )


def wall_reminder(frac: float, elapsed_s: float, budget_s: float) -> str:
    left = max(0, int(budget_s - elapsed_s))
    tail = "现在就收尾：保存产物、清理临时文件、调用 finish。" if frac >= 0.85 else \
        "按剩余时间安排：不要再开很长的命令，优先保证产物可用，再逐步改进。"  # fmt: skip
    return f"时间提醒：已用约 {int(elapsed_s)} 秒 / 预算 {int(budget_s)} 秒（{frac:.0%}），剩余约 {left} 秒。{tail}"
