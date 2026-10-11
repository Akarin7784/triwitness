"""结构化异常。给模型看的错误要说明“错在哪、怎么改”。"""

from __future__ import annotations

from typing import Any


class TriWitnessError(Exception):
    """所有 TriWitness 异常的基类。"""


class ConfigError(TriWitnessError):
    """配置缺失或不合法。"""


class ModelNotAllowed(TriWitnessError):
    """请求的模型不在白名单内（ADR-0002：deepseek-v4-pro 永远被拒）。"""


class ConstraintViolation(TriWitnessError):
    """路由约束无法满足（如 cross_vendor 策略下找不到异厂商模型）。"""


class LLMUnavailable(TriWitnessError):
    """重试后模型仍不可用。"""


class ContextOverflow(TriWitnessError):
    """厂商拒绝请求：输入 + max_tokens 超过模型上下文长度（HTTP 400）。AgentLoop 会压缩后重试一次。"""


class PeakHourBlocked(TriWitnessError):
    """DeepSeek 高峰时段拒绝启动 live / 批量调用（需 --allow-peak）。"""


class BudgetExceeded(TriWitnessError):
    """单任务或全局预算耗尽。"""

    def __init__(self, message: str, *, limit: str, used: float, cap: float) -> None:
        super().__init__(message)
        self.limit = limit
        self.used = used
        self.cap = cap
        # 调用后记账才触发上限时，那次已付费调用的 LLMResponse（调用方据此写轨迹、接住终止工具的提交）
        self.response: Any = None


class SandboxError(TriWitnessError):
    """沙箱创建、执行或销毁失败。"""


class ToolError(TriWitnessError):
    """工具内部错误（会被包装成 ok=False 的 ToolResult，不终止循环）。"""


class NeedsHuman(TriWitnessError):
    """需要人来决定（权限审批、ask_human、计划确认）而当前没有审批通道：任务进入 NEEDS_HUMAN。
    工具里抛出时 ToolRegistry 不把它包成工具错误，直接交给 AgentLoop。"""

    def __init__(self, request_id: str, reason: str) -> None:
        super().__init__(f"等待人工审批：{reason}")
        self.request_id = request_id


class IllegalTransition(TriWitnessError):
    """任务状态机的非法迁移（spec 010 §4）：只有迁移表里的边可以走，终态不能迁出。"""
