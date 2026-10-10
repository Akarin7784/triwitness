"""验证流水线（spec 008 / 009，W3）：确定性检查在前，模型判读在后。

- `anticheat`：diff 上的防作弊规则（04 §4.4）
- `claim`：完成声明审计（复现是否对应 Issue、声明与自述风险是否矛盾）
- `risk`：风险分 → L0–L3（04 §4.6，configs/policies/risk.yaml）
- `rerun`：干净环境复跑复现测试（基线必须失败、修复后必须通过）与回归对比
- `evidence`：组装 Evidence、渲染 PR 正文
"""

from triwitness.verify.claim import ClaimVerdict, verify_claim
from triwitness.verify.evidence import build_evidence, render_pr

__all__ = ["ClaimVerdict", "build_evidence", "render_pr", "verify_claim"]
