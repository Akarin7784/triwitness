"""spec 011 AC（W4-09 Demo 测试）：中途 kill -9 进程 → 续跑 → 任务完成，且有副作用的工具没有重复执行。

子进程里跑真实的 InProcessOrchestrator（FakeRouter + 真实 none 后端 git worktree），在指定时刻 SIGKILL 自己；
父进程用 load_resume 续跑。副作用用一个**工作区外**的计数文件观测（工作区里的副作用会随快照回滚，看不出重复）。
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from triwitness.core.models import Budget
from triwitness.harness.config import HarnessConfig
from triwitness.harness.replay import read_journal
from triwitness.harness.resume import load_resume, run_status
from triwitness.harness.run import run_task
from triwitness.harness.testing import FakeRouter, say
from triwitness.llm.types import ToolCallSpec
from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools
from triwitness.verify.testing import make_repo

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="用 SIGKILL 模拟进程被杀")

TOOLS = ["read_file", "write_file", "edit_file", "bash", "finish"]
RUN1 = "r_01M4P0000000000000000CRASH1"
RUN2 = "r_01M4P0000000000000000CRASH2"

CHILD = textwrap.dedent(
    """
    import asyncio, json, os, signal, sys
    from pathlib import Path
    from triwitness.core.models import Budget
    from triwitness.harness.config import HarnessConfig
    from triwitness.harness.run import run_task
    from triwitness.harness.testing import FakeRouter, say
    from triwitness.llm.types import ToolCallSpec
    from triwitness.sandbox.base import SandboxSpec
    from triwitness.sandbox.local import LocalSandboxBackend
    from triwitness.telemetry.trajectory import TrajectoryRecorder
    from triwitness.tools import ToolRegistry, default_tools

    repo, home, run_dir, counter, kill_at = sys.argv[1:6]
    kill_at = int(kill_at)

    def c(i, name, **a):
        return ToolCallSpec(id=f"k{i}", name=name, arguments=json.dumps(a))

    script = [
        say(c(1, "bash", command=f"echo A >> {counter}"), c(2, "read_file", path="calc.py")),
        say(c(3, "edit_file", path="calc.py", old_str="a - b", new_str="a + b")),
        say(c(4, "bash", command=f"echo B >> {counter}")),
        say(c(5, "bash", command=f"echo C >> {counter} && kill -9 $PPID")),
    ]

    class KillingRouter(FakeRouter):
        async def complete(self, req, **kw):
            if len(self.requests) + 1 == kill_at:
                os.kill(os.getpid(), signal.SIGKILL)
            return await super().complete(req, **kw)

    async def main():
        backend = LocalSandboxBackend(home=Path(home))
        sb = await backend.create(SandboxSpec(repo=Path(repo), run_id="exec1"))
        rd = Path(run_dir)
        rec = TrajectoryRecorder("t_crash", rd.name, run_dir=rd)
        cfg = HarnessConfig.load("harness/long-context-1m.yaml")
        reg = ToolRegistry(default_tools(names=__TOOLS__))
        await run_task(recorder=rec, router=KillingRouter(script), registry=reg,
                       sandbox=sb, issue_title="add", task_prompt="add(1, 2) 应该是 3", repo="o/r", budget=Budget(),
                       config_hash="c", test_command=None, verify=None, tw_dir=str(sb.tw_dir), config=cfg,
                       progress_dir=rd)

    asyncio.run(main())
"""
).replace("__TOOLS__", repr(TOOLS))


def crash(tmp_path: Path, kill_at: int) -> tuple[Path, Path, Path, Path]:
    repo = make_repo(tmp_path, {"calc.py": "def add(a, b):\n    return a - b\n"})
    home = tmp_path / "home"
    run1 = home / "runs" / RUN1
    run1.mkdir(parents=True)
    counter = tmp_path / "side-effects.txt"
    p = subprocess.run([sys.executable, "-c", CHILD, str(repo), str(home / "sb"), str(run1), str(counter),
                        str(kill_at)], capture_output=True, text=True, timeout=120)  # fmt: skip
    assert p.returncode == -9, p.stderr[-2000:]
    return repo, home, run1, counter


async def resume_run(repo: Path, home: Path, script: list[Any]) -> tuple[Any, FakeRouter, Path]:
    state = load_resume(home, RUN1)
    run2 = home / "runs" / RUN2
    run2.mkdir()
    backend = LocalSandboxBackend(home=home / "sb2")
    sb = await backend.create(SandboxSpec(repo=repo, run_id="exec2"))
    rec = TrajectoryRecorder("t_crash", RUN2, run_dir=run2)
    router = FakeRouter(script)
    try:
        res = await run_task(recorder=rec, router=router, registry=ToolRegistry(default_tools(names=TOOLS)),
                             sandbox=sb, issue_title="add", task_prompt="add(1, 2) 应该是 3", repo="o/r",
                             budget=Budget(), config_hash="c", test_command=None, verify=None,
                             tw_dir=str(sb.tw_dir),  # type: ignore[attr-defined]
                             config=HarnessConfig.load("harness/long-context-1m.yaml"), progress_dir=run2,
                             resume=state)  # fmt: skip
    finally:
        await sb.finish("discard")  # type: ignore[attr-defined]
    return res, router, run2


def fin(i: str) -> Any:
    args = {"summary": "add 改成加法", "changes": [{"path": "calc.py", "kind": "modified"}], "tests_run": [],
            "tests_passed": True, "confidence": 0.9}  # fmt: skip
    return say(ToolCallSpec(id=i, name="finish", arguments=json.dumps(args, ensure_ascii=False)))


async def test_kill_between_steps_resume_replays_history(tmp_path: Path) -> None:
    """第 4 次模型调用时被杀（第 3 步刚结束）：重放 3 步历史，工作区带着改动，A / B 各只执行一次。"""
    repo, home, run1, counter = crash(tmp_path, kill_at=4)
    assert counter.read_text().split() == ["A", "B"]
    assert run_status(run1) == "interrupted"
    doc = json.loads((run1 / "resume" / "resume.json").read_text(encoding="utf-8"))
    assert isinstance(doc["event_seq"], int) and doc["steps"] == 3
    res, router, run2 = await resume_run(repo, home, [fin("r1")])
    assert res.status == "done", res.outcome
    assert counter.read_text().split() == ["A", "B"]  # 没有重复执行
    assert "a + b" in res.diff
    msgs = router.requests[0].messages
    # 重放：system + 任务 + 3 轮（assistant + 工具结果），最后一条是续跑说明
    tool_ids = [m.tool_call_id for m in msgs if m.role == "tool"]
    assert tool_ids == ["k1", "k2", "k3", "k4"]
    assert msgs[-1].role == "user" and 'replayed_steps="3"' in (msgs[-1].content or "")
    assert "calc.py" in (msgs[-1].content or "")
    assert "执行中被打断" not in (msgs[-1].content or "")
    assert len(router.requests) == 1  # 直接 finish：不需要重新读、重新改
    info = json.loads((run2 / "artifacts" / "replay.json").read_text(encoding="utf-8"))
    assert info["replayed_model_calls"] == 3 and info["after_checkpoint"] == []


async def test_kill_inside_side_effect_tool_is_not_rerun(tmp_path: Path) -> None:
    """第 4 步的 bash 执行中进程被杀：这一步不重放、不自动重跑，续跑说明里点名它“执行中被打断”。"""
    repo, home, run1, counter = crash(tmp_path, kill_at=99)
    assert counter.read_text().split() == ["A", "B", "C"]
    started = [e for e in read_journal(run1) if e["phase"] == "start"]
    ended = {e["call_id"] for e in read_journal(run1) if e["phase"] == "end"}
    assert [e["call_id"] for e in started] == ["k1", "k3", "k4", "k5"] and "k5" not in ended
    res, router, _ = await resume_run(repo, home, [fin("r1")])
    assert res.status == "done", res.outcome
    assert counter.read_text().split() == ["A", "B", "C"]
    msgs = router.requests[0].messages
    assert [m.tool_call_id for m in msgs if m.role == "tool"] == ["k1", "k2", "k3", "k4"]  # k5 那一步不重放
    note = msgs[-1].content or ""
    assert "bash（执行中被打断）" in note and "echo C" in note and "没有自动重跑" in note


async def test_replay_off_falls_back_to_resume_note(tmp_path: Path) -> None:
    repo, home, _, counter = crash(tmp_path, kill_at=4)
    state = load_resume(home, RUN1)
    cfg = HarnessConfig.load("harness/long-context-1m.yaml")
    cfg.orchestration.replay_on_resume = False
    run2 = home / "runs" / RUN2
    run2.mkdir()
    sb = await LocalSandboxBackend(home=home / "sb2").create(SandboxSpec(repo=repo, run_id="exec2"))
    router = FakeRouter([fin("r1")])
    try:
        res = await run_task(recorder=TrajectoryRecorder("t", RUN2, run_dir=run2), router=router,
                             registry=ToolRegistry(default_tools(names=TOOLS)), sandbox=sb, issue_title="add",
                             task_prompt="add(1, 2) 应该是 3", repo="o/r", budget=Budget(), config_hash="c",
                             test_command=None, verify=None, tw_dir=str(sb.tw_dir),  # type: ignore[attr-defined]
                             config=cfg, progress_dir=run2, resume=state)  # fmt: skip
    finally:
        await sb.finish("discard")  # type: ignore[attr-defined]
    assert res.status == "done"
    msgs = router.requests[0].messages
    assert len(msgs) == 2 and "<resume" in (msgs[1].content or "")
    assert counter.read_text().split() == ["A", "B"]
