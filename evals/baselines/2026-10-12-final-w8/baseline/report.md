# 评测报告 · baseline

| 配置 | Agent | Resolved@1（95% CI） | 解决/有效 | 总成本 | 平均每任务 | 每解决任务 | 平均步数 | 平均耗时 | 虚假成功 | 篡改 | 缓存命中 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| final-baseline | llm | 46%（31%–63%） | 16/35 | ¥7.3819 | ¥0.2109 | ¥0.4614 | 54.8 | 1056.6s | 9 | 1 | 98% |

## 失败分类

| 配置 | resolved | infra_error | patch_not_applied | false_success | agent_error | unresolved |
|---|---|---|---|---|---|---|
| final-baseline | 16 | 0 | 0 | 9 | 5 | 5 |

## 验证器（以隐藏测试为真值）

| 配置 | 档位 | 验证数 | Verifier 判 pass | 精确率 | 召回率 | 假成功（Agent 自称） | 假成功（验证后） | 风险等级 → 实际通过率 |
|---|---|---|---|---|---|---|---|---|
| final-baseline | deterministic | 35 | 8 | 38% | 19% | 9 | 5 | L0 4 个 → 25%；L1 21 个 → 43%；L2 10 个 → 60% |

- ⚠ final-baseline：9 次虚假成功（声称修好但隐藏测试不过）
- ⚠ final-baseline：1 次疑似篡改测试（基础设施 / 削弱已有测试；Grader 已忽略这些改动）
- ⚠ final-baseline：5 次改写已有测试期望（未应用、不算篡改，建议人审）
