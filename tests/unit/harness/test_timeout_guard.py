"""超时循环守卫 + 墙钟提示（W5-13 第三轮，TB2 r2 overfull-hbox 反复跑超时的长命令后被 750s 取消）。"""

from __future__ import annotations

import json

from triwitness.core.models import Budget
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.harness.events import EventEmitter
from triwitness.harness.loop import AgentLoop, HarnessConfig
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.harness.timeouts import TimedOut, TimeoutGuard, TimeoutGuardConfig, normalize_command, similarity
from triwitness.sandbox.base import ExecResult
from triwitness.tools import ToolContext, ToolRegistry, default_tools
from triwitness.tools.base import ToolResult

LONG = "cd /tmp/tw_repro && NLW=3 ITERS=2000 SEED=1 timeout 590 perl search5.pl 2>&1 | tail -12"
FINISH = {"summary": "done", "changes": [], "tests_run": [], "tests_passed": True, "confidence": 0.5}


def on() -> TimeoutGuardConfig:
    return TimeoutGuardConfig(enabled=True)


# ---------------------------------------------------------------- 纯函数


def test_numbers_do_not_make_a_new_command() -> None:
    assert normalize_command("timeout 590 perl s.pl 40") == normalize_command("timeout  300 perl s.pl 7")
    assert similarity(LONG, LONG.replace("ITERS=2000", "ITERS=5000").replace("SEED=1", "SEED=7")) == 1.0
    assert similarity(LONG, LONG.replace("search5.pl", "search6.pl")) >= 0.8  # 换个脚本名仍是同一做法
    assert similarity(LONG, "ls -la /app") < 0.3


def test_check_block_warn_and_legit_retry() -> None:
    g = TimeoutGuard(on())
    args = json.dumps({"command": LONG})
    assert g.check("bash", args, remaining_s=None) == ("run", None)  # 还没有超时记录
    g.record("bash", args, ToolResult(ok=False, content="", error_code="timeout"), step=3)
    action, hit = g.check("bash", json.dumps({"command": LONG.replace("2000", "4000")}), remaining_s=500)
    assert action == "block" and hit is not None and (hit.step, hit.timeout_s) == (3, 120)
    # 显式调大 timeout_s 且剩余时间够：放行；剩余时间不够：仍拦
    assert g.check("bash", json.dumps({"command": LONG, "timeout_s": 400}), remaining_s=500)[0] == "run"
    assert g.check("bash", json.dumps({"command": LONG, "timeout_s": 400}), remaining_s=200)[0] == "block"
    assert g.check("bash", json.dumps({"command": "cat /tmp/x.log"}), remaining_s=500) == ("run", None)
    assert g.check("read_file", json.dumps({"path": "a"}), remaining_s=500) == ("run", None)
    warn = TimeoutGuard(TimeoutGuardConfig(enabled=True, action="warn"), timed_out=[TimedOut(LONG, 120, 1)])
    assert warn.check("bash", args, remaining_s=None)[0] == "warn"
    off = TimeoutGuard(TimeoutGuardConfig(), timed_out=[TimedOut(LONG, 120, 1)])
    assert off.check("bash", args, remaining_s=None) == ("run", None)


def test_only_timeouts_are_recorded() -> None:
    g = TimeoutGuard(on())
    assert g.record("bash", json.dumps({"command": "false"}), ToolResult(ok=False, content="", exit_code=1), 1) is None
    timed_out = ToolResult(ok=False, content="", error_code="timeout")
    t = g.record("bash", json.dumps({"command": LONG, "timeout_s": 60}), timed_out, 2)
    assert t is not None and t.timeout_s == 60 and g.timed_out == [t]


def test_timeout_capped_to_remaining_wall_time() -> None:
    g = TimeoutGuard(on())
    args, capped = g.capped_arguments("bash", json.dumps({"command": "make", "timeout_s": 600}), remaining_s=200)
    assert capped == 155 and json.loads(args) == {"command": "make", "timeout_s": 155}  # 留 reserve_s=45
    assert g.capped_arguments("bash", json.dumps({"command": "make"}), remaining_s=1000)[1] is None
    assert g.capped_arguments("bash", json.dumps({"command": "make"}), remaining_s=None)[1] is None
    assert g.capped_arguments("bash", json.dumps({"command": "make"}), remaining_s=10)[1] == 5  # 至少 5 秒


def test_wall_notes_fire_once_each() -> None:
    g = TimeoutGuard(on())
    assert g.wall_note(100, 675) is None
    assert g.wall_note(340, 675) == 0.5
    assert g.wall_note(350, 675) is None
    assert g.wall_note(650, 675) == 0.9  # 一次跨过 0.75 和 0.9：只提示最新的
    assert g.wall_note(670, 675) is None
    assert TimeoutGuard(TimeoutGuardConfig()).wall_note(670, 675) is None


def test_config_default_off_and_hash_unchanged() -> None:
    base = HarnessConfig.load()
    assert base.timeout_guard.enabled is False
    on_cfg = base.model_copy(update={"timeout_guard": on()})
    assert on_cfg.config_hash() != base.config_hash()
    # 默认值不进哈希：W2 基线等冻结配置的 harness_hash 不变（与 test_default_harness 里固定的哈希一起守住）
    assert base.config_hash() == HarnessConfig.load().config_hash()
    cfg = HarnessConfig.from_dict({"timeout_guard": {"enabled": True, "action": "warn"}})
    assert cfg.timeout_guard.enabled and cfg.timeout_guard.action == "warn"


# ---------------------------------------------------------------- AgentLoop 集成


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def make(script, *, enabled: bool = True, action: str = "block", wall: int = 675, clock: Clock | None = None,
         handler=None):  # type: ignore[no-untyped-def]  # fmt: skip
    em = EventEmitter("t_1", "r_1")
    cfg = HarnessConfig.load()
    cfg = cfg.model_copy(update={"timeout_guard": TimeoutGuardConfig(enabled=enabled, action=action)})  # type: ignore[arg-type]
    budget = Budget(max_wall_seconds=wall, max_turns=50)
    guard = TaskBudgetGuard(budget=budget, clock=clock or Clock())
    loop = AgentLoop(FakeRouter(script), ToolRegistry(default_tools()), system_prompt="x", budget=budget, emitter=em,
                     config=cfg, guard=guard)  # fmt: skip

    def timeout_long(cmd: str, sb: FakeSandbox) -> ExecResult:
        if "ITERS" in cmd:
            return ExecResult(exit_code=124, stdout="partial", stderr="", duration_ms=120_000, timed_out=True)
        return ExecResult(exit_code=0, stdout="ok", stderr="", duration_ms=1, timed_out=False)

    sb = FakeSandbox({}, exec_handler=handler or timeout_long)
    return loop, ToolContext(sandbox=sb, test_command="pytest -q"), sb


async def test_loop_reminds_then_blocks_repeated_timed_out_command() -> None:
    loop, ctx, sb = make([
        say(call("bash", command=LONG)),
        say(call("bash", command=LONG.replace("ITERS=2000", "ITERS=3000"))),  # 换个参数重跑 → 拦截
        say(call("bash", command="nohup perl search5.pl > /tmp/x.log 2>&1 &", timeout_s=10)),
        say(call("finish", **FINISH)),
    ])  # fmt: skip
    out = await loop.run("task", ctx)
    assert out.status == "finished"
    assert sum("ITERS" in c for c in sb.commands) == 1  # 第二条没有执行
    tools = [m for m in loop.messages if m.role == "tool"]
    assert tools[1].content and "已拦截" in tools[1].content
    users = [m.content or "" for m in loop.messages if m.role == "user"]
    assert sum("超时被终止" in u for u in users) == 1 and "放后台" in users[1]
    # 提醒排在该轮所有 tool 消息之后
    i = next(k for k, m in enumerate(loop.messages) if m.role == "user" and "超时被终止" in (m.content or ""))
    assert loop.messages[i - 1].role == "tool"


async def test_loop_warn_mode_runs_and_appends_warning() -> None:
    twice = [say(call("bash", command=LONG)), say(call("bash", command=LONG)), say(call("finish", **FINISH))]
    loop, ctx, sb = make(twice, action="warn")
    await loop.run("task", ctx)
    assert sum("perl" in c for c in sb.commands) == 2
    assert "[警告]" in ([m for m in loop.messages if m.role == "tool"][1].content or "")


async def test_loop_off_by_default_keeps_old_behaviour() -> None:
    twice = [say(call("bash", command=LONG)), say(call("bash", command=LONG)), say(call("finish", **FINISH))]
    loop, ctx, sb = make(twice, enabled=False)
    await loop.run("task", ctx)
    assert sum("perl" in c for c in sb.commands) == 2
    assert not any("超时被终止" in (m.content or "") for m in loop.messages if m.role == "user")


async def test_loop_wall_notes_and_timeout_cap() -> None:
    clock = Clock()
    seen: list[str] = []

    def handler(cmd: str, sb: FakeSandbox) -> ExecResult:
        seen.append(cmd)
        clock.t += 200  # 每条命令耗 200 秒
        return ExecResult(exit_code=0, stdout="ok", stderr="", duration_ms=1, timed_out=False)

    loop, ctx, _ = make([say(call("bash", command="step1")), say(call("bash", command="step2", timeout_s=600)),
                         say(call("finish", **FINISH))], clock=clock, handler=handler)  # fmt: skip
    out = await loop.run("task", ctx)
    assert out.status == "finished"
    users = [m.content or "" for m in loop.messages if m.role == "user"]
    assert any("时间提醒" in u and "（50%）" in u for u in users)  # 400/675 → 跨过 0.5
    # 第二条命令请求 600s，剩余 475s → 压到 430s，并在结果里说明；历史里的原始参数不变
    tool2 = [m for m in loop.messages if m.role == "tool"][1]
    assert "压到 430 秒" in (tool2.content or "")
    asst = [m for m in loop.messages if m.role == "assistant"][1]
    assert json.loads(asst.tool_calls[0].arguments)["timeout_s"] == 600  # type: ignore[index]
