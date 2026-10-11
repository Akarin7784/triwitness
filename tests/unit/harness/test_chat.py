"""对话轮（0.3.1）：问候直接回复（无工具 / 无产物）、要动手才转任务、没仓库先请用户选、多轮历史、桥接往返。¥0。"""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from triwitness.bridge import demo
from triwitness.bridge.stdio import Bridge, error_message
from triwitness.core.errors import BudgetExceeded, ConfigError
from triwitness.core.ids import new_run_id, new_task_id
from triwitness.harness.chat import NO_REPO_REPLY, TOOLS, load_history, run_turn, valid_run_id, write_turn
from triwitness.harness.local_run import run_local
from triwitness.harness.testing import FakeRouter, call, say
from triwitness.llm.client import base_url
from triwitness.llm.types import LLMRequest, LLMResponse, Message, ToolCallSpec
from triwitness.prompts import load_prompt
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.telemetry.trajectory import TrajectoryRecorder

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("mock_llm", ROOT / "packaging" / "mock_llm.py")
assert _spec and _spec.loader
mock_llm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mock_llm)


class MockRouter(FakeRouter):
    """按 packaging/mock_llm.respond 的判定回复（与 CI 冒烟用的模拟服务同一套规则）。"""

    def __init__(self) -> None:
        super().__init__([])

    async def complete(self, req: LLMRequest, **kw: Any) -> LLMResponse:
        payload = {"messages": [m.model_dump(exclude_none=True) for m in req.messages], "tools": req.tools}
        r = mock_llm.respond(payload, demo.python_cmd())
        calls = None
        if r.get("tool"):
            name, args = r["tool"]
            calls = [ToolCallSpec(id=f"call_{len(self.requests)}", name=name, arguments=json.dumps(args))]
        self.script = [Message(role="assistant", content=r.get("content"), tool_calls=calls)]
        return await super().complete(req, **kw)


def new_rec(home: Path) -> tuple[TrajectoryRecorder, Path]:
    run_id = new_run_id()
    run_dir = home / "runs" / run_id
    return TrajectoryRecorder(new_task_id(), run_id, run_dir=run_dir), run_dir


async def no_work(issue: str, rec: TrajectoryRecorder) -> Any:
    raise AssertionError(f"不该开始仓库任务：{issue}")


async def chat(home: Path, text: str, router: Any, *, repo: Path | None = None, parent: str | None = None,
               work: Any = no_work) -> Any:  # fmt: skip
    rec, run_dir = new_rec(home)
    out = await run_turn(text, router=router, rec=rec, run_dir=run_dir, home=home, repo=repo, parent=parent,
                         work=work)  # fmt: skip
    return out, [e.kind for e in rec.events]


async def test_greeting_is_a_plain_reply_without_tools_or_artifacts(tmp_path: Path) -> None:
    router = FakeRouter([say(text="你好！有什么可以帮你？")])
    out, kinds = await chat(tmp_path, "你好", router)
    assert out.kind == "chat" and out.task is None and out.reply == "你好！有什么可以帮你？"
    assert kinds == ["user_message", "model_call", "turn_finished"]
    files = {p.name for p in out.run_dir.iterdir()}
    assert "turn.json" in files and "trajectory.jsonl" in files
    assert not files & {"patch.diff", "evidence.json", "finish.json", "pr.md"}  # 不产生证据 / 补丁
    req = router.requests[0]
    assert req.tools == TOOLS and req.messages[-1].content == "你好"
    assert "当前未选择仓库" in (req.messages[0].content or "")


@pytest.mark.parametrize(
    ("text", "repo", "expect"),
    [("你好", False, "chat"), ("谢谢", False, "chat"), ("你能做什么？", True, "chat"),
     ("帮我修一下 line_count 的 bug", True, "task"), ("帮我修一下 line_count 的 bug", False, "ask_repo")],
)  # fmt: skip
async def test_intent_cases(tmp_path: Path, text: str, repo: bool, expect: str) -> None:
    started: list[str] = []

    async def work(issue: str, rec: TrajectoryRecorder) -> Any:
        started.append(issue)
        raise RuntimeError("stop")  # 只验证会转任务

    r = tmp_path / "repo" if repo else None
    if expect == "task":
        with pytest.raises(RuntimeError, match="stop"):
            await chat(tmp_path, text, MockRouter(), repo=r, work=work)
        assert started and text in started[0]
        return
    out, kinds = await chat(tmp_path, text, MockRouter(), repo=r, work=work)
    assert out.kind == "chat" and not started and "task_started" not in kinds
    if expect == "ask_repo":
        assert "仓库" in out.reply


async def test_work_request_without_repo_asks_for_one_without_second_call(tmp_path: Path) -> None:
    router = FakeRouter([say(call("start_repo_work", goal="修 bug"), text="好的")])
    out, _ = await chat(tmp_path, "修一下 bug", router)
    assert out.kind == "chat" and out.reply == NO_REPO_REPLY and len(router.requests) == 1


def test_chat_prompt_states_the_rules() -> None:
    p = load_prompt("chat")
    assert p.version and "start_repo_work" in p.text and "未选择仓库" in p.text and "问候" in p.text


async def test_history_follows_parent_chain(tmp_path: Path) -> None:
    first, _ = await chat(tmp_path, "你好", FakeRouter([say(text="你好呀")]))
    router = FakeRouter([say(text="你说了你好")])
    second, _ = await chat(tmp_path, "我刚才说了什么", router, parent=first.run_id)
    msgs = [(m.role, m.content) for m in router.requests[0].messages[1:]]
    assert msgs == [("user", "你好"), ("assistant", "你好呀"), ("user", "我刚才说了什么")]
    ev = json.loads((second.run_dir / "trajectory.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert ev["kind"] == "user_message" and ev["payload"]["parent_run"] == first.run_id
    third, _ = await chat(tmp_path, "再说一次", FakeRouter([say(text="好")]), parent=second.run_id)
    assert [m.content for m in load_history(tmp_path, third.run_id)][::2] == ["你好", "我刚才说了什么", "再说一次"]


def test_history_guards(tmp_path: Path) -> None:
    assert not valid_run_id("../etc") and not valid_run_id("r_..") and valid_run_id("r_01M4N6SQ7D25BFZW24M35BK811")
    a, b = "r_01AAAAAAAAAAAAAAAAAAAAAAAA", "r_01BBBBBBBBBBBBBBBBBBBBBBBB"
    write_turn(tmp_path / "runs" / a, parent=b, user="a", assistant="A", kind="chat")
    write_turn(tmp_path / "runs" / b, parent=a, user="b", assistant="B", kind="chat")  # 环
    assert len(load_history(tmp_path, a)) == 4
    assert load_history(tmp_path, "../x") == [] and load_history(tmp_path, None) == []
    write_turn(tmp_path / "runs" / a, parent=None, user="key sk-abcdefghijklmnopqrstuvwx", assistant="", kind="chat")
    assert "sk-abcdefghijklmnopqrstuvwx" not in (tmp_path / "runs" / a / "turn.json").read_text(encoding="utf-8")


def test_base_url_override_is_local_only(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("TW_LLM_BASE_URL_OVERRIDE", raising=False)
    assert base_url() == "https://api.deepseek.com"
    monkeypatch.setenv("TW_LLM_BASE_URL_OVERRIDE", "http://127.0.0.1:9/")
    assert base_url() == "http://127.0.0.1:9" and "测试用" in capsys.readouterr().err
    monkeypatch.setenv("TW_LLM_BASE_URL_OVERRIDE", "https://evil.example.com")
    with pytest.raises(ConfigError):
        base_url()


def test_budget_error_is_safety_limit() -> None:
    msg = error_message(BudgetExceeded("单任务安全上限 max_turns 已用尽", limit="max_turns", used=100, cap=100))
    assert msg["code"] == "budget" and "max_turns" in msg["message"]


class Collect:
    def __init__(self) -> None:
        self.lines: list[dict[str, Any]] = []
        self.commands: asyncio.Queue[str | None] = asyncio.Queue()

    def write(self, line: str) -> None:
        obj = json.loads(line)
        self.lines.append(obj)
        if obj.get("kind") == "approval_requested":
            cmd = {"cmd": "approve", "request_id": obj["payload"]["request_id"], "decision": "allow"}
            self.commands.put_nowait(json.dumps(cmd))


async def bridge_turn(home: Path, text: str, router: Any, repo: Path | None = None) -> Collect:
    h = Collect()

    def start(approver, on_event):  # type: ignore[no-untyped-def]
        rec, run_dir = new_rec(home)
        rec.subscribe(on_event)

        def work(issue: str, r: TrajectoryRecorder) -> Any:
            return run_local(repo, issue, router=router, backend="none",  # type: ignore[arg-type]
                             backends=[LocalSandboxBackend(home=home)], home=home, test_command=demo.test_command(),
                             verify="deterministic", approver=approver, on_event=on_event, recorder=r)  # fmt: skip

        return run_turn(text, router=router, rec=rec, run_dir=run_dir, home=home, repo=repo, parent=None, work=work)

    assert await Bridge(h.write, mode="live", home=home).run(start, h.commands) == 0
    return h


async def test_bridge_round_trip_chat(tmp_path: Path) -> None:
    h = await bridge_turn(tmp_path / "home", "你好", FakeRouter([say(text="你好！")]))
    seq = [x.get("bridge") or x["kind"] for x in h.lines]
    assert seq == ["hello", "run", "user_message", "model_call", "turn_finished", "result"]
    res = h.lines[-1]
    assert res["kind"] == "chat" and res["reply"] == "你好！" and res["run_id"] in res["run_dir"]
    assert "verdict" not in res and "pr_md" not in res


async def test_bridge_round_trip_task_shares_one_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = demo.ensure_repo(tmp_path / "verses")
    router = FakeRouter([say(call("start_repo_work", goal="修 line_count"), text="好的"), *demo.script()])
    h = await bridge_turn(home / ".triwitness", demo.ISSUE, router, repo=repo)
    res = h.lines[-1]
    assert res["kind"] == "task" and (res["status"], res["verdict"]) == ("done", "pass"), res
    assert res["reply"] == "好的" and res["pr_md"]
    evs = [x for x in h.lines if "kind" in x and "v" in x]
    assert len({e["run_id"] for e in evs}) == 1
    kinds = [e["kind"] for e in evs]
    assert kinds[0] == "user_message" and kinds.index("task_started") > kinds.index("model_call")
    assert kinds[-1] == "turn_finished" and "task_finished" in kinds
    turn = json.loads((Path(res["run_dir"]) / "turn.json").read_text(encoding="utf-8"))
    assert turn["kind"] == "task" and "done" in turn["assistant"]


async def test_real_http_adapter_against_mock_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """真实 DeepSeek 适配器 + HTTP SSE 流式 → 本机模拟服务（与打包冒烟同一条路径）。"""
    from triwitness.llm.router import Router

    server = mock_llm.MockServer().start()
    try:
        monkeypatch.setenv("TW_HOME", str(tmp_path / "home"))
        monkeypatch.setenv("TW_LLM_BASE_URL_OVERRIDE", server.url)
        monkeypatch.setenv("TW_LLM_MODE", "record")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-real")
        router = Router.deepseek_default(allow_peak=True)
        out, kinds = await chat(tmp_path / "home", "你好", router)
        assert out.kind == "chat" and "你好" in out.reply and out.cost_cny > 0
        assert "reasoning_delta" in kinds and "model_delta" in kinds
        assert server.requests[0]["stream"] and server.requests[0]["auth"]
        assert (tmp_path / "home" / "ledger.sqlite").is_file()  # 记账
    finally:
        server.stop()
