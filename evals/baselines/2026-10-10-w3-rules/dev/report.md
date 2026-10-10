# 评测报告 · 2026-10-10-w3-rules-dev

| 配置 | Agent | Resolved@1（95% CI） | 解决/有效 | 总成本 | 平均每任务 | 每解决任务 | 平均步数 | 平均耗时 | 虚假成功 | 篡改 | 缓存命中 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline-deepseek-nothink+deterministic | llm | 80%（60%–100%） | 12/15 | ¥0.8101 | ¥0.0540 | ¥0.0675 | 29.3 | 285.1s | 2 | 0 | 98% |
| baseline-deepseek-nothink+none | llm | 80%（60%–100%） | 12/15 | ¥0.8101 | ¥0.0540 | ¥0.0675 | 29.3 | 285.1s | 2 | 0 | 98% |

## 失败分类

| 配置 | resolved | infra_error | patch_not_applied | false_success | agent_error | unresolved |
|---|---|---|---|---|---|---|
| baseline-deepseek-nothink+deterministic | 12 | 0 | 0 | 2 | 0 | 1 |
| baseline-deepseek-nothink+none | 12 | 0 | 0 | 2 | 0 | 1 |

## 验证器（以隐藏测试为真值）

| 配置 | 档位 | 验证数 | Verifier 判 pass | 精确率 | 召回率 | 假成功（Agent 自称） | 假成功（验证后） | 风险等级 → 实际通过率 |
|---|---|---|---|---|---|---|---|---|
| baseline-deepseek-nothink+deterministic | deterministic | 15 | 9 | 100% | 75% | 2 | 0 | L0 8 个 → 100%；L1 4 个 → 50%；L2 3 个 → 67% |

- ⚠ baseline-deepseek-nothink+deterministic：2 次虚假成功（声称修好但隐藏测试不过）
- ⚠ baseline-deepseek-nothink+deterministic：1 次改写已有测试期望（未应用、不算篡改，建议人审）
- ⚠ baseline-deepseek-nothink+none：2 次虚假成功（声称修好但隐藏测试不过）
- ⚠ baseline-deepseek-nothink+none：1 次改写已有测试期望（未应用、不算篡改，建议人审）
