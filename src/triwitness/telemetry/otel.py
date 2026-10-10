"""OTel 埋点（spec 005 §5.4，W2-17）：从轨迹事件流派生 span，不在循环里另插桩。

span 树：`tw.task` → `invoke_agent {role}` → `chat {model}` / `execute_tool {tool}`。
- 时间取自事件本身：chat 的开始 = ts − latency_ms，工具的开始 = ts − duration_ms；
- 属性用 OTel GenAI 语义约定（gen_ai.*，版本见 SEMCONV_URL）+ tw.* 自定义属性；
- 默认不记录任何消息内容；`TW_TRACE_CONTENT=1` 时只附加已脱敏的 `display`；
- 没配置端点（TW_OTLP_ENDPOINT / OTEL_EXPORTER_OTLP_[TRACES_]ENDPOINT）时 `bridge_from_env()` 返回 None，零开销；
- 导出出错只记日志，绝不影响任务（AC5）。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Span, Status, StatusCode

from triwitness.core.events import TrajectoryEvent

log = logging.getLogger(__name__)

SEMCONV_URL = "https://opentelemetry.io/schemas/1.44.0"  # gen_ai.* 属性按此版本（GenAI 约定仍为 development 状态）
_PROVIDER: TracerProvider | None = None


def _ns(ts: datetime, minus_ms: int = 0) -> int:
    return int(ts.timestamp() * 1e9) - minus_ms * 1_000_000


def _provider_name(model: str) -> str:
    return model.split("-", 1)[0] if "-" in model else model


def provider_from_env() -> TracerProvider | None:
    """按环境变量建一次 OTLP/HTTP 导出（Langfuse 用 OTEL_EXPORTER_OTLP_HEADERS 传鉴权）；没配置返回 None。"""
    global _PROVIDER
    if _PROVIDER is not None:
        return _PROVIDER
    base = os.environ.get("TW_OTLP_ENDPOINT")
    if not (
        base or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    ):
        return None
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # 端点不可达时每次导出最多 3s（含重试），任务结束的 force_flush 不会把评测拖慢（AC5）
    exporter = (
        OTLPSpanExporter(endpoint=f"{base.rstrip('/')}/v1/traces", timeout=3) if base else OTLPSpanExporter(timeout=3)
    )
    provider = TracerProvider(resource=Resource.create({"service.name": "triwitness"}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    _PROVIDER = provider
    return provider


def bridge_from_env() -> OtelBridge | None:
    provider = provider_from_env()
    return OtelBridge(provider) if provider is not None else None


class OtelBridge:
    """TrajectoryRecorder 的订阅者：`rec.subscribe(bridge.observe)`。"""

    def __init__(self, provider: trace.TracerProvider, *, content: bool | None = None) -> None:
        self.tracer = provider.get_tracer("triwitness", schema_url=SEMCONV_URL)
        self.provider = provider
        self.content = os.environ.get("TW_TRACE_CONTENT") == "1" if content is None else content
        self.task: Span | None = None
        self.agents: dict[str, Span] = {}

    def observe(self, ev: TrajectoryEvent) -> None:
        try:
            self._observe(ev)
        except Exception:  # 埋点出错绝不影响任务
            log.warning("OTel 埋点失败（已忽略）", exc_info=True)

    # ------------------------------------------------------------------ 内部
    def _attrs(self, ev: TrajectoryEvent, **kv: Any) -> dict[str, Any]:
        out = {k: v for k, v in kv.items() if v is not None}
        if self.content and ev.payload.get("display"):
            out["tw.display"] = ev.payload["display"]
        return out

    def _agent(self, ev: TrajectoryEvent) -> Span | None:
        if self.task is None:
            return None
        role = ev.role or "executor"
        if role not in self.agents:
            ctx = trace.set_span_in_context(self.task)
            self.agents[role] = self.tracer.start_span(
                f"invoke_agent {role}", context=ctx, start_time=_ns(ev.ts),
                attributes={"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": role},
            )  # fmt: skip
        return self.agents[role]

    def _child(self, ev: TrajectoryEvent, name: str, minus_ms: int, attrs: dict[str, Any]) -> Span | None:
        parent = self._agent(ev)
        if parent is None:
            return None
        span = self.tracer.start_span(name, context=trace.set_span_in_context(parent),
                                      start_time=_ns(ev.ts, minus_ms), attributes=attrs)  # fmt: skip
        return span

    def _observe(self, ev: TrajectoryEvent) -> None:
        p = ev.payload
        if ev.kind == "task_started":
            self.task = self.tracer.start_span("tw.task", start_time=_ns(ev.ts), attributes=self._attrs(
                ev, **{"tw.task_id": ev.task_id, "tw.run_id": ev.run_id, "tw.repo": p.get("repo"),
                       "tw.config_hash": p.get("config_hash"), "tw.harness": p.get("harness"),
                       "tw.harness_hash": p.get("harness_hash"), "tw.mode": p.get("mode")}))  # fmt: skip
            for role, ver in (p.get("prompt_versions") or {}).items():
                self.task.set_attribute(f"tw.prompt.{role}", ver)
        elif ev.kind == "model_call":
            u = p.get("usage") or {}
            span = self._child(ev, f"chat {p['model']}", int(p.get("latency_ms", 0)), self._attrs(
                ev, **{"gen_ai.operation.name": "chat", "gen_ai.provider.name": _provider_name(p["model"]),
                       "gen_ai.request.model": p["model"], "gen_ai.response.model": p.get("served_model"),
                       "gen_ai.usage.input_tokens": u.get("input_tokens"),
                       "gen_ai.usage.output_tokens": u.get("output_tokens"),
                       "gen_ai.response.finish_reasons": [p["finish_reason"]] if p.get("finish_reason") else None,
                       "tw.cache_hit_tokens": u.get("cache_hit_tokens"),
                       "tw.cache_miss_tokens": u.get("cache_miss_tokens"),
                       "tw.reasoning_tokens": u.get("reasoning_tokens"), "tw.cost_cny": p.get("cost_cny"),
                       "tw.thinking": p.get("thinking"), "tw.peak": p.get("peak")}))  # fmt: skip
            if span is not None:
                span.end(end_time=_ns(ev.ts))
        elif ev.kind == "tool_call":
            span = self._child(ev, f"execute_tool {p['tool']}", int(p.get("duration_ms", 0)), self._attrs(
                ev, **{"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": p["tool"],
                       "tw.tool.ok": p.get("ok"), "tw.tool.exit_code": p.get("exit_code"),
                       "tw.tool.truncated": p.get("truncated"), "tw.tool.permission": p.get("permission"),
                       "error.type": p.get("error_type")}))  # fmt: skip
            if span is not None:
                if not p.get("ok"):
                    span.set_status(Status(StatusCode.ERROR, p.get("error_type") or "tool_failed"))
                span.end(end_time=_ns(ev.ts))
        elif ev.kind == "task_finished":
            self._finish(ev)
        else:  # state_change / context_event / loop_warning / checkpoint / error / approval_* …：记为 span event
            target = self._agent(ev) if ev.kind in ("context_event", "loop_warning") else self.task
            if target is None:
                return
            attrs = {f"tw.{k}": v for k, v in p.items()
                     if isinstance(v, str | int | float | bool) and (k != "display" or self.content)}  # fmt: skip
            target.add_event(f"tw.{ev.kind}", attributes=attrs, timestamp=_ns(ev.ts))
            if ev.kind == "error":
                target.set_status(Status(StatusCode.ERROR, str(p.get("type"))))

    def _finish(self, ev: TrajectoryEvent) -> None:
        if self.task is None:
            return
        p = ev.payload
        cost = p.get("cost_report") or {}
        self.task.set_attribute("tw.status", p.get("status", ""))
        if "total_cny" in cost:
            self.task.set_attribute("tw.cost_cny", cost["total_cny"])
        if cost.get("cache_hit_rate") is not None:
            self.task.set_attribute("tw.cache_hit_rate", cost["cache_hit_rate"])
        if p.get("status") != "done":
            self.task.set_status(Status(StatusCode.ERROR, p.get("status", "")))
        for span in self.agents.values():
            span.end(end_time=_ns(ev.ts))
        self.task.end(end_time=_ns(ev.ts))
        self.task, self.agents = None, {}
        # 不在每个任务结束时 force_flush：BatchSpanProcessor 后台定时导出，进程退出时 TracerProvider 的 atexit
        # shutdown 会再刷一次；端点挂了时同步 flush 会让每个任务多等几秒（评测几十个任务就是几分钟，违背 AC5）
