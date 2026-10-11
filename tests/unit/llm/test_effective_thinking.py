"""W5-13 发现：轨迹里的 thinking 记的是 LLMRequest.thinking 的默认值（非思考运行也记 true）。现在记实际发出去的值。"""

from __future__ import annotations

import json
from typing import Any

from triwitness.llm import cases
from triwitness.llm.types import LLMRequest, LLMResponse, Message, Usage, effective_thinking

from .helpers import replay_client


def _resp(thinking: bool | None) -> LLMResponse:
    return LLMResponse(message=Message(role="assistant", content="x"), usage=Usage(), served_model="deepseek-flash",
                       finish_reason="stop", raw={}, thinking=thinking)  # fmt: skip


def test_effective_thinking_prefers_response_then_override() -> None:
    req = LLMRequest(role="executor", messages=[Message(role="user", content="hi")])
    assert req.thinking is True  # 请求默认值
    assert effective_thinking(req, _resp(False)) is False
    assert effective_thinking(req.model_copy(update={"thinking_override": False}), _resp(None)) is False
    assert effective_thinking(req, _resp(None)) is True


async def test_client_records_what_was_sent() -> None:
    req = cases.text_nonthinking()
    resp = await replay_client().complete(req, cases.MODEL)
    assert req.thinking is False and resp.thinking is False


async def test_trajectory_records_effective_flag(tmp_path: Any) -> None:
    """checklist 评审变体（thinking_override=False）：model_call 事件与请求附件都记 false。"""
    from ..roles.test_reviewer_force_submit import READ, SUBMIT, _cfg, _review

    _, router, rec = await _review([READ, SUBMIT], _cfg(5), tmp_path)
    assert all(r.thinking is True for r in router.requests)  # 请求上的默认值没变
    calls = [e for e in rec.events if e.kind == "model_call"]
    payloads = [e.payload if isinstance(e.payload, dict) else e.payload.model_dump() for e in calls]
    assert payloads and all(p["thinking"] is False for p in payloads)
    for p in payloads:
        art = json.loads((tmp_path / "run" / p["request_ref"]).read_text(encoding="utf-8"))
        assert art["thinking"] is False
