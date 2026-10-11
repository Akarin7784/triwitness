"""模型自动审批（spec 006 v3 §4.3，auto_review 模式；参照 Codex auto-review）。

权限引擎判为 ask 的动作，在 auto_review 模式下先交给审核者：
- allow / deny → 直接执行或拒绝，写 `approval_requested` + `approval_resolved(by="reviewer")`（理由与费用进审计）；
- uncertain / 出错 / 超时 → 退回询问用户（与 ask 模式一样弹审批卡）。

审核者：
- `ModelReviewer`：deepseek-flash 非思考（role=classifier，thinking=False），一次请求 ≤ 200 输出 token，¥ 极小、记账；
- `FakeReviewer`：确定性规则，演示 / 测试用，¥0、不联网。
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from triwitness.core.events import ApprovalRequestedPayload

ReviewOutcome = Literal["allow", "deny", "uncertain"]

POLICY = """你是编程 Agent 的权限审核员。Agent 运行在用户的本地仓库里，下面这个动作被权限规则判为“需要确认”。
按以下策略判断，只输出一行 JSON：{"decision": "allow" | "deny" | "uncertain", "reason": "≤40 字中文理由"}
- allow：常规开发动作，影响限于工作区且可逆（跑测试 / 构建 / lint、安装锁文件里已有的依赖、读写工作区内文件）。
- deny：破坏性或不可逆（rm -rf 工作区外 / 根目录、git push --force、改系统配置、sudo）、外传数据或凭证
  （上传 .env / 密钥、curl 到陌生域名）、下载并执行脚本（curl | sh）、关闭安全设置。
- uncertain：信息不够、涉及网络 / 工作区外路径 / 发布 / 付费操作，或你没有把握 —— 交给用户决定。
宁可 uncertain，不要误放行。"""


@dataclass
class ReviewDecision:
    decision: ReviewOutcome
    reason: str
    cost_cny: float = 0.0
    model: str = "fake"
    response: Any = None  # ModelReviewer：原始 LLMResponse（门把它记成 role=reviewer 的 model_call，进运行成本）


class Reviewer(Protocol):
    async def review(self, req: ApprovalRequestedPayload) -> ReviewDecision: ...


# ---------------------------------------------------------------- 假审核者（演示 / 测试，¥0）

_DENY = [
    (r"\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)+(/|~|\$HOME|\.\.)", "删除工作区外 / 根目录"),
    (r"\bgit\s+push\b.*(--force|-f\b)", "强制推送会改写远端历史"),
    (r"\b(curl|wget|iwr|invoke-webrequest)\b.*\|\s*(sh|bash|iex|powershell)", "下载并执行脚本"),
    (r"\bsudo\b|\bRun[Aa]s\b", "提权操作"),
    (r"\.env\b|id_rsa|\.ssh/|credentials", "涉及凭证 / 密钥文件"),
    (r"\b(format|mkfs|diskpart|shutdown|reg\s+add|Set-ExecutionPolicy)\b", "改系统配置"),
]
_ALLOW = [
    (
        r"\b(pytest|unittest|npm\s+(run\s+)?(test|build|lint)|pnpm\s+(test|build|lint)|yarn\s+(test|build|lint)"
        r"|cargo\s+(test|build|check|clippy|fmt)|go\s+(test|build|vet)|ruff|mypy|tsc|eslint|oxlint|make\s+test)\b",
        "常规测试 / 构建 / lint",
    ),
    (r"^(python|python3|py)(\s+-m)?\s+\S+", "在工作区里运行 Python 脚本"),
    (r"\bgit\s+(add|commit|checkout\s+-b|switch\s+-c|stash)\b", "本地 git 操作，可撤销"),
    (r"\b(mkdir|touch|cp|mv)\b", "工作区内文件操作"),
]


class FakeReviewer:
    """确定性规则审核：命中危险模式 → deny；常规开发命令 → allow；其他 → uncertain（问用户）。"""

    async def review(self, req: ApprovalRequestedPayload) -> ReviewDecision:
        text = req.action
        if "工作区外" in req.reason or req.tool == "Fetch":
            return ReviewDecision("uncertain", "涉及工作区外路径或网络，交给你决定")
        for pat, why in _DENY:
            if re.search(pat, text, re.IGNORECASE):
                return ReviewDecision("deny", why)
        if req.tool == "Edit":
            return ReviewDecision("allow", "工作区内修改文件，可通过 diff 撤销")
        for pat, why in _ALLOW:
            if re.search(pat, text.strip(), re.IGNORECASE):
                return ReviewDecision("allow", why)
        return ReviewDecision("uncertain", "没有把握，交给你决定")


# ---------------------------------------------------------------- 模型审核者（deepseek-flash 非思考）


def parse_decision(text: str) -> tuple[ReviewOutcome, str]:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return "uncertain", "审核模型没有给出可解析的结论"
    try:
        data: Any = json.loads(m.group(0))
    except json.JSONDecodeError:
        return "uncertain", "审核模型输出不是 JSON"
    d = str(data.get("decision", "")).lower()
    reason = str(data.get("reason") or "")[:120]
    if d not in ("allow", "deny", "uncertain"):
        return "uncertain", "审核模型结论无效"
    return d, reason or "（无理由）"  # type: ignore[return-value]


class ModelReviewer:
    def __init__(self, router: Any, *, timeout_s: float = 20.0) -> None:
        self.router = router
        self.timeout_s = timeout_s

    async def review(self, req: ApprovalRequestedPayload) -> ReviewDecision:
        from triwitness.llm.types import LLMRequest, Message

        body = json.dumps({"tool": req.tool, "action": req.action, "reason": req.reason, "rule": req.rule,
                           "risk": req.risk, "backend": req.backend}, ensure_ascii=False)  # fmt: skip
        msgs = [Message(role="system", content=POLICY), Message(role="user", content=body)]
        llm_req = LLMRequest(role="classifier", thinking=False, max_output_tokens=200, temperature=0.0, messages=msgs)
        try:
            resp = await asyncio.wait_for(self.router.complete(llm_req, category="reviewer"), timeout=self.timeout_s)
        except Exception as e:
            return ReviewDecision(
                "uncertain", f"审核模型不可用（{type(e).__name__}），交给你决定", model="deepseek-flash"
            )
        cost = float(getattr(resp, "cost_cny", 0.0) or 0.0)
        content = getattr(getattr(resp, "message", None), "content", None) or ""
        decision, reason = parse_decision(content if isinstance(content, str) else str(content))
        return ReviewDecision(decision, reason, cost_cny=cost, model=str(getattr(resp, "model", "deepseek-flash")),
                              response=resp)  # fmt: skip
