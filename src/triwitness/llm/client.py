"""LLMClient：一次模型调用的完整护栏链（W1-07/08/11/12/14 的最小组合）。

顺序：白名单 → 回放缓存（命中则 ¥0 返回）→ 空闲闸门 → 全局账本 + 单任务预算预检 → 真调 → 计价 → 记账。
Router（W1-13）在此之上加角色路由、回退与 eval 模式约束。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

from triwitness.core.errors import PeakHourBlocked
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.cost.ledger import GlobalLedger
from triwitness.llm.adapter import ModelAdapter, ModelPolicy
from triwitness.llm.deepseek import BASE_URL, DeepSeekAdapter
from triwitness.llm.http import HttpTransport
from triwitness.llm.pricing import estimate_cost, is_peak, next_off_peak, price_call
from triwitness.llm.replay import RecordReplayTransport, ReplayStore
from triwitness.llm.stream import current_sink, replay_deltas
from triwitness.llm.types import LLMRequest, LLMResponse

CHAT_PATH = "/chat/completions"
DEFAULT_MAX_OUTPUT_ESTIMATE = 4096


def _estimate_input_tokens(payload: dict[str, object]) -> int:
    import json

    return len(json.dumps(payload, ensure_ascii=False)) // 3 + 1  # 偏保守：约 3 字符 / token


class LLMClient:
    def __init__(
        self,
        adapter: ModelAdapter,
        transport: RecordReplayTransport,
        *,
        policy: ModelPolicy | None = None,
        ledger: GlobalLedger | None = None,
        allow_peak: bool = False,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.adapter = adapter
        self.transport = transport
        self.policy = policy or ModelPolicy.from_config()
        self.ledger = ledger
        self.allow_peak = allow_peak
        self.now = now

    @classmethod
    def deepseek(cls, *, ledger: GlobalLedger | None = None, allow_peak: bool = False) -> LLMClient:
        """按 TW_LLM_MODE 构造。replay 模式下不创建任何 HTTP 客户端。"""
        store = ReplayStore.default("deepseek")
        rr = RecordReplayTransport(store, None)
        if rr.may_hit_network:
            rr.inner = HttpTransport(BASE_URL, "DEEPSEEK_API_KEY")
            ledger = ledger or GlobalLedger()
        return cls(DeepSeekAdapter(), rr, ledger=ledger, allow_peak=allow_peak)

    def check_peak_gate(self, at: datetime) -> None:
        if is_peak(at) and not self.allow_peak:
            raise PeakHourBlocked(
                "现在是 DeepSeek 高峰时段（2× 价），默认拒绝真实调用；"
                f"下一个空闲时刻约 {next_off_peak(at):%m-%d %H:%M}（北京时间）。"
                "确需调用请显式 --allow-peak"
            )

    async def complete(
        self,
        req: LLMRequest,
        model: str,
        *,
        guard: TaskBudgetGuard | None = None,
        category: str = "dev",
        task_id: str | None = None,
    ) -> LLMResponse:
        name = self.policy.check(model)
        payload = self.adapter.build_request(name, req)
        at = self.now()
        cached = self.transport.lookup(payload)
        live = cached is None
        if live:
            if self.transport.mode == "replay":
                await self.transport.post(CHAT_PATH, payload)  # 必然抛 ReplayMiss，绝不联网
            self.check_peak_gate(at)
            est = estimate_cost(
                self.adapter.vendor,
                name,
                input_tokens=_estimate_input_tokens(payload),
                max_output_tokens=req.max_output_tokens or DEFAULT_MAX_OUTPUT_ESTIMATE,
                at=at,
            )
            if self.ledger is not None:
                self.ledger.precheck(est, category)
            if guard is not None:
                guard.precheck(est)
        elif guard is not None:
            guard.precheck(0.0)
        sink = current_sink()
        t0 = time.monotonic()
        raw = cached if cached is not None else await self.transport.post(CHAT_PATH, payload, sink=sink)
        latency = int((time.monotonic() - t0) * 1000)
        resp = self.adapter.parse_response(raw)
        if sink is not None and cached is not None:  # 回放命中：把完整回复切片送出，界面照样“流”
            replay_deltas(resp.message.reasoning_content, resp.message.content, sink)
        cost, peak = price_call(self.adapter.vendor, name, resp.usage, at)
        resp.model = name
        resp.cost_cny = cost
        resp.peak = peak
        resp.latency_ms = latency
        resp.source = "live" if live else "replay"
        resp.request_key = self.transport.last_key if live else None
        if live and self.ledger is not None:
            from triwitness.llm.pricing import pricing_version

            self.ledger.record(
                category=category,
                model=name,
                usage=resp.usage,
                cost_cny=cost,
                peak=bool(peak),
                pricing_version=pricing_version(),
                served_model=resp.served_model,
                task_id=task_id,
                at=at,
            )
        if guard is not None:
            guard.record(resp.usage, cost)
        return resp
