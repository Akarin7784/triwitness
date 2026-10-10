# Spec 007：上下文工程

- 状态：草稿（实现已完成，待 Eva 审）｜负责人：Eva｜目标周：W2｜依赖：001、003、005
- 相关文档：04-detailed-design.md 第 3.4 节（上下文工程）；ADR-0002（预算与模型策略）

## 1. 背景

DeepSeek 的缓存命中价约为未命中的 1/10，W1 基线 95% 的输入是缓存命中。上下文管理做得不好有两种代价：一是上下文溢出或被噪声淹没，任务失败；二是每次改写历史都会让缓存前缀失效，成本成倍上升。所以这里的每个决定都要同时看**效果**和**缓存命中**。

## 2. 目标

1. **稳定前缀**：system prompt（带版本号）+ 按名字排序的工具 schema，跨任务、跨步骤逐字节不变。
2. **只追加**：两次上下文事件之间，消息列表只追加、不改写。
3. **批量清理**：超过清理线时，一次清掉一批可重新获取的旧工具结果（带回滞），而不是每步滑动窗口。
4. **压缩**：超过压缩线时，先把失败尝试写进 `.tw/NOTES.md`，再调用摘要模型，改写为 system + 任务 + 摘要 + 最近若干轮。
5. **截断**：按工具区分头尾比例；所有外部内容包进 `<untrusted>`。
6. **笔记 / 仓库地图**：`notes` 工具（`.tw/NOTES.md`）、`git` 只读工具、`repo_map`（默认关闭）。
7. **可版本化**：prompt 与 harness 配置都带版本 / 哈希，写进 `task_started` 事件，消融实验可追溯。

## 3. 非目标

- 多模态、跨任务长期记忆（W4 memory A/B）。
- 用 tokenizer 精确计数（估算 + 上一次真实 input_tokens 已够用）。
- 非 Python 语言的 repo map（v0 只解析 Python）。

## 4. 数据模型

- `prompts/<name>.md`：front matter `name`、`version`；`Prompt.tag = "executor@v2"`。
- `configs/harness/*.yaml`：`HarnessConfig`，支持 `extends` 深合并；未知键报错；`config_hash()` = 规范化 JSON 的 sha256 前 12 位。
- `ContextConfig`：`working_budget_tokens`（默认 128K）、`clear_at` 0.6、`clear_to` 0.35、`min_clear_gain` 0.1、`compact_at` 0.8、`keep_recent` 8、`keep_recent_turns`、`min_steps_between_compactions` 3、`allocation`。校验：`0 < clear_to < clear_at ≤ compact_at ≤ 1`，且固定分配之和 ≤ `clear_at × budget`。
- token 分配（默认）：

| 项 | token | 用途 |
|---|---|---|
| prefix | 12000 | system + 工具 schema + AGENTS.md（AGENTS.md 上限由此推算） |
| task | 8000 | Issue 正文上限 |
| notes | 2000 | 压缩后保留的 NOTES 片段 |
| summary | 4000 | 摘要模型 max_output |
| tool_result | 8000 | 单个工具结果上限（≈ 字符 × 3） |
| repo_map | 2000 | repo_map 默认预算 |

- 事件（tw-events/1，只增不改）：新增 `context_event`（action clear｜compact、tokens_before/after、cleared、summary_chars、notes_chars、failures_recorded、summarizer model｜fallback）；`task_started` 新增 `harness`、`harness_hash`、`prompt_versions`。

## 5. 行为细节

- **估算**：上一次响应的真实 input_tokens + 之后新增消息的字符数 / 3；改写历史后退回纯字符估算。
- **清理**：只清理成功的、可重新获取的结果（read_file、grep、list_files、repo_map、git 等），保留最近 `keep_recent` 个且至少 2 个；bash / 失败结果不清理（可能有副作用或包含错误信息）。触发后一次清到 `clear_to` 以下（回滞）；若清不到 `clear_to` 且省不到 `min_clear_gain × 预算` 就不清（交给压缩）；清理后估算 = 真实用量锚点 − 省下的量；占位符形如 `[已清理：read_file a.py L1-200，需要时重新读取]`。
- **压缩**：距上次压缩至少 3 步；先把失败的工具调用追加到 NOTES 的“失败尝试（压缩前自动记录）”一节；摘要模型 role=summarizer、thinking 关闭；失败（TriWitnessError）时退回确定性摘要，BudgetExceeded 直接上抛。保留的尾部轮数自适应：≤ 40% 预算，至少 1 轮。
- **截断**：头部比例 bash / powershell 0.3、run_tests 0.25，其他 0.6（日志的结论通常在末尾）。
- **untrusted**：Issue 与外部工具输出包进 `<untrusted source="...">`，内容中的 `</untrusted` 转义为 `<\/untrusted`；edit_file / write_file / finish 等自身产生的结果不包。
- **grep**：新增 `context`（0–5，默认 0）与 `max_matches`（≤200）；相邻块合并，不相邻用 `--` 分隔；正则错误给出提示。
- **list_files / repo_map** 尊重根目录 .gitignore（子集）并跳过 `__pycache__`。

## 6. 验收标准

- [x] AC1：同一配置下，不同任务、不同步骤的前缀哈希一致；工具 schema 按名字排序（`test_context.py`）。
- [x] AC2：Issue 与工具输出被包进 untrusted 块，伪造的闭合标签被转义；超长输出按工具比例保留头尾。
- [x] AC3：超过清理线时批量清理，回滞生效（一次清 10 条，保留最近 2 条）；低于阈值 / 不可清理时不动。
- [x] AC4：压缩前失败尝试写入 NOTES；摘要失败退回确定性摘要；BudgetExceeded 上抛。
- [x] AC5：端到端：一个长任务依次产出 clear 与 compact 两种 `context_event`，摘要调用记为 summarizer 角色。
- [x] AC6：两次上下文事件之间消息列表只追加。
- [x] AC7：模拟最长公共前缀缓存：40K 预算下批量清理命中率 ≥ 0.9，滑动窗口显著更低；回滞防止退化成逐步清理。
- [x] AC8：所有 `configs/harness/*.yaml` 可加载、哈希互不相同；坏配置报 ConfigError；`task_started` 带 harness / hash / prompt 版本。
- [x] AC9：真实运行（DeepSeek，小预算压力配置）中清理 / 压缩真实触发，且任务仍能完成、命中率不明显下降（见变更记录中的实测）。

## 7. 测试计划

- 单测：`tests/unit/harness/test_context.py`（AC1–AC8，含模拟缓存）、`tests/unit/tools/test_tools_w2.py`（notes / git / repo_map / grep / gitignore）。
- 真实验证：`configs/harness/context-stress.yaml`（32K 工作预算）跑 dev 的 SWE 题；`baseline.yaml` 跑 dev 10 题做回归。

## 8. 评测影响

- 消融配置：`no-context-mgmt`、`clear-only`、`compact-only`、`minimal-4-tools`、`repo-map`、`no-untrusted-wrap`（W2-25 / W3 消融）。
- 结果里的 `harness_hash` 区分配置；prompt 版本变动必须升版本号。

## 9. 开放问题

- repo_map 不受逐文件 Read deny 规则约束（只输出符号签名）；W3 权限复审时决定是否按 deny 规则过滤。
- grep 默认 `context=0`（04 建议 2）：为省 token；W2 消融时比较。
- 估算用字符 / 3：中文内容会偏低，压缩线留了余量；若实测溢出再引入 tokenizer。

## 10. AI 实施提示

- 改 system prompt 或工具 schema 都会让所有缓存失效：先升版本号，再在成本里预期一次冷启动。
- 不要在每步都改写历史；所有改写必须走 `ContextManager` 并发 `context_event`。

## 11. 变更记录

- 2026-10-10：初稿（W2-06），同时完成实现 W2-07（压缩 / 清理 / 截断 / untrusted）、W2-08（repo_map v0，Python）、W2-12（notes）、W2-13（git 只读）、W2-14（版本化 prompt / harness 配置）、W2-15（grep 上下文 / gitignore）。模拟发现两个设计缺陷并修正：① 小预算下清理还没有可清内容就反复压缩 → 尾部轮数自适应（≤ 40% 预算）；② keep_recent × 结果大小接近阈值时，批量清理退化为逐步清理（模拟命中率 63%）→ 增加 clear_to 回滞（89%，40K 预算下 93%）。
- 2026-10-10：真实验证（¥0.986，见 evals/baselines/2026-10-10-w2-context）。dev 10 回归 9/9 完成即解决、命中 95.3%（W1 95.2%）；32K 压力配置下清理 / 压缩真实触发（crosstl 压缩 25.7K→7.6K，模型摘要）。发现并修复：可清内容不足时清理退化成每几步清 1 条（命中降到 87–91%）→ 新增 `min_clear_gain`；清理后改用“真实用量锚点 − 省下量”估算。新增 `tw eval run --task` 过滤与 `configs/harness/context-stress.yaml`。AC9 勾选（修复后的行为尚未二次真跑，留到 W2-25 基线一并观察）。
