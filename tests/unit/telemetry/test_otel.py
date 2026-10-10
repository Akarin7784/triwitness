# pyright: reportOptionalMemberAccess=false, reportOptionalSubscript=false, reportOperatorIssue=false
"""OTel 埋点（spec 005 AC5，W2-17）：用 golden 轨迹 + InMemorySpanExporter 断言 span 树与属性名。"""

from __future__ import annotations

from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from triwitness.core.events import TrajectoryEvent
from triwitness.telemetry import otel
from triwitness.telemetry.otel import OtelBridge, bridge_from_env
from triwitness.telemetry.trajectory import Trajectory

GOLDEN = Path(__file__).resolve().parents[3] / "evals" / "fixtures" / "events" / "recorded.jsonl"


def replay(content: bool = False) -> InMemorySpanExporter:
    exp = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exp))
    bridge = OtelBridge(provider, content=content)
    for ev in Trajectory.read_events(GOLDEN):
        bridge.observe(ev)
    return exp


def test_span_tree_from_golden_trajectory() -> None:
    spans = replay().get_finished_spans()
    by = {s.name: s for s in spans}
    names = [s.name for s in spans]
    assert names.count("chat deepseek-flash") == 5
    assert {"execute_tool list_files", "execute_tool read_file", "execute_tool run_tests", "execute_tool edit_file",
            "execute_tool finish"} <= set(names)  # fmt: skip
    task, agent = by["tw.task"], by["invoke_agent executor"]
    assert task.parent is None and agent.parent.span_id == task.context.span_id
    for s in spans:
        if s.name.startswith(("chat ", "execute_tool ")):
            assert s.parent.span_id == agent.context.span_id
            assert task.start_time <= s.start_time <= s.end_time <= task.end_time
        assert s.context.trace_id == task.context.trace_id
    chat = by["chat deepseek-flash"]
    for k in ("gen_ai.operation.name", "gen_ai.provider.name", "gen_ai.request.model", "gen_ai.usage.input_tokens",
              "gen_ai.usage.output_tokens", "tw.cache_hit_tokens", "tw.cost_cny"):  # fmt: skip
        assert k in chat.attributes, k
    assert chat.attributes["gen_ai.provider.name"] == "deepseek"
    tool = by["execute_tool read_file"]
    assert (
        tool.attributes["gen_ai.tool.name"] == "read_file"
        and tool.attributes["gen_ai.operation.name"] == "execute_tool"
    )
    for k in ("tw.task_id", "tw.config_hash", "tw.harness", "tw.harness_hash", "tw.status", "tw.cost_cny"):
        assert k in task.attributes, k
    assert task.attributes["tw.status"] == "done" and task.status.status_code != StatusCode.ERROR
    assert any(e.name == "tw.state_change" for e in task.events)


def test_no_content_by_default() -> None:
    spans = replay().get_finished_spans()
    assert all("tw.display" not in s.attributes for s in spans)
    assert all("tw.display" not in e.attributes for s in spans for e in s.events)
    assert any("tw.display" in s.attributes for s in replay(content=True).get_finished_spans())


def test_failed_tool_marks_error() -> None:
    exp = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exp))
    b = OtelBridge(provider)
    evs = Trajectory.read_events(GOLDEN)
    b.observe(evs[0])
    bad = evs[5].model_copy(update={"payload": {**evs[5].payload, "ok": False, "error_type": "not_found"}})
    b.observe(bad)
    (span,) = exp.get_finished_spans()
    assert span.status.status_code == StatusCode.ERROR and span.attributes["error.type"] == "not_found"


def test_no_endpoint_is_silent_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC5：没配置端点 → 不建 provider、不订阅，运行不报错。"""
    for k in ("TW_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(otel, "_PROVIDER", None)
    assert bridge_from_env() is None


def test_endpoint_builds_exporter_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TW_OTLP_ENDPOINT", "http://127.0.0.1:9/api/public/otel")
    monkeypatch.setattr(otel, "_PROVIDER", None)
    b = bridge_from_env()
    assert b is not None
    b.provider.shutdown()  # type: ignore[attr-defined]
    monkeypatch.setattr(otel, "_PROVIDER", None)


def test_bridge_errors_never_propagate() -> None:
    b = OtelBridge(TracerProvider())
    ev = Trajectory.read_events(GOLDEN)[0]
    b.observe(ev)
    broken = TrajectoryEvent.model_construct(**{**ev.model_dump(), "kind": "model_call", "payload": {}})
    b.observe(broken)  # payload 缺 model：内部 KeyError 被吞掉
