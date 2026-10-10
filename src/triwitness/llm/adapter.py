"""ModelAdapter 协议与模型白名单（spec 001 §5、§6.7；ADR-0002）。

所有厂商差异只能写在 llm/ 里；harness 只看到 LLMRequest / LLMResponse。
"""

from __future__ import annotations

from typing import Any, Protocol

from triwitness.config import load_config
from triwitness.core.errors import ModelNotAllowed
from triwitness.core.models import Vendor
from triwitness.llm.types import Caps, LLMRequest, LLMResponse, Message, Usage


class ModelAdapter(Protocol):
    vendor: Vendor

    def capabilities(self, model: str) -> Caps: ...
    def prepare_history(self, msgs: list[Message], has_tools: bool) -> list[dict[str, Any]]: ...
    def build_request(self, model: str, req: LLMRequest) -> dict[str, Any]: ...
    def parse_response(self, raw: dict[str, Any]) -> LLMResponse: ...
    def normalize_usage(self, raw_usage: dict[str, Any]) -> Usage: ...


def split_model_id(model: str) -> tuple[str | None, str]:
    """ "deepseek/deepseek-flash" → ("deepseek", "deepseek-flash")；无前缀时 vendor 为 None。"""
    if "/" in model:
        vendor, name = model.split("/", 1)
        return vendor, name
    return None, model


class ModelPolicy:
    """白名单（configs/models.yaml）。deepseek-v4-pro 不论配置如何都拒绝。"""

    HARD_DENY = frozenset({"deepseek-v4-pro"})

    def __init__(self, allowed: list[str], denied: list[str] | None = None) -> None:
        self.allowed = frozenset(allowed)
        self.denied = frozenset(denied or []) | self.HARD_DENY

    @classmethod
    def from_config(cls) -> ModelPolicy:
        cfg = load_config("models.yaml")
        return cls(list(cfg.get("allowed_models", [])), list(cfg.get("denied_models", [])))

    def check(self, model: str) -> str:
        """返回去掉厂商前缀后的模型名；不允许时抛 ModelNotAllowed。"""
        _, name = split_model_id(model)
        if name in self.denied or name.startswith("deepseek-v4-pro"):
            raise ModelNotAllowed(f"模型 {name} 被禁止（ADR-0002：v0.1 只允许 deepseek-flash）")
        if name not in self.allowed:
            raise ModelNotAllowed(f"模型 {name} 不在白名单 {sorted(self.allowed)} 中")
        return name
