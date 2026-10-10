# 评测报告 · 2026-10-10-w2-dev

| 配置 | Agent | Resolved@1（95% CI） | 解决/有效 | 总成本 | 平均每任务 | 每解决任务 | 平均步数 | 平均耗时 | 虚假成功 | 篡改 | 缓存命中 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline-deepseek-nothink | llm | 80%（60%–100%） | 12/15 | ¥0.8101 | ¥0.0540 | ¥0.0675 | 29.3 | 285.1s | 2 | 0 | 98% |

## 失败分类

| 配置 | resolved | infra_error | patch_not_applied | false_success | agent_error | unresolved |
|---|---|---|---|---|---|---|
| baseline-deepseek-nothink | 12 | 0 | 0 | 2 | 0 | 1 |

- ⚠ baseline-deepseek-nothink：2 次虚假成功（声称修好但隐藏测试不过）
- ⚠ baseline-deepseek-nothink：1 次改写已有测试期望（未应用、不算篡改，建议人审）
