# W5-13 外部对照第三轮 · Terminal-Bench 2.0 子集 × TriWitness（Harbor）· 10 题 × 3 次 · 2026-10-12（box）

- **是什么**：第二轮（`../2026-10-12-harbor-tb2-r2/`，26/30）之后，带上超时循环守卫的重复跑。同一个 10 题子集、Harbor 0.24.0 + terminal-bench-2@`2fd12b88aafd`，Agent 仍是 TriWitness `harness=baseline` + deepseek-flash 非思考。代码以 `731a2de`（`timeout_guard` + 按题目时间预算推导步数/墙钟）为准，入库时 tip 在 `f5e5c06` 附近。
- **超时守卫**：Harbor Agent 默认 `timeout_guard=block`（拦截近似重跑超时命令、按剩余墙钟压 timeout_s、墙钟里程碑提醒）。
- **在哪跑**：box（Linux）。并发 2。
- **墙钟**：北京时间约 13:32–14:31（约 59 分钟）；`rep0` / `rep1` / `rep2` 墙钟约 18.5 / 22.7 / 16.6 分钟。Eva 批准 `--allow-peak`，14:00 后进入 DeepSeek 高峰价（账本记高峰调用 496/890）。
- **完整性**：30/30 完成，Harbor 记 0 异常、0 重试。
- **花费（账本）**：类别 `harbor-external` 共 890 次调用，**¥3.0144**，与 Agent 上报之和一致。served_model 全部 deepseek-flash。比 r2 的 ¥1.86 高，主要是高峰价 + polyglot 三次偏贵（¥0.52 / ¥0.38 / ¥0.20）。
- **入库内容**：`report.md` / `summary.json` / `analysis.json`，三个 job 的 `config.json` / `result.json`。轨迹与 verifier 输出不入库；`scripts/secret_scan.py` 应对干净。

## 结果

| 题 | 第二轮 k/3 | 第三轮 k/3 | 备注 |
|---|---|---|---|
| cobol-modernization | 2/3 | **3/3** | |
| constraints-scheduling | 3/3 | 3/3 | |
| fix-git | 3/3 | **1/3** | rep1/rep2 判分环境 `apt` 装 curl 遇 debian 镜像 500/404；Agent 已给出合理 merge。**不是 Agent 回归** |
| git-leak-recovery | 3/3 | 3/3 | |
| multi-source-data-merger | 3/3 | 3/3 | |
| nginx-request-logging | 3/3 | 3/3 | |
| openssl-selfsigned-cert | 3/3 | 3/3 | |
| overfull-hbox | 1/3 | **3/3** | r2 里 perl 暴力搜索反复超时被 Harbor 取消；r3 仍有 2 次 exit 124，但守卫后均解决 |
| polyglot-c-py | 2/3 | **3/3** | |
| prove-plus-comm | 3/3 | 3/3 | |

| 指标 | 第三轮（30 次） | 第二轮（30 次） |
|---|---|---|
| 解决 | **28/30 = 93.3%**（Wilson 79%–98%；按题聚类 bootstrap 80%–100%） | 26/30 = 86.7%（70%–95%） |
| 每题至少一次解决 / 三次全过 | 10/10 / 8/10 | 10/10 / 7/10 |
| 花费 | ¥3.01（高峰价占比高），每次中位 ¥0.053、最高 ¥0.522 | ¥1.86，每次 ¥0.062 |
| tokens | 输入 16.6M（缓存命中 **98.1%**），输出 338k，890 次调用 | 15.7M（97.9%），307k，924 次 |
| 步数 / Agent 秒（中位） | 18 步 / 67 秒 | 18 / 65 |
| 上下文清理 / 压缩 | 0 | 0 |

## 结论

- **超时守卫有效**：overfull-hbox 从 1/3 → 3/3；cobol / polyglot 也到 3/3。守卫没有把题做挂。
- **fix-git 的 2 次失败记为判分环境**：verifier 侧 apt 镜像故障，Agent 侧已完成合并；rep0 同题在镜像正常时得 1.0。不要据此改 Agent。
- 与 r2 的配对可检出差距约 23 个百分点（n=30）/ 40 个百分点（按 10 题），本次 +6.7pp 在噪声里；方向与守卫预期一致。
- 子集是挑过的，n 小，只作外部参照，不和公开榜单或 dev / test 比较。
