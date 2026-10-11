"""角色路由（W1-13；spec 001 §5、§6.6–6.7；ADR-0002）。

- 按 configs/models.yaml 给每个角色选模型与思考档位；reviewer 可带 variant（同厂商异构评审）。
- vendor_policy=single_vendor（v0.1 默认）：允许同厂商评审，结果上标注 vendor_policy / variant。
- vendor_policy=cross_vendor（资金到位后）：reviewer / verifier 必须与 executor 不同厂商，否则 ConstraintViolation。
- 重试：同模型的 429 / 5xx / 超时退避重试在 HttpTransport 里（2 次，1s、4s，带抖动）；
  仍失败（LLMUnavailable）→ background 模式走回退链；eval 模式禁止回退，直接抛出。
- 白名单、空闲闸门、预算预检都在 LLMClient 里，Router 不绕过它们。
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from triwitness.config import load_config
from triwitness.core.errors import ConfigError, ConstraintViolation, LLMUnavailable
from triwitness.core.models import Role, Vendor
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.llm.adapter import split_model_id
from triwitness.llm.types import LLMRequest, LLMResponse

log = logging.getLogger(__name__)
Mode = Literal["background", "eval"]
VendorPolicy = Literal["single_vendor", "cross_vendor"]
CONSTRAINED_ROLES: tuple[Role, ...] = ("reviewer", "verifier")


class CompletionClient(Protocol):
    async def complete(
        self,
        req: LLMRequest,
        model: str,
        *,
        guard: TaskBudgetGuard | None = None,
        category: str = "dev",
        task_id: str | None = None,
    ) -> LLMResponse: ...


class RoleRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str  # "deepseek/deepseek-flash"
    thinking: bool = True
    effort: Literal["low", "high", "max"] | None = None
    variant: str | None = None
    fallback: list[str] = Field(default_factory=list)
    max_output_tokens: int | None = Field(default=None, gt=0)  # 显式 max_tokens（窗口里的输出预留，core/limits.py）


# 界面上的思考强度 → DeepSeek（thinking 开关 + reasoning_effort low / high / max）
THINKING_LEVELS: dict[str, dict[str, Any]] = {
    "off": {"thinking": False},
    "low": {"thinking": True, "effort": "low"},
    "medium": {"thinking": True, "effort": "high"},
    "high": {"thinking": True, "effort": "max"},
}
SELECTABLE_MODELS = ("deepseek-flash", "deepseek/deepseek-flash")


def executor_override(model: str | None, thinking: str | None) -> dict[str, Any]:
    """桌面端选择（模型 + 思考强度）→ RunConfig.executor 覆盖；不允许的模型直接拒绝（ADR-0002）。"""
    out: dict[str, Any] = {}
    if model and model not in SELECTABLE_MODELS:
        raise ValueError(f"模型只允许 deepseek-flash，收到 {model}")
    if model:
        out["model"] = "deepseek/deepseek-flash"
    if thinking is not None:
        if thinking not in THINKING_LEVELS:
            raise ValueError(f"思考强度只能是 {' / '.join(THINKING_LEVELS)}，收到 {thinking}")
        out.update(THINKING_LEVELS[thinking])
    return out


def vendor_of(model: str) -> Vendor:
    vendor, _ = split_model_id(model)
    if vendor not in ("deepseek", "qwen", "zhipu"):
        raise ConfigError(f"模型 {model} 必须带厂商前缀（deepseek/ qwen/ zhipu/）")
    return vendor  # type: ignore[return-value]


class Router:
    def __init__(
        self,
        routes: dict[Role, RoleRoute],
        clients: dict[Vendor, CompletionClient],
        *,
        vendor_policy: VendorPolicy = "single_vendor",
    ) -> None:
        self.routes = routes
        self.clients = clients
        self.vendor_policy: VendorPolicy = vendor_policy
        for r in routes.values():
            for m in [r.model, *r.fallback]:
                vendor_of(m)

    @classmethod
    def from_config(cls, clients: dict[Vendor, CompletionClient], cfg: dict[str, Any] | None = None) -> Router:
        cfg = cfg or load_config("models.yaml")
        routes = {role: RoleRoute.model_validate(v) for role, v in (cfg.get("roles") or {}).items()}
        policy = cfg.get("vendor_policy", "single_vendor")
        if policy not in ("single_vendor", "cross_vendor"):
            raise ConfigError(f"vendor_policy 只能是 single_vendor / cross_vendor，收到 {policy!r}")
        return cls(routes, clients, vendor_policy=policy)

    @classmethod
    def deepseek_default(cls, *, allow_peak: bool = False, executor: dict[str, Any] | None = None) -> Router:
        """v0.1 默认：单厂商，只有 DeepSeek 客户端（按 TW_LLM_MODE 选择回放 / 录制 / 真调）。

        executor：RunConfig.executor 覆盖（thinking / effort），用于“flash 思考 vs 非思考”对照。
        """
        from triwitness.llm.client import LLMClient

        router = cls.from_config({"deepseek": LLMClient.deepseek(allow_peak=allow_peak)})
        if executor:
            router.override_executor(executor)
        return router

    def override_executor(self, executor: dict[str, Any]) -> None:
        """按 RunConfig.executor 改写 executor 路由；模型仍只允许 deepseek-flash（ADR-0002）。"""
        unknown = set(executor) - {"model", "thinking", "effort"}
        if unknown:
            raise ConfigError(f"RunConfig.executor 不认识的字段：{sorted(unknown)}")
        model = executor.get("model")
        if model is not None and model not in ("deepseek-flash", "deepseek/deepseek-flash"):
            raise ConfigError(f"executor.model 只允许 deepseek-flash（ADR-0002），收到 {model}")
        base = self.route_for("executor")
        thinking = bool(executor.get("thinking", base.thinking))
        effort = executor.get("effort", base.effort) if thinking else None
        routes = dict(self.routes)
        routes["executor"] = base.model_copy(update={"thinking": thinking, "effort": effort})
        self.routes = routes

    def route_for(self, role: Role) -> RoleRoute:
        if role not in self.routes:
            raise ConfigError(f"configs/models.yaml 没有为角色 {role} 配置模型")
        return self.routes[role]

    def candidates(self, role: Role, *, executor_vendor: Vendor | None, mode: Mode) -> list[str]:
        route = self.route_for(role)
        chain = [route.model, *route.fallback]
        if self.vendor_policy == "cross_vendor" and role in CONSTRAINED_ROLES and executor_vendor:
            chain = [m for m in chain if vendor_of(m) != executor_vendor]
            if not chain:
                raise ConstraintViolation(
                    f"cross_vendor：{role} 的主选与回退链都和 executor（{executor_vendor}）同厂商"
                )
        return chain[:1] if mode == "eval" else chain

    def _apply_route(self, req: LLMRequest, route: RoleRoute) -> LLMRequest:
        upd: dict[str, Any] = {"thinking": route.thinking}
        if req.effort is None and route.effort is not None:
            upd["effort"] = route.effort
        if req.max_output_tokens is None and route.max_output_tokens is not None:
            upd["max_output_tokens"] = route.max_output_tokens
        return req.model_copy(update=upd)

    async def complete(
        self,
        req: LLMRequest,
        *,
        executor_vendor: Vendor | None = None,
        mode: Mode = "background",
        guard: TaskBudgetGuard | None = None,
        category: str = "dev",
        task_id: str | None = None,
    ) -> LLMResponse:
        route = self.route_for(req.role)
        routed = self._apply_route(req, route)
        chain = self.candidates(req.role, executor_vendor=executor_vendor, mode=mode)
        errors: list[str] = []
        for i, model in enumerate(chain):
            vendor = vendor_of(model)
            client = self.clients.get(vendor)
            if client is None:
                errors.append(f"{model}: 没有 {vendor} 客户端")
                continue
            try:
                resp = await client.complete(routed, model, guard=guard, category=category, task_id=task_id)
            except LLMUnavailable as e:
                errors.append(f"{model}: {e}")
                if mode == "eval":
                    raise  # spec 001 AC7：评测禁止回退
                log.warning("模型 %s 不可用，尝试回退链下一个", model)
                continue
            resp.role = req.role
            resp.variant = route.variant
            resp.vendor_policy = self.vendor_policy
            if i > 0:
                resp.fallback_from = chain[0]
                resp.degraded.append(f"fallback:{chain[0]}->{model}")
            if any(d.startswith("served_model_drift") for d in resp.degraded):
                log.warning("served_model 漂移：请求 %s，返回 %s", model, resp.served_model)
            return resp
        raise LLMUnavailable("回退链全部失败：" + "；".join(errors))
