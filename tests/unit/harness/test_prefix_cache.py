"""前缀缓存纪律（W1-22）：系统提示 + 工具定义在不同任务 / 不同运行之间逐字节相同，消息历史只追加。"""

from __future__ import annotations

import itertools
import json
import re

from triwitness.core.models import Budget
from triwitness.harness.loop import prefix_hash
from triwitness.harness.run import run_task
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.llm.deepseek import DeepSeekAdapter
from triwitness.sandbox.base import ExecResult
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools

FIN = {"summary": "ok", "changes": [{"path": "a.py", "kind": "modified"}], "tests_passed": True, "confidence": 0.5}


async def _run(task_id: str, run_id: str, prompt: str, files: dict[str, str | bytes]) -> FakeRouter:
    router = FakeRouter([say(call("read_file", path="a.py")), say(call("run_tests")), say(call("finish", **FIN))])
    sb = FakeSandbox(files, exec_handler=lambda c, s: ExecResult(exit_code=0, stdout="==== 1 passed ====", stderr="",
                                                                 duration_ms=1, timed_out=False))  # fmt: skip
    await run_task(recorder=TrajectoryRecorder(task_id, run_id), router=router, registry=ToolRegistry(default_tools()),
                   sandbox=sb, issue_title=prompt, task_prompt=prompt, repo="r", budget=Budget(),
                   config_hash="baseline", test_command="pytest -q")  # fmt: skip
    return router


async def test_prefix_identical_across_tasks_and_runs() -> None:
    a = await _run("t_1", "r_1", "修复 IndexError", {"a.py": "x = 1\n"})
    b = await _run("t_2", "r_2", "完全不同的问题描述", {"a.py": "y = 2\n", "b.py": "z\n"})
    ha = {prefix_hash(r) for r in a.requests}
    hb = {prefix_hash(r) for r in b.requests}
    assert len(ha) == 1 and ha == hb
    # 发给 DeepSeek 的实际字节：system 消息与 tools 完全一致（工具按名称排序）
    ad = DeepSeekAdapter()
    pa = ad.build_request("deepseek-flash", a.requests[0])
    pb = ad.build_request("deepseek-flash", b.requests[-1])
    assert json.dumps(pa["messages"][0], ensure_ascii=False) == json.dumps(pb["messages"][0], ensure_ascii=False)
    assert json.dumps(pa["tools"], ensure_ascii=False) == json.dumps(pb["tools"], ensure_ascii=False)
    names = [t["function"]["name"] for t in pa["tools"]]
    assert names == sorted(names)
    # 系统提示里没有时间戳、随机 ID、绝对路径
    system = pa["messages"][0]["content"]
    assert not re.search(r"\d{4}-\d{2}-\d{2}|[0-9A-HJKMNP-TV-Z]{26}|/home/|/workspace/|[A-Z]:\\\\", system)


async def test_history_is_append_only() -> None:
    r = await _run("t_1", "r_1", "x", {"a.py": "x = 1\n"})
    dumps = [[m.model_dump(mode="json") for m in req.messages] for req in r.requests]
    for prev, cur in itertools.pairwise(dumps):
        assert cur[: len(prev)] == prev  # 之前发过的消息一字不改
