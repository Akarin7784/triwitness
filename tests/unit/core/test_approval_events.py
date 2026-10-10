"""tw-events/1 新增 approval_requested / approval_resolved（spec 006 §7，只增不改）。"""

from __future__ import annotations

from datetime import UTC, datetime

from triwitness.core.events import (
    ApprovalRequestedPayload,
    ApprovalResolvedPayload,
    ToolCallPayload,
    VerificationPayload,
    make_event,
    parse_event_line,
)


def _ev(payload, seq: int = 1):
    return make_event(
        seq=seq, ts=datetime(2026, 10, 10, 12, tzinfo=UTC), task_id="t1", run_id="r1", role="executor", payload=payload
    )


def test_approval_round_trip() -> None:
    req = ApprovalRequestedPayload(
        request_id="ap1",
        tool="Bash",
        action="git push origin tw/r1",
        reason="命中 ask 规则",
        rule="Bash(git push *)",
        rule_source="default",
        risk="L2",
        suggested_rule="Bash(git push origin tw/*)",
    )
    ev = _ev(req)
    assert ev.kind == "approval_requested"
    back = parse_event_line(ev.model_dump_json(by_alias=True))
    assert back.typed_payload() == req
    res = _ev(ApprovalResolvedPayload(request_id="ap1", decision="deny", by="policy", comment="eval：ask 视为 deny"), 2)
    assert parse_event_line(res.model_dump_json(by_alias=True)).kind == "approval_resolved"


def test_additive_fields_default_none() -> None:
    assert ToolCallPayload(tool="bash", ok=True, duration_ms=1).permission is None
    v = VerificationPayload(verdict="inconclusive", clean_env="unverified", unverified_reason="no_sandbox")
    assert _ev(v).kind == "verification"
    assert VerificationPayload(verdict="pass").clean_env is None
