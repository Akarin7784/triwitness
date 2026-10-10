# W3-14 后续：新确定性规则在 W2-25 补丁上的效果（¥0）

同一批 W2-25 补丁（test 35 + dev 15，去 2 个 infra 题后 48 个 attempt；真值 28 解决 / 8 假成功），只重跑验证、不重跑 Executor。
旧 = W3-14 确定性档（evals/baselines/2026-10-10-w3-verifier）；新 = 本目录（代码 e21a725 + 656e108）。对比表见 compare.md，逐 attempt 见 compare.json。

## 1. 数字

| | 旧 | 新 |
|---|---|---|
| 精确率 / 召回率 | 85% / 61% | 88% / 54% |
| 判 pass / 放过的假成功 / 误报 | 20 / 3 / 11 | 17 / 2 / 13 |
| 已知假成功拦下 | 5/8 | 6/8 |
| 回归盲区（全量/相关 0 通过） | 10 | 9（全部封顶 inconclusive 或 fail） |
| L3 | 3（2 个其实是正确补丁） | 0 |

## 2. 各条规则实际起的作用

- **去掉 `-x` + `--continue-on-collection-errors`**：旧的 10 个盲区里 6 个（dymos、isort、leanclient、lilio、msal-730、opensandbox）恢复了真实回归证据。
- **新的盲区换了来源**：全量跑完整个套件后，大仓库在 600s 内跑不完（conan、copier、faststream、marimo×2、stumpy、spikeinterface×2、huggingface_hub）。没有 `-x`，超时就成了主要的盲区原因。
- **回归盲区封顶 inconclusive**：faststream、spikeinterface-3778 从 pass 降为 inconclusive。两题都是真解决，因此误报 +2，召回下降。这是有意的代价：没跑起来的测试不能当作“无回归”。
- **相关测试回退**：只有 scrapy 一题用上了（scope = related）。选出超过 40 个文件时不回退（faststream 选出约 300 个文件，断网下整批超时）。
- **skip 单独出现降为 L2 人审**：llm-sandbox-101（假成功）、spikeinterface-3047（真解决）、copier-2646（真解决）都不再判 L3。llm-sandbox 仍然没放行（inconclusive），两个正确补丁不再被直接判失败。
- **新拦下的假成功 conan-19750 属于侥幸**：理由是“新增失败 `<timeout>`”，即补丁后的全量运行超时、基线没超时。copier-2646（真解决）也因为同样的原因判了 fail。**已知问题：只在补丁侧超时，应判 inconclusive（回归超时），不应判 fail**。按这条修正，conan 会变成 inconclusive，仍然没放行。
- **证据缺口降级（提示词 v2 + 代码兜底）只作用于模型档**，本次 ¥0 没跑。用 W3-14 的 144 次判读离线回放：conan 在 3 次里有 2 次降级（3 次全变时为 inconclusive），pyflakes-765（真解决）有 1 次降级；canvasapi 不受影响。

## 3. 仍放过的 2 个假成功

- canvasapi-716：改写并扩展了已有测试，Executor 自报 4 条风险。确定性信号只有“防作弊提示”（非阻断）。
- msal-730：回归现在跑通了，没有新失败。缺口在“Issue 未指定参数名”，只有模型档能看到。

## 4. model 档门控（thin_pass）的问题

新确定性 pass 共 17 个，**17 个都满足“证据薄”**：几乎每个 Executor 都自报未覆盖的风险，单这一条就会触发模型。按默认策略，每次 pass 都要调一次模型（约 ¥0.02/次，48 题约 ¥0.34，便宜但门控失去意义）。建议：“自报风险”单独出现不算证据薄，或者要求 ≥3 条且同时有其他信号。2 个假成功（canvasapi、msal）仍会被送到模型。

## 5. 结论

- 精确率继续上升（85% → 88%），不再有错判的 L3，假成功放过 3 → 2。召回下降主要来自盲区封顶，这是正确的保守取向。
- 下一步要修的是 **补丁侧超时的判定**（fail → inconclusive），以及 **大仓库全量回归的时间预算**（只跑相关 + 抽样，或者把超时提高到 1200s）。两者都是 ¥0 的改动。eval 工作按 Eva 的决定到此暂停。
