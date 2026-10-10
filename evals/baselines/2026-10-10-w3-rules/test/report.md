# 评测报告 · 2026-10-10-w3-rules-test

| 配置 | Agent | Resolved@1（95% CI） | 解决/有效 | 总成本 | 平均每任务 | 每解决任务 | 平均步数 | 平均耗时 | 虚假成功 | 篡改 | 缓存命中 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline-deepseek+deterministic | llm | 48%（33%–67%） | 16/33 | ¥8.1596 | ¥0.2331 | ¥0.5100 | 53.3 | 520.1s | 6 | 3 | 97% |
| baseline-deepseek+none | llm | 48%（33%–67%） | 16/33 | ¥8.1596 | ¥0.2331 | ¥0.5100 | 53.3 | 520.1s | 6 | 3 | 97% |

## 失败分类

| 配置 | resolved | infra_error | patch_not_applied | false_success | agent_error | unresolved |
|---|---|---|---|---|---|---|
| baseline-deepseek+deterministic | 16 | 2 | 0 | 6 | 11 | 0 |
| baseline-deepseek+none | 16 | 2 | 0 | 6 | 11 | 0 |

## 验证器（以隐藏测试为真值）

| 配置 | 档位 | 验证数 | Verifier 判 pass | 精确率 | 召回率 | 假成功（Agent 自称） | 假成功（验证后） | 风险等级 → 实际通过率 |
|---|---|---|---|---|---|---|---|---|
| baseline-deepseek+deterministic | deterministic | 33 | 8 | 75% | 38% | 6 | 2 | L0 9 个 → 56%；L1 7 个 → 43%；L2 17 个 → 47% |

## 基础设施错误（不计入分母）

- `baseline-deepseek+deterministic/swe-ultraplot-696/1`：单任务预算 max_input_tokens 已用尽：3.045e+06 / 3e+06 | infra（W2-25 复核）：判分环境 uid 1000 的 HOME=/ 不可写，参考解在 Grader 条件下 reward=0（任务校验用 root 才通过）；44f9f41 修复后离线重判 ultraplot：resolved，仅供参考，不计入本基线
- `baseline-deepseek+deterministic/swe-xcp_d-1433/1`：单任务预算 max_input_tokens 已用尽：3.073e+06 / 3e+06 | infra（W2-25 复核）：判分环境 uid 1000 的 HOME=/ 不可写，参考解在 Grader 条件下 reward=0（任务校验用 root 才通过）；44f9f41 修复后离线重判 xcp_d：unresolved（2 failed），仅供参考，不计入本基线
- `baseline-deepseek+none/swe-ultraplot-696/1`：单任务预算 max_input_tokens 已用尽：3.045e+06 / 3e+06 | infra（W2-25 复核）：判分环境 uid 1000 的 HOME=/ 不可写，参考解在 Grader 条件下 reward=0（任务校验用 root 才通过）；44f9f41 修复后离线重判 ultraplot：resolved，仅供参考，不计入本基线
- `baseline-deepseek+none/swe-xcp_d-1433/1`：单任务预算 max_input_tokens 已用尽：3.073e+06 / 3e+06 | infra（W2-25 复核）：判分环境 uid 1000 的 HOME=/ 不可写，参考解在 Grader 条件下 reward=0（任务校验用 root 才通过）；44f9f41 修复后离线重判 xcp_d：unresolved（2 failed），仅供参考，不计入本基线

- ⚠ baseline-deepseek+deterministic：6 次虚假成功（声称修好但隐藏测试不过）
- ⚠ baseline-deepseek+deterministic：3 次疑似篡改测试（基础设施 / 削弱已有测试；Grader 已忽略这些改动）
- ⚠ baseline-deepseek+deterministic：6 次改写已有测试期望（未应用、不算篡改，建议人审）
- ⚠ baseline-deepseek+none：6 次虚假成功（声称修好但隐藏测试不过）
- ⚠ baseline-deepseek+none：3 次疑似篡改测试（基础设施 / 削弱已有测试；Grader 已忽略这些改动）
- ⚠ baseline-deepseek+none：6 次改写已有测试期望（未应用、不算篡改，建议人审）
- ⚠ 4 个基础设施错误，单独列出、不计入分母
