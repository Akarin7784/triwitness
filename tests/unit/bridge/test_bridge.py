"""tw-bridge/1（UI-10）：桌面端 ↔ 核心的逐行协议。离线：演示适配器 + 本地沙箱，¥0。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from triwitness.bridge import demo
from triwitness.bridge.stdio import PROTOCOL, Bridge
from triwitness.harness.local_run import run_local
from triwitness.sandbox.local import LocalSandboxBackend


class Harness:
    """把 Bridge 的输出收集起来；看到 approval_requested 就按 policy 回一条命令（模拟桌面端）。"""

    def __init__(self, reply: dict[str, Any] | None = None, cancel_on: str | None = None) -> None:
        self.lines: list[dict[str, Any]] = []
        self.commands: asyncio.Queue[str | None] = asyncio.Queue()
        self.reply = reply
        self.cancel_on = cancel_on

    def write(self, line: str) -> None:
        obj = json.loads(line)  # 每行都必须是合法 JSON
        self.lines.append(obj)
        if obj.get("kind") == "approval_requested" and self.reply is not None:
            cmd = {"cmd": "approve", "request_id": obj["payload"]["request_id"], **self.reply}
            self.commands.put_nowait(json.dumps(cmd))
        if self.cancel_on and obj.get("kind") == self.cancel_on:
            self.commands.put_nowait(json.dumps({"cmd": "cancel"}))

    def kinds(self) -> list[str]:
        return [x.get("kind") or f"bridge:{x['bridge']}" for x in self.lines]

    def bridge_msg(self, name: str) -> dict[str, Any]:
        return next(x for x in self.lines if x.get("bridge") == name)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    tw_home = home / ".triwitness"  # 与默认 home 同形：工作树在 ~/.triwitness/worktrees 下（曾被 deny 规则误伤）
    return {"repo": demo.ensure_repo(tmp_path / "verses"), "tw_home": tw_home}


async def drive(env: dict[str, Path], h: Harness, router: demo.DemoRouter | None = None) -> int:
    def start(approver, on_event):  # type: ignore[no-untyped-def]
        return run_local(env["repo"], demo.ISSUE, router=router or demo.DemoRouter(delay_s=0), backend="none",
                         backends=[LocalSandboxBackend(home=env["tw_home"])], home=env["tw_home"],
                         test_command=demo.test_command(), verify="deterministic", approver=approver,
                         on_event=on_event)  # fmt: skip

    return await Bridge(h.write, mode="demo", home=env["tw_home"]).run(start, h.commands)


async def test_demo_end_to_end_with_approval_card(env: dict[str, Path]) -> None:
    h = Harness(reply={"decision": "allow", "scope": "once"})
    assert await drive(env, h) == 0
    k = h.kinds()
    assert k[0] == "bridge:hello" and h.lines[0]["protocol"] == PROTOCOL and h.lines[0]["mode"] == "demo"
    assert k[1] == "bridge:run" and k[2] == "task_started"
    run = h.bridge_msg("run")
    assert Path(run["run_dir"]) == env["tw_home"] / "runs" / run["run_id"]
    assert k.index("approval_requested") < k.index("approval_resolved") < k.index("verification")
    req = next(x for x in h.lines if x.get("kind") == "approval_requested")["payload"]
    assert req["tool"] == "Bash" and "unittest" in req["action"] and req["display"].startswith("待批")
    ack = next(x for x in h.lines if x.get("bridge") == "ack")
    assert ack == {"bridge": "ack", "cmd": "approve", "request_id": req["request_id"], "ok": True}
    assert not any(x.get("kind") == "tool_call" and x["payload"].get("error_type") == "permission_denied"
                   for x in h.lines)  # fmt: skip
    res = h.bridge_msg("result")
    assert (res["status"], res["verdict"]) == ("done", "pass"), res
    assert res["risk_level"] in ("L1", "L2") and res["clean_env"] == "unverified"  # 宿主机后端：无干净环境
    assert res["pr_md"] and res["branch"] and res["cost_cny"] == 0.0
    assert res["repo"] and res["run_id"].startswith("r_")  # 开 PR 用
    seqs = [x["seq"] for x in h.lines if "seq" in x]
    assert seqs == list(range(len(seqs)))  # 事件按 seq 连续、无重复
    on_disk = (Path(res["run_dir"]) / "trajectory.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(on_disk) == len(seqs)  # 续传：磁盘上的轨迹与推流一致


async def test_deny_is_returned_to_the_model(env: dict[str, Path]) -> None:
    h = Harness(reply={"decision": "deny", "scope": "once"})
    assert await drive(env, h) == 0
    resolved = next(x for x in h.lines if x.get("kind") == "approval_resolved")["payload"]
    assert resolved["decision"] == "deny" and resolved["by"] == "user"
    assert h.bridge_msg("result")["status"] != "done"


async def test_cancel_mid_run(env: dict[str, Path]) -> None:
    h = Harness(reply=None, cancel_on="approval_requested")  # 卡在审批时取消
    assert await drive(env, h) == 0
    res = h.bridge_msg("result")
    assert res["status"] == "cancelled"
    fin = next(x for x in h.lines if x.get("kind") == "task_finished")["payload"]
    assert fin["status"] == "cancelled"
    assert any(x.get("kind") == "state_change" and x["payload"]["to"] == "cancelled" for x in h.lines)


def test_bad_commands_are_acked_not_fatal(tmp_path: Path) -> None:
    out: list[str] = []
    b = Bridge(out.append, mode="demo", home=tmp_path)
    b.handle("not json")
    b.handle(json.dumps({"cmd": "approve", "request_id": "h_x", "decision": "allow", "scope": "forever"}))
    b.handle(json.dumps({"cmd": "approve", "request_id": "h_missing", "decision": "allow"}))
    b.handle(json.dumps({"cmd": "cancel"}))
    b.handle(json.dumps({"cmd": "dance"}))
    b.handle("   ")
    acks = [json.loads(x) for x in out]
    assert [a["ok"] for a in acks] == [False, False, False, False, False]
    assert [a["cmd"] for a in acks] == [None, "approve", "approve", "cancel", "dance"]


def test_demo_repo_refuses_nonempty_non_git(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("hi", encoding="utf-8")
    with pytest.raises(FileExistsError):
        demo.ensure_repo(tmp_path)
    repo = demo.ensure_repo(tmp_path / "fresh")
    assert (repo / ".git").exists() and demo.ensure_repo(repo) == repo  # 已是仓库：原样使用


async def test_stream_deltas_reasoning_and_tool_rows(env: dict[str, Path]) -> None:
    """UI-20：交互运行写 model_delta / reasoning_delta；同一次调用的 call_id 贯穿增量、model_call、tool_call。"""
    h = Harness(reply={"decision": "allow", "scope": "session"})
    assert await drive(env, h, demo.DemoRouter(delay_s=0, effort="max")) == 0
    ev = [x for x in h.lines if "kind" in x]
    calls = [x for x in ev if x["kind"] == "model_call"]
    assert len(calls) == len(demo.script())
    first = calls[1]["payload"]["call_id"]
    text = "".join(x["payload"]["text"] for x in ev if x["kind"] == "model_delta" and x["payload"]["call_id"] == first)
    assert text == demo.script()[1].content
    think = "".join(x["payload"]["text"] for x in ev
                    if x["kind"] == "reasoning_delta" and x["payload"]["call_id"] == first)  # fmt: skip
    assert think == demo.reasoning_for(1, "max") and think
    deltas = [x for x in ev if x["kind"] in ("model_delta", "reasoning_delta") and x["payload"]["call_id"] == first]
    assert [d["payload"]["index"] for d in deltas] == list(range(len(deltas)))
    assert max(d["seq"] for d in deltas) < calls[1]["seq"]  # 增量都在 model_call 之前
    tool = next(x["payload"] for x in ev if x["kind"] == "tool_call" and x["payload"].get("call_id") == first)
    assert tool["tool"] == "read_file" and "test_verses.py" in tool["args_preview"]
    assert "unittest" in (tool.get("output_preview") or "")


async def test_thinking_off_streams_no_reasoning(env: dict[str, Path]) -> None:
    h = Harness(reply={"decision": "allow", "scope": "session"})
    assert await drive(env, h, demo.DemoRouter(delay_s=0, thinking=False)) == 0
    kinds = h.kinds()
    assert "model_delta" in kinds and "reasoning_delta" not in kinds
