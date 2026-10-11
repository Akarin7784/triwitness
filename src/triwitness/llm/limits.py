"""按 configs/models.yaml 查模型窗口、最大输出与角色输出预留，推导输入硬上限与 auto 工作预算。"""

from __future__ import annotations

from typing import Any

from triwitness.config import load_config
from triwitness.core.errors import ConfigError
from triwitness.core.limits import FALLBACK, FALLBACK_ROLE_OUTPUT, ModelLimits, hard_limit_for


def _models_cfg() -> dict[str, Any]:
    try:
        return load_config("models.yaml")
    except ConfigError:
        return {}


def _bare(model: str) -> str:
    return model.split("/", 1)[1] if "/" in model else model


def model_limits(model: str) -> ModelLimits:
    """按模型名（可带厂商前缀，可是别名）查窗口与最大输出；查不到退回 deepseek-flash 的官方值。"""
    name = _bare(model)
    for key, v in (_models_cfg().get("models") or {}).items():
        if isinstance(v, dict) and (name == key or name in (v.get("aliases") or [])):
            return ModelLimits(int(v.get("context_window", FALLBACK.context_window)),
                               int(v.get("max_output", FALLBACK.max_output)))  # fmt: skip
    return FALLBACK


def _role(role: str) -> dict[str, Any]:
    r = (_models_cfg().get("roles") or {}).get(role)
    return r if isinstance(r, dict) else {}


def role_model(role: str) -> str:
    return str(_role(role).get("model", "deepseek/deepseek-flash"))


def role_max_output(role: str) -> int:
    """角色单次输出预留（Router 显式写进请求的 max_tokens）。"""
    v = _role(role).get("max_output_tokens")
    lim = model_limits(role_model(role))
    return min(int(v) if v else FALLBACK_ROLE_OUTPUT, lim.max_output)


def hard_input_limit(role: str = "executor") -> int:
    return hard_limit_for(model_limits(role_model(role)).context_window, role_max_output(role))


def auto_working_budget(role: str = "executor") -> int:
    return hard_input_limit(role)


__all__ = ["auto_working_budget", "hard_input_limit", "model_limits", "role_max_output", "role_model"]
