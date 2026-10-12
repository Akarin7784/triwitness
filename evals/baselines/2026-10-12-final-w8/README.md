# W8-01 终测 · test 35 × {单 Executor 基线, 完整流水线} × 1 次 · 2026-10-12（Eva 本机）

- **在哪跑**：Eva 的 Windows PC（Docker Desktop + WSL2，内核 6.18.40.1-microsoft-standard-WSL2，Docker 29.8.2），`scripts/windows/run-final-eval.ps1 -Reproduce`，代码 `86b5975`，并发 3。结果包分 10 卷发回，已全部收齐、合并。
- **冻结配置**：两臂都是 deepseek-flash 非思考（`configs/runs/final-baseline.yaml` = long-context-1m 单 Executor；`configs/runs/final-orchestrated.yaml` = orchestrated-1m：Planner → 复现 → Executor → 确定性 verifier → checklist 评审，ADR-0007）。评测模式权限全开、不读写记忆，只有防失控上限（100 轮 / 1800 s 墙钟 / token 兜底）。
- **价格表**：`configs/pricing.yaml` verified_at 2026-10-10（sha256 `22338c4f7b258690`）；served_model 两臂全部 `deepseek-flash`（基线 1917 次调用、流水线 2611 次）。
- **花费**：result.json 合计 **¥15.872**，本机账本 `final-eval` **¥15.924**（指导线 ≤ ¥18）。基线臂 1917 次调用里 **1478 次落在 DeepSeek 高峰价（2×）**，流水线臂 0 次——所以“实付”不能直接比，下面另给按空闲价重算的口径。

## 结果

| 臂 | 解决 / 判分 | Resolved@1 | Wilson 95% | 任务级 bootstrap 95% | 假成功 | 改写已有测试 / 篡改 | 平均回合 | 平均墙钟 | 撞安全上限 |
|---|---|---|---|---|---|---|---|---|---|
| 单 Executor 基线 | 16 / 35 | **45.7%** | 30%–62% | 31%–63% | 9 | 5 / 1 | 54.8 | 1057 s | 8（轮数 4、墙钟 4） |
| 完整流水线 | 19 / 35 | **54.3%** | 38%–70% | 37%–71% | 8 | 9 / 1 | 42.0 | 1284 s | 7（墙钟 5、轮数 2） |

- **基础设施错误 0**：两臂 35 题全部判分（W2 时的两个 infra 题 ultraplot-696 / xcp_d-1433 因 44f9f41 修复，这次正常判分；ultraplot 两臂都解决）。
- **配对**：只有流水线解决 3 题（loguru-1451、scrapy-7351_interface、sqlglot-7479），只有基线解决 0 题；**McNemar 精确 p = 0.25 → 无显著差异**。n = 35 时可检出差异约 25–30 个百分点，+8.6pp 在噪声范围内；方向一致（没有一题被流水线做坏）。
- **假成功**：两臂都偏高（9 / 8），其中 7 题两臂都是假成功（crosstl-98、django-components-489、huggingface_hub-4056、loguru-1306、openhands-resolver-123、opensandbox-816、ro-crate-py-193）——Reviewer 与确定性 verifier 都没拦下，是下一步要看的。

## 成本

| 臂 | 实付 | ¥/题（实付） | **空闲价重算** | ¥/题（空闲价） | ¥/解决（空闲价） | 缓存命中 | 按角色（实付） |
|---|---|---|---|---|---|---|---|
| 基线 | ¥7.382 | 0.211 | **¥4.168** | 0.119 | 0.261 | 98.1% | Executor 100% |
| 流水线 | ¥8.490 | 0.243 | **¥8.490** | 0.243 | 0.447 | 96.1% | Planner ¥4.19 · Executor ¥3.16 · Reviewer ¥1.14 |

- 同价口径下流水线约为基线的 **2.0 倍**，多出的钱几乎都是 **Planner（¥4.19，占流水线 49%）**；流水线的 Executor 反而比基线便宜（¥3.16 vs ¥4.17 同价）。
- “每解决一题的成本”实付口径两臂接近（0.461 vs 0.447）只是因为基线吃了高峰价；同价口径基线明显更便宜（0.261 vs 0.447）。
- 空闲价重算：逐条 model_call 的 usage × 空闲单价（命中 0.02 / 未命中 1.0 / 输出 4.0 元每百万），见 `analysis.json`。

## W8-05 复现（tw eval reproduce）

`reproduce/`：从基线臂挑最便宜的已解决题 swe-cyclopts-633 用同一配置 `--live` 重跑 1 次：原 ✓ → 现 ✓（一致率 100%），¥0.0765 → ¥0.0521，模型快照不变（deepseek-flash）。复现报告里“复现缺少”列出了其余 34 题——这是 `compare` 的显示 bug（`--task` 只复现子集时把没计划的题也算成缺少），已在本次提交修正，不影响结论。

## 与历史的关系（只作参考，不做配对）

- W2 基线（`../2026-10-10-w2/`，旧代码、flash **思考 high**、long-context 前）：test 16/33 = 48%、¥0.233/题。本次基线非思考 16/35 = 45.7%、同价 ¥0.119/题——解决率相当、成本约一半，与 W5 OFAT“思考无收益、约 3.3× 成本”一致。代码、harness、判分环境都变了，不能当配对比较。

## 结论（写进对外材料的口径）

1. 完整流水线 54.3%（38%–70%）vs 单 Executor 45.7%（30%–62%），**+8.6pp，McNemar p = 0.25，无显著差异**；3 : 0 的不一致方向全偏流水线。
2. 同价成本约 **2 倍**，主要来自 Planner；若要省钱，优先考虑按难度跳过 Planner（OFAT 在 dev 上也是 Planner 无收益、3.4× 成本）。
3. 假成功仍有 8–9 次，7 题两臂共有——验证器 / 评审对“接口没写清、模型自己猜”和“只修主路径”这两类仍无力，是 v1 之后的首要改进点。
4. 所有数字注明：2026-10-12、上述配置、deepseek-flash、价格表 2026-10-10；不和公开榜单或厂商自报分数比较。

## 入库内容

`summary.json` / `report.md`（`final_eval.py report` 生成）、`analysis.json`（空闲价重算、按角色、逐题、不一致题、撞上限统计）、`plan.json`、`env.json`、`run.log`；每臂 `report.json/md`、`run.json` 和逐题 `result.json` + `patch.diff`；`reproduce/`。轨迹与 artifacts（约 580 MB）不入库，原始结果包留在 Eva 本机与 box `/workspace/final-eval-in/`。账本 sqlite 不入库（数字已写在上面）。
