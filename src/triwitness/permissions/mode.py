"""会话 / 任务内的审批模式切换，含 full_access（完全访问，原勇士模式）的激活与回退。

见 ADR-0005 §3.6、spec 006 §4.6。

只在内存里：从不写任何配置文件；应用重启 = 新 ModeController = 回到配置里的模式。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

from triwitness.core.errors import ConfigError
from triwitness.core.events import ModeChangedPayload
from triwitness.permissions.config import (
    HIGH_RISK_MODES,
    MODE_LABELS,
    UNRESTRICTED_CONFIRM_PHRASE,
    Mode,
    UnrestrictedActivation,
)


@dataclass
class ModeController:
    base_mode: Mode  # 配置文件合并出来的模式（永远不是 full_access）
    backend: str
    interactive: bool
    eval_mode: bool = False
    _override: Mode | None = None
    _scope: Literal["task", "session"] | None = None
    _task_id: str | None = None
    activation: UnrestrictedActivation | None = None
    history: list[ModeChangedPayload] = field(default_factory=list)

    @property
    def mode(self) -> Mode:
        return self._override or self.base_mode

    @property
    def high_risk(self) -> bool:
        return self.mode in HIGH_RISK_MODES

    def _emit(self, to: Mode, *, scope: Literal["task", "session"], by: str, reason: str | None) -> ModeChangedPayload:
        p = ModeChangedPayload.model_validate(
            {
                "from_mode": self.mode,
                "to_mode": to,
                "scope": scope,
                "risk": "high" if to in HIGH_RISK_MODES else "normal",
                "by": by,
                "backend": self.backend,
                "reason": reason,
                "display": f"{MODE_LABELS[self.mode]} → {MODE_LABELS[to]}",
            }
        )
        self.history.append(p)
        return p

    def activate_unrestricted(
        self, activation: UnrestrictedActivation, *, task_id: str | None = None
    ) -> ModeChangedPayload:
        """两步确认后调用。eval / CI / 非交互一律拒绝（硬底线）。"""
        if self.eval_mode or not self.interactive or os.environ.get("CI"):
            raise ConfigError("full_access（完全访问模式）在评测 / CI / 非交互运行中被禁止")
        if not activation.acknowledged:
            raise ConfigError("第一步未确认：需要勾选“我知道没有任何确认和默认拒绝”")
        if activation.typed.strip() != UNRESTRICTED_CONFIRM_PHRASE:
            raise ConfigError(f"第二步未通过：请输入“{UNRESTRICTED_CONFIRM_PHRASE}”")
        if activation.scope == "task" and not task_id:
            raise ConfigError("scope=task 需要 task_id")
        p = self._emit("full_access", scope=activation.scope, by="user", reason="两步确认通过")
        self._override, self._scope, self._task_id = "full_access", activation.scope, task_id
        self.activation = activation
        return p

    activate_full_access = activate_unrestricted

    def adopt(self, to: Mode, *, task_id: str, reason: str) -> ModeChangedPayload | None:
        """`tw run --permission-mode` 等任务级设置：load_policy 已校验过（含勇士模式两步确认），
        这里只记录切换并在任务结束时自动回退；与基础模式相同则不发事件。"""
        if to == self.mode:
            return None
        p = self._emit(to, scope="task", by="user", reason=reason)
        self._override, self._scope, self._task_id = to, "task", task_id
        return p

    def revert(
        self, *, by: Literal["user", "auto_revert"] = "user", reason: str | None = None
    ) -> ModeChangedPayload | None:
        if self._override is None:
            return None
        p = self._emit(self.base_mode, scope=self._scope or "task", by=by, reason=reason)
        self._override = self._scope = self._task_id = None
        self.activation = None
        return p

    def on_task_finished(self, task_id: str) -> ModeChangedPayload | None:
        """任务结束（任何终态）时调用；scope=task 的覆盖自动回退。"""
        if self._override is not None and self._scope == "task" and self._task_id == task_id:
            return self.revert(by="auto_revert", reason="任务结束，自动回退")
        return None
