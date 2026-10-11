# W5-13 外部对照 · Terminal-Bench 2.0 子集 × TriWitness（Harbor）· 2026-10-12（Eva 本机）

- **是什么**：不是 OFAT 消融，是 W5-13 的外部对照。用 `scripts/windows/run-harbor-tb2.ps1` 在 Eva 电脑的 WSL2 里跑，Harbor 0.24.0 + terminal-bench-2@`2fd12b88aafd`。
  Agent 是 TriWitness（`harness=baseline`：文件 + bash 工具，无快照 / diff），模型 deepseek-flash 非思考；代码是当时的 main（`080503b`，agent 版本 0.3.2a1）。
- **跑了什么**：
  - 冒烟 1 次：fix-git（job `2026-10-12__03-08-52`）。
  - 全量 1 次：脚本内置 10 题各 1 次，并发 2（job `2026-10-12__03-10-36`，03:10:37–03:26:09 北京时间，墙钟 15 分 32 秒）。
- **完整性**：全量 10/10 完成，Harbor 记 0 异常、0 重试、0 取消；冒烟 1/1 完成。这是**完整**的一轮，每题 1 次，没有重复。
- **花费**：账本类别 `harbor-external` 共 338 次调用，**¥0.6893**（全量 ¥0.6614 + 冒烟 ¥0.0279），高峰调用 0，served_model 全部 deepseek-flash；与 Agent 上报一致。
- **入库内容**：`report.md` / `summary.json`（脚本原样输出，10/11 把冒烟也算进去了）、`analysis.json`（逐次试验：账本、tokens、缓存命中、步数、工具、耗时）、两个 job 的 `config.json` / `result.json`。
  轨迹、artifacts、verifier 输出和账本原件不入库。结果包里没有密钥（`redact_secrets` 规则与 `sk-` / Bearer 等 0 命中）。

## 结果（全量 10 题 × 1 次）

| 指标 | 值 |
|---|---|
| 解决 | **9/10 = 90%**（Wilson 95%：60%–98%；bootstrap 70%–100%） |
| 含冒烟（fix-git 两次都过） | 10/11 = 91%（62%–98%） |
| 花费 | ¥0.661，每题中位 ¥0.045，最高 ¥0.160（cobol-modernization） |
| tokens | 输入 5.11M（缓存命中 4.99M = **97.5%**），输出 109k，调用 318 次 |
| 步数 | 中位 21.5，最多 70 |
| 耗时 | Agent 执行中位 68s、最长 386s；单题含建环境和 verifier 合计 1781s（并发 2，墙钟 15.5 分钟） |
| 上下文清理 / 压缩 | 0 次（baseline harness 没开；最长一题 70 步也没碰到上下文上限） |

| 题 | 奖励 | 步数 | ¥ | 命中 | Agent 秒 |
|---|---|---|---|---|---|
| cobol-modernization | 1 | 70 | 0.160 | 98.6% | 386 |
| constraints-scheduling | 1 | 19 | 0.042 | 95.7% | 46 |
| fix-git（全量 / 冒烟） | 1 / 1 | 22 / 20 | 0.031 / 0.028 | 95.4% / 95.2% | 38 / 33 |
| git-leak-recovery | 1 | 41 | 0.066 | 97.3% | 141 |
| multi-source-data-merger | 1 | 21 | 0.049 | 96.2% | 71 |
| nginx-request-logging | 1 | 19 | 0.041 | 94.7% | 64 |
| openssl-selfsigned-cert | 1 | 15 | 0.025 | 95.3% | 40 |
| overfull-hbox | 1 | 52 | 0.112 | 97.9% | 130 |
| **polyglot-c-py** | **0** | 41 | 0.115 | 97.5% | 206 |
| prove-plus-comm | 1 | 18 | 0.022 | 96.1% | 37 |

## 唯一的失败不是能力问题，是我们自己的复现测试残留

polyglot-c-py 的 verifier 第一条断言是 `/app/polyglot` 里只能有 `main.py.c`，实际是 `['main.py.c', 'tests']`。
Agent 按 executor 提示把复现测试写到了 `/app/polyglot/tests/tw_repro/test_issue_1.py`，结束时没删。程序本身两种语言都跑对了。
11 次试验**全部**留下了 `tests/tw_repro/`，只有这一题的检查会看目录内容。

## 能下和不能下的结论

- **能说**：TriWitness 的 Harbor 适配可以端到端工作（建环境 → Agent → verifier，0 异常）；在这 10 道偏容易的 TB2 题上，flash 非思考每题约 ¥0.07、缓存命中约 97%；
  这次唯一的失败来自 harness 行为（复现测试残留），可以修。
- **不能说**：
  - “TriWitness 在 Terminal-Bench 2.0 上是 90%”：子集是挑过的（easy 全部 4 题 + 6 道专家估时 ≤ 30 分钟的 medium），不能代表全集，也不能和公开榜单比。
  - 每题只有 1 次，n = 10：Wilson 区间 60%–98%。和其他配置比较时，独立样本要差约 63 个百分点才看得出（mde_independent）；同题配对约 40 个百分点，每题 3 次约 23 个百分点（mde_paired）。
  - 只跑了一个配置，没有对照组，所以不做 McNemar / Holm；也不和 dev / test 的 SWE 类结果直接比。

## 顺带发现（不影响上面的数字）

1. **复现测试残留**（见上）：外部任务（Harbor）没有“仓库”概念，复现测试写进工作目录会污染产物。
2. **轨迹里 `thinking: true` 记错了**：request / model_call 事件记的是 `LLMRequest.thinking` 的默认值 True，不是路由实际生效的值。
   实际是非思考：335 份可解析的回复都没有 reasoning_tokens / reasoning_content，花费也是非思考水平。这个问题从 W1 起就有，影响所有非思考运行的轨迹分析。
3. **artifact 脱敏会弄坏 JSON**：git-leak-recovery 有 3 份 response artifact 不是合法 JSON，脱敏把 `secret=...` 一直替换到了字符串的结束引号。不影响账本和判分，但会影响离线分析。

## 复算

`analysis.json` 由结果包（`harbor/2026-*/*/result.json`、各试验 `agent/tw/trajectory.jsonl`、`ledger.sqlite`）算出，统计用 `triwitness.eval.ablation`（wilson / bootstrap_ci / mde_*）。
