# 评测报告 · orchestrated

| 配置 | Agent | Resolved@1（95% CI） | 解决/有效 | 总成本 | 平均每任务 | 每解决任务 | 平均步数 | 平均耗时 | 虚假成功 | 篡改 | 缓存命中 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| final-orchestrated | llm | 54%（37%–71%） | 19/35 | ¥8.4901 | ¥0.2426 | ¥0.4468 | 42 | 1283.9s | 8 | 1 | 96% |

## 失败分类

| 配置 | resolved | infra_error | patch_not_applied | false_success | agent_error | unresolved |
|---|---|---|---|---|---|---|
| final-orchestrated | 19 | 0 | 0 | 8 | 3 | 5 |

## 验证器（以隐藏测试为真值）

| 配置 | 档位 | 验证数 | Verifier 判 pass | 精确率 | 召回率 | 假成功（Agent 自称） | 假成功（验证后） | 风险等级 → 实际通过率 |
|---|---|---|---|---|---|---|---|---|
| final-orchestrated | deterministic | 35 | 9 | 56% | 26% | 8 | 4 | L0 5 个 → 60%；L1 18 个 → 50%；L2 12 个 → 58% |

- ⚠ final-orchestrated：8 次虚假成功（声称修好但隐藏测试不过）
- ⚠ final-orchestrated：1 次疑似篡改测试（基础设施 / 削弱已有测试；Grader 已忽略这些改动）
- ⚠ final-orchestrated：9 次改写已有测试期望（未应用、不算篡改，建议人审）
