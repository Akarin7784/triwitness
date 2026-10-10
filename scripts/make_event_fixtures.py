"""生成 evals/fixtures/events/*.jsonl（tw-events/1 golden fixture，内容手写，贴近桌面端 mock 的 Issue #87）。

确定性输出：固定时间、固定 ID；价格按 deepseek-flash 空闲价（configs/pricing.yaml）。
用法：uv run python scripts/make_event_fixtures.py [--check]
W1-24 完成后改用 FakeRouter 真实跑出的轨迹重新生成，diff 只允许时间戳与 ID 不同。
"""

from __future__ import annotations

import sys
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

from triwitness.core.events import (
    CheckpointPayload,
    ErrorPayload,
    LoopWarningPayload,
    ModelCallPayload,
    Payload,
    ReviewPayload,
    StateChangePayload,
    TaskFinishedPayload,
    TaskStartedPayload,
    ToolCallPayload,
    TrajectoryEvent,
    VerificationPayload,
    make_event,
)
from triwitness.core.ids import new_ulid
from triwitness.core.models import (
    CostLine,
    CostReport,
    FileChange,
    Finding,
    FinishReport,
    ReproRef,
    Role,
    TaskState,
    Usage,
)

OUT = Path(__file__).resolve().parent.parent / "evals" / "fixtures" / "events"
OFF_PEAK = {"hit": 0.02, "miss": 1.0, "out": 4.0}  # 元 / 百万 token
PRICING_VERSION = "deepseek-2026-10-10"
MODEL = "deepseek-flash"
SERVED = "deepseek-v4.1-flash"
S = TaskState


def price(u: Usage) -> float:
    c = u.cache_hit_tokens * OFF_PEAK["hit"] + u.cache_miss_tokens * OFF_PEAK["miss"]
    return round((c + u.output_tokens * OFF_PEAK["out"]) / 1_000_000, 6)


def usage(inp: int, hit_rate: float, out: int, reasoning: int | None = None) -> Usage:
    hit = int(inp * hit_rate)
    return Usage(
        input_tokens=inp,
        cache_hit_tokens=hit,
        cache_miss_tokens=inp - hit,
        output_tokens=out,
        reasoning_tokens=reasoning,
    )


class Run:
    def __init__(self, name: str, start: datetime, budget_cny: float) -> None:
        base_ms = int(start.timestamp() * 1000)
        self.task_id = "t_" + new_ulid(base_ms, name.encode().ljust(10, b"\0")[:10])
        self.run_id = "r_" + new_ulid(base_ms + 1, name.encode().rjust(10, b"\1")[:10])
        self.t = start
        self.budget_cny = budget_cny
        self.events: list[TrajectoryEvent] = []
        self.lines: dict[Role, list[Usage]] = defaultdict(list)
        self.costs: dict[Role, float] = defaultdict(float)
        self.state = S.RECEIVED

    def emit(self, role: Role | None, payload: Payload, dt: float = 2.0) -> None:
        self.t += timedelta(seconds=dt)
        ev = make_event(
            seq=len(self.events),
            ts=self.t,
            task_id=self.task_id,
            run_id=self.run_id,
            role=role,
            payload=payload,
        )
        self.events.append(ev)

    def go(self, to: TaskState, display: str) -> None:
        self.emit(None, StateChangePayload(**{"from": self.state}, to=to, display=display, role_hint="system"))
        self.state = to

    def call(self, role: Role, u: Usage, display: str, *, thinking: bool = True, latency_ms: int = 6000) -> None:
        cost = price(u)
        self.lines[role].append(u)
        self.costs[role] += cost
        hint = role if role in ("planner", "executor", "verifier", "reviewer") else "system"
        self.emit(
            role,
            ModelCallPayload(
                model=MODEL,
                served_model=SERVED,
                thinking=thinking,
                usage=u,
                cost_cny=cost,
                peak=False,
                latency_ms=latency_ms,
                finish_reason="tool_calls",
                display=display,
                role_hint=hint,  # type: ignore[arg-type]
            ),
            dt=latency_ms / 1000,
        )

    def tool(self, role: Role, tool: str, ok: bool, display: str, *, exit_code: int | None = 0, ms: int = 300) -> None:
        seq = len(self.events)
        self.emit(
            role,
            ToolCallPayload(
                tool=tool,
                ok=ok,
                exit_code=exit_code,
                duration_ms=ms,
                output_ref=f"artifacts/{seq}-output.txt",
                display=display,
                role_hint=role,  # type: ignore[arg-type]
            ),
            dt=ms / 1000 + 0.2,
        )

    def cost_report(self) -> CostReport:
        lines = [
            CostLine(
                role=role,
                vendor="deepseek",
                model=MODEL,
                calls=len(us),
                usage=sum(us, Usage()),
                cost_cny=round(self.costs[role], 6),
                peak_calls=0,
            )
            for role, us in self.lines.items()
        ]
        return CostReport.from_lines(self.task_id, lines, budget_cny=self.budget_cny, pricing_version=PRICING_VERSION)


def started(r: Run) -> None:
    r.emit(
        None,
        TaskStartedPayload(
            issue_title="并发刷新 token 时偶发 401",
            repo="example/auth-demo",
            issue_number=87,
            config_hash="cfg_3f9a1c",
            display="Issue #87 · 并发刷新 token 时偶发 401",
            role_hint="system",
        ),
        dt=0,
    )


def success() -> list[TrajectoryEvent]:
    r = Run("success", datetime(2026, 10, 9, 19, 58, tzinfo=UTC), 0.8)  # 北京时间 10-10 03:58（空闲）
    started(r)
    r.go(S.PREPARING, "准备沙箱")
    r.go(S.PLANNING, "规划")
    r.call("planner", usage(18_000, 0.0, 900, 600), "读 Issue，定验收：并发刷新后会话仍有效")
    r.tool("planner", "list_files", True, "$ list_files src/auth → 7 个文件")
    r.tool("planner", "grep", True, "$ grep refresh_token src/ → 5 处")
    r.tool("planner", "read_file", True, "$ read_file src/auth/session.py 1-120")
    r.call("planner", usage(26_000, 0.68, 1_200, 800), "根因假设：刷新无锁，旧 token 被并发作废")
    r.go(S.REPRODUCING, "复现")
    r.call("executor", usage(31_000, 0.82, 700, 300), "写复现测试")
    r.tool("executor", "write_file", True, "$ write_file tests/tw_repro/test_issue_87.py")
    r.tool(
        "executor",
        "run_tests",
        False,
        "$ run_tests tests/tw_repro/test_issue_87.py → 1 failed",
        exit_code=1,
        ms=4210,
    )
    r.emit(
        "executor",
        CheckpointPayload(label="复现成功", ref="snap_repro", display="── 复现成功 ──", role_hint="executor"),
    )
    r.go(S.EXECUTING, "修复")
    r.call("executor", usage(38_000, 0.9, 1_100, 500), "给刷新加单飞锁，复用进行中的请求")
    r.tool("executor", "edit_file", True, "$ edit_file src/auth/session.py（+18 −4）")
    r.tool("executor", "run_tests", True, "$ run_tests → 42 passed", ms=6120)
    r.call("executor", usage(42_000, 0.93, 400, 200), "自查 diff")
    r.tool("executor", "bash", True, "$ bash git diff --stat → 2 files")
    r.tool("executor", "finish", True, "finish · 置信度 0.82")
    r.go(S.VERIFYING, "干净沙箱复验")
    r.call("verifier", usage(22_000, 0.55, 800, 900), "在干净沙箱重放补丁")
    r.tool("verifier", "run_tests", True, "$ run_tests（干净沙箱）→ 43 passed", ms=7030)
    r.emit(
        "verifier",
        VerificationPayload(
            verdict="pass",
            evidence_ref="artifacts/evidence.json",
            tests_passed=True,
            risk_level="L1",
            display="复验通过 · 风险 L1",
            role_hint="verifier",
        ),
    )
    r.go(S.REVIEWING, "评审")
    r.call("reviewer", usage(24_000, 0.6, 1_000, 1_400), "对抗式评审：锁粒度、超时路径")
    r.emit(
        "reviewer",
        ReviewPayload(
            model=MODEL,
            variant="adversarial-thinking-max",
            findings=[
                Finding(
                    severity="minor",
                    file="src/auth/session.py",
                    line=88,
                    message="锁等待无超时",
                    suggestion="加 5s 超时",
                )
            ],
            display="评审：1 条 minor（同厂商·变体）",
            role_hint="reviewer",
        ),
    )
    r.go(S.PACKAGING, "整理证据包")
    r.go(S.DONE, "完成")
    report = FinishReport(
        summary="刷新 token 加单飞锁，并发请求复用同一次刷新，避免旧 token 被作废导致 401。",
        changes=[
            FileChange(path="src/auth/session.py", kind="modified", note="单飞锁"),
            FileChange(path="tests/tw_repro/test_issue_87.py", kind="added", note="复现测试"),
        ],
        repro=ReproRef(path="tests/tw_repro/test_issue_87.py", cmd="pytest -q tests/tw_repro/test_issue_87.py"),
        tests_run=["pytest -q"],
        tests_passed=True,
        confidence=0.82,
        open_risks=["锁等待无超时（评审 minor）"],
    )
    cr = r.cost_report()
    r.emit(
        None,
        TaskFinishedPayload(
            status="done",
            finish_report=report,
            cost_report=cr,
            display=f"完成 · ¥{cr.total_cny:.3f} · 命中 {cr.cache_hit_rate:.0%}",
            role_hint="system",
        ),
    )
    return r.events


def failure() -> list[TrajectoryEvent]:
    r = Run("failure", datetime(2026, 10, 10, 13, 5, tzinfo=UTC), 0.8)  # 北京时间 10-10 21:05（空闲）
    started(r)
    r.go(S.PLANNING, "规划")
    r.call("planner", usage(18_000, 0.0, 800, 500), "根因假设：时钟偏差导致 token 提前过期")
    r.go(S.EXECUTING, "修复")
    r.call("executor", usage(30_000, 0.8, 600, 300), "放宽过期判断")
    r.tool("executor", "edit_file", False, "edit_file：old_str 匹配到 0 处", exit_code=None)
    r.tool("executor", "edit_file", False, "edit_file：old_str 匹配到 0 处", exit_code=None)
    r.tool("executor", "edit_file", False, "edit_file：old_str 匹配到 0 处", exit_code=None)
    r.emit(
        "executor",
        LoopWarningPayload(
            signal="repeat_action",
            level=1,
            detail="相同 edit_file 3 次",
            display="⚠ 重复动作：换个思路",
            role_hint="system",
        ),
    )
    r.tool("executor", "read_file", True, "$ read_file src/auth/clock.py")
    r.call("executor", usage(36_000, 0.9, 700, 300), "改用宽限窗口")
    r.tool("executor", "edit_file", True, "$ edit_file src/auth/clock.py（+3 −1）")
    r.tool("executor", "run_tests", False, "$ run_tests → 1 failed, 41 passed", exit_code=1, ms=5900)
    r.tool("executor", "finish", True, "finish · 置信度 0.41")
    r.go(S.VERIFYING, "干净沙箱复验")
    r.call("verifier", usage(21_000, 0.5, 700, 800), "重放补丁并跑相关测试")
    r.tool("verifier", "run_tests", False, "$ run_tests（干净沙箱）→ 1 failed", exit_code=1, ms=6400)
    r.emit(
        "verifier",
        VerificationPayload(
            verdict="fail",
            evidence_ref="artifacts/evidence.json",
            tests_passed=False,
            risk_level="L2",
            display="复验未通过：test_concurrent_refresh 仍失败",
            role_hint="verifier",
        ),
    )
    r.go(S.FAILED, "失败")
    report = FinishReport(
        summary="放宽 token 过期判断（未解决并发问题）。",
        changes=[FileChange(path="src/auth/clock.py", kind="modified")],
        repro=None,
        tests_run=["pytest -q"],
        tests_passed=False,
        confidence=0.41,
        open_risks=["根因可能不是时钟偏差"],
    )
    cr = r.cost_report()
    r.emit(
        None,
        TaskFinishedPayload(
            status="failed",
            finish_report=report,
            cost_report=cr,
            display=f"失败 · ¥{cr.total_cny:.3f}",
            role_hint="system",
        ),
    )
    return r.events


def budget_exceeded() -> list[TrajectoryEvent]:
    r = Run("budget", datetime(2026, 10, 10, 14, 30, tzinfo=UTC), 0.05)  # 冒烟任务：单任务上限 ¥0.05
    started(r)
    r.go(S.EXECUTING, "修复")
    r.call("executor", usage(20_000, 0.0, 1_500, 900), "读代码（缓存未命中）")
    r.tool("executor", "read_file", True, "$ read_file src/auth/session.py")
    r.call("executor", usage(24_000, 0.1, 1_800, 1_000), "继续阅读（前缀不稳定，命中率低）")
    r.emit(
        "executor",
        LoopWarningPayload(signal="no_progress", level=1, detail="6 步无修改", display="⚠ 无进展", role_hint="system"),
    )
    r.call("executor", usage(26_000, 0.1, 1_600, 900), "尝试修复")
    r.emit(
        None,
        ErrorPayload(
            type="BudgetExceeded",
            message="max_cost_cny 已超出",
            display="超出单任务预算 ¥0.05",
            role_hint="system",
        ),
    )
    r.go(S.BUDGET_EXCEEDED, "预算耗尽")
    cr = r.cost_report()
    r.emit(
        None,
        TaskFinishedPayload(
            status="budget_exceeded",
            cost_report=cr,
            display=f"预算耗尽 · ¥{cr.total_cny:.3f} / ¥0.05",
            role_hint="system",
        ),
    )
    assert cr.total_cny > cr.budget_cny
    return r.events


def render() -> Iterator[tuple[Path, str]]:
    for name, fn in (("success", success), ("failure", failure), ("budget_exceeded", budget_exceeded)):
        yield OUT / f"{name}.jsonl", "".join(ev.to_json_line() + "\n" for ev in fn())


def main() -> int:
    check = "--check" in sys.argv
    stale = False
    for path, text in render():
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                sys.stderr.write(f"fixture 已过期：{path.name}\n")
                stale = True
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            sys.stdout.write(f"wrote {path} ({text.count(chr(10))} 行)\n")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
