# W3-14 verifier 三档对比 · 分析

数据：W2-25 基线 50 个 attempt（test 35 思考 high + dev 15 非思考），去掉 2 个判分环境 infra 题（ultraplot-696、xcp_d-1433）后 **48 个**，其中 46 个有补丁、2 个空补丁；隐藏测试真值：**28 个解决**（test 16 + dev 12），**8 个已知假成功**。数据表见 `tiers.md`，逐 attempt 明细见 `test/`、`dev/`。

## 1. 三档总表（以隐藏测试为真值）

| 档位 | 判 pass | 精确率 | 召回率 | 放过的假成功 | 误报（真解决被拦） | 已知 8 个假成功拦下 | 花费 |
|---|---|---|---|---|---|---|---|
| none（采信 Agent 自称） | 29 | 72%（21/29） | 75%（21/28） | 8 | 7（Agent 自己没声称成功） | 0/8 | ¥0 |
| deterministic | 20 | 85%（17/20） | 61%（17/28） | 3 | 11 | 5/8 | ¥0 |
| model（每补丁 3 次，多数票） | 18 | 89%（16/18） | 57%（16/28） | 2 | 12 | 6/8 | ¥2.94（48 补丁 × 3） |

分集合：dev 上 deterministic 与 model 都是 100% 精确 / 75% 召回（9 pass，0 放过，3 误报）；test 上 deterministic 73% / 50%，model 78% / 44%。

“判 pass”在 v0.1 里意味着“可以不经人审直接信”，所以精确率是主指标：**确定性验证把“可直接信”的错误率从 28% 降到 15%，模型档再降到 11%，代价是召回率从 75% → 61% → 57%**——被拦下的真解决补丁不会丢，只是落到 inconclusive（需要人看），不是 fail。

## 2. 8 个已知假成功

| 任务 | 集合 | deterministic | model（3 次判读） | 拦截信号 |
|---|---|---|---|---|
| crosstl-257 | dev | ✅ inconclusive L1 | ✅ inc/inc/inc | 声明审计：repro_not_tied_to_issue（复现断言的名字 Issue 里没有） |
| h-transport-materials-224 | dev | ✅ inconclusive L2 | ✅ inc/inc/inc | 声明审计：repro_not_tied_to_issue |
| django-components-489 | test | ✅ inconclusive L1 | ✅ inc/**pass**/inc | 声明审计：claim_contradicts_open_risks（自称修好但 open_risks 自己承认没覆盖） |
| loguru-1306 | test | ✅ inconclusive L2 | ✅ inc/inc/inc | 没有复现测试 + 声明审计 repro_missing / issue_underspecified |
| llm-sandbox-101 | test | ✅ **fail** L3 | ✅ fail/**inc**/fail | 防作弊：skip_or_xfail_added（同时改了已有测试） |
| msal-730 | test | ❌ pass L0 | ✅ inc/inc/inc | **模型**：指出全量回归只跑出“0 通过 / 1 错误”（沙箱断网，收集期报错 + `-x` 直接停），无回归证据；参数名是自己猜的 |
| canvasapi-716 | test | ❌ pass L2 | ❌ pass×3 | —（改了已有测试 existing_test_modified，但规则只记风险不拦） |
| conan-19750 | test | ❌ pass L0 | ❌ pass×3 | —（只修了 profile 层这一条路径，边界没覆盖） |

- **复现复跑与回归对比没有直接拦下任何一个假成功**：8 个假成功里 7 个的复现测试在干净沙箱里都“基线失败、打补丁后通过”（剩下 loguru 根本没交复现）——Agent 自写的复现测试只证明“它实现了它以为的需求”。真正起作用的是**声明审计（4 个）**、**防作弊（1 个）**和**模型（1 个）**。
- 放过的两个都属于 W2 分析里的“只修主路径 / 改已有测试迁就自己”：模型其实在 evidence_gaps 里写出了风险（canvasapi：“错误文案改了，若隐藏测试匹配旧文案可能失败”；conan：“graph.py 的断言没改，其他路径仍可能崩溃”），但 3 次都给了 pass（置信度 0.65–0.78）——**模型看见了风险却没降级**，是下一版 verifier 提示词 / 规则要补的地方。

## 3. 误报（隐藏测试通过、验证器没放行）

deterministic 11 个，model 12 个（多 spikeinterface-3778）。按原因：

| 原因 | 数量（det） | 任务 |
|---|---|---|
| 没有复现测试（repro_status = not_applicable） | 5 | icontract-297、sqlglot-7479、ro-crate-py-171、leanclient-24、stumpy-1015 |
| 声明审计 repro_not_tied_to_issue（复现文件名是占位编号等） | 3 | cyclopts-633、scrapy-7351、csv-blank-line |
| 防作弊 skip_or_xfail_added（L3 fail） | 2 | copier-2646、spikeinterface-3047 |
| Agent 自己没声称通过（claim 审计“不是 pass”但没有 flag） | 1 | dymos-1021 |
| （model 新增）全量回归收集期报错 → 模型判 inconclusive | +1 | spikeinterface-3778 |

其中 5 个“没有复现”是 Agent 自己没走 repro-first（W2 基线的 Executor 还没接 W3-04 的 submit_repro），dymos-1021 是 Agent 自己报告测试没全过，这 6 个属于**证据缺失**而不是验证器误判；接上 repro-first 后这一类应当大幅减少。真正的规则误报是 skip_or_xfail_added（3 次触发、2 次是正确补丁，精确率 1/3）和 repro_not_tied_to_issue 的“占位编号”分支。

## 4. model 档：3 次判读的稳定性

- 46 个补丁 × 3 = 138 次判读（另有 2 个 infra 题 6 次，共 144 次调用），**全部走 tool_call 路径**，0 次修复 / 0 次解析失败。
- **全票一致 44/46（96%）**，Fleiss κ = **0.95**，单次判读偏离多数票的比例 1%（2/138）。不一致的两个（django-components inc/pass/inc、llm-sandbox fail/inc/fail）多数票都没改变最终结论。
- **只取第 1 次判读的精确率 / 召回率与多数票完全相同（89% / 57%）**：在这批数据上“判 3 次”没有带来准确率收益，只花了 3 倍钱。
- 模型与确定性结论不同的 7 个补丁：更严 4 个（marimo-6819、marimo-8401 inc→fail 正确；msal-730 pass→inc 正确；spikeinterface-3778 pass→inc 误报），更松 3 个（cyclopts-633、sqlglot-7479 inc→pass 正确；lilio-58 inc→pass 错误，但最终结论取保守仍是 inconclusive）。模型单独看（不与确定性取保守）：精确率 86%、召回率 64%。

## 5. 风险等级 → 实际通过率（46 个有补丁的 attempt）

| 等级 | deterministic | model |
|---|---|---|
| L0 | 14/16 = 88% | 14/15 = 93% |
| L1 | 3/9 = 33% | 3/10 = 30% |
| L2 | 9/18 = 50% | 9/18 = 50% |
| L3 | 2/3 = 67% | 2/3 = 67% |

L0 是可信的（≥ 88%），但 **L1–L3 不单调**：L3 全部来自 skip_or_xfail_added（2/3 其实是对的），L2 混了“没有复现”这种证据缺失（与补丁好坏关系不大）。风险分级目前只适合当“L0 可放行 / 其余要人看”的二分用。

## 6. 拦截信号汇总

| 信号 | 拦下的已知假成功 | 在“没解决且没放行”的 attempt 上出现（det） |
|---|---|---|
| 复现复跑（repro rerun） | 0 | 0（复现失败 0 次） |
| 回归对比（新增失败） | 0 | 2（openhands-resolver-123、param-1117，均为 Agent 没声称成功的） |
| 防作弊 | 1（llm-sandbox） | 1 |
| 改已有测试（existing_test_modified / grader edited_paths） | 0（canvasapi 带此标记但被放过） | 单独当规则：8 次触发，4 次是正确补丁（50%） |
| 声明审计 | 4（crosstl、h-transport、django-components、loguru） | 4 |
| 没有复现测试 | 1（loguru，与声明审计重叠） | 8 |
| 模型 | 1（msal） | 1 |

**回归“盲区”**：46 个补丁里有 **10 个**（22%）全量回归只跑出“0 通过 / ≥1 错误”——任务的 `test_cmd` 是 `python -m pytest -q -x`，评测沙箱断网，有的仓库收集期就要联网（如 msal 的 test_cryptography.py 去拉 pypi.org），`-x` 让整套直接停。基线也一样报错，所以“新增失败”永远是 0，回归信号对这 10 题等于没开。模型档唯一多拦下的 msal 和唯一多出的误报 spikeinterface-3778 都是模型读到了这个盲区——**这应该由确定性检查直接标出来**（¥0），而不是靠模型。

## 7. 花费

- model 档 **¥2.9437**（dev ¥0.6902 + test ¥2.2535；infra 2 题约 ¥0.14），144 次调用，平均 ¥0.0204/次、¥0.061/补丁（3 次）；本地账本 ¥10.6761 → ¥13.6199，高峰 0。上限 ¥5 的 59%。
- 预估：期望 ¥2.18、保守 ¥3.86；实际比期望高 35%（思考输出比估的长），仍在保守值以内。
- deterministic 档 ¥0（Docker 机器时间约 12 分钟，test 35 + dev 15，3 并发）。磁盘全程 26%。

## 8. 结论与建议

1. **默认档用 deterministic（¥0）**：精确率 72% → 85%，8 个假成功拦下 5 个，已经拿到大部分收益。
2. **model 档 v0.1 不作为默认**：只多拦 1 个（而且是确定性规则也能拿到的“回归盲区”），多 1 个误报，每补丁 ¥0.02；要用就**判 1 次**（3 次判读 96% 一致、准确率无差别），只在 L0/pass 但证据薄（回归盲区、Issue 欠明确）时调用。
3. **补两条确定性规则（¥0）**：①回归盲区——全量跑出 0 通过且基线同样报错时，结论最多 inconclusive 并在证据包里写明；②修 `test_cmd`：去掉 `-x`、加 `--continue-on-collection-errors` 或用 W3-07 的相关测试选择，让断网沙箱里的回归真正跑起来。
4. **规则调参**：skip_or_xfail_added 从“阻断（L3）”降为“需人审（L2）”，除非同时削弱断言；repro_not_tied_to_issue 的“占位编号”分支不单独降级；existing_test_modified 单独做规则只有 50% 精确，维持“记风险不拦”。
5. **Verifier 提示词**：当 evidence_gaps 里出现“Issue 未指定名称 / 只修了一条路径 / 改了已有测试期望”时要求降为 inconclusive——canvasapi、conan 两个漏网的都属于这一类。
6. **召回率的大头在 Executor 而不是验证器**：12 个误报里 7 个没有复现测试（W2 Executor 还没接 repro-first）；W2-26（输入上限与“找不到下手点”）+ 接上 repro-first 后再跑一次 W3-14 对比，预计召回率能回到 70% 以上。
