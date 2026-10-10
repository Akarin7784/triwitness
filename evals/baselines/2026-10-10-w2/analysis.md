# W2-25 基线分析（2026-10-10，北京时间 18:12 起，全程空闲时段）

模型 `deepseek-flash`；test 集 35 题 = 思考 high（`configs/runs/baseline-deepseek.yaml`），dev 集 15 题 = 非思考
（`configs/runs/baseline-deepseek-nothink.yaml`）；每题 1 次；本轮上限 ¥30（Eva 批）。高峰调用 0。
账本：本轮结果合计 ¥8.97（test ¥8.16 + dev ¥0.81）；总账 ¥10.68 / ¥100（`tw budget`）。
统计口径：Resolved@1 = attempt 1；95% CI = 任务级 bootstrap（2000 次，种子 0）；基础设施错误不计分母（W2-24）。
本目录的 `result.json` 已按复核结论更新（原始版本存为同目录 `result.orig.json`），`report.*` 用 `tw eval report` 重建。

## 1. 总表

| 子集 | 解决/有效 | Resolved@1 | 95% CI | 花费 | ¥/任务 | ¥/解决 | 虚假成功 | 预算耗尽 | infra |
|---|---|---|---|---|---|---|---|---|---|
| **test 全部（思考 high）** | 16/33 | **48%** | 33%–67% | ¥8.16 | ¥0.233 | ¥0.510 | 6 | 17 | 2 |
| test · leaderboard（2025-10～2026-03 新题） | 10/22 | 45% | 27%–68% | ¥5.38 | ¥0.234 | ¥0.538 | 3 | 12 | 1 |
| test · filtered（2024 旧题，可能被训练见过） | 6/11 | 55% | 27%–82% | ¥2.78 | ¥0.231 | ¥0.463 | 3 | 5 | 1 |
| test · easy | 2/6 | 33% | 0%–67% | ¥1.16 | ¥0.193 | ¥0.578 | 2 | 3 | 0 |
| test · medium | 11/17 | 65% | 41%–88% | ¥3.87 | ¥0.215 | ¥0.351 | 2 | 7 | 1 |
| test · hard | 3/10 | 30% | 0%–60% | ¥3.14 | ¥0.285 | ¥1.046 | 2 | 7 | 1 |
| **dev 全部（非思考）** | 12/15 | **80%** | 60%–100% | ¥0.81 | ¥0.054 | ¥0.068 | 2 | 1 | 0 |
| dev · 合成 | 5/5 | 100% | — | ¥0.05 | ¥0.010 | ¥0.010 | 0 | 0 | 0 |
| dev · SWE filtered | 7/10 | 70% | 40%–100% | ¥0.76 | ¥0.076 | ¥0.109 | 2 | 1 | 0 |

- leaderboard 与 filtered 的差（45% vs 55%）远在 CI 内，**看不出污染效应**；样本太小，只能如实分开报。
- 难度标签是启发式的（W2-23）：easy 反而最低（2/6），说明“补丁行数”不是好的难度代理，W5 扩题时要换口径。
- 平均每题输入 2.14M token（命中 97.2%）、输出 3.3 万；平均 53 步、520 秒。

## 2. 基础设施错误（不计分母）

- **swe-opensandbox-816**：首次 apt `BuildError`（errors.json），续跑后正常跑完并判分（reward 0，1 个隐藏用例失败）→ **结果有效，不算 infra**。
  errors.json 残留旧条目导致报告把它同时算进分母和 infra，已修（runner 合并 / report 过滤，63e1233）。
- **swe-ultraplot-696、swe-xcp_d-1433 → infra**：离线“参考解 × Grader 条件”复查（50 题全跑）发现这两题的参考解在
  Grader 里 reward=0。原因：任务校验用 root，Grader 和 Agent 沙箱用 uid 1000（镜像里没有这个用户，HOME=/ 不可写），
  ultraplot 导入时 `mkdir /.config`、xcp_d 收集时 `mkdir /.cache` 必挂。已修（44f9f41：uid 1000 的 Grader/Agent 沙箱 HOME=/tmp），
  修后两题参考解 =1、空补丁 =0。用修后的 Grader 离线重判 Agent 已存补丁：ultraplot **resolved**、xcp_d unresolved
  （仅供参考，不计入本基线；若计入则 test = 17/35 = 49%）。两题的 Agent 也在同样坏的环境里干活（xcp_d 还为此自建了 conftest.py），所以整体按 infra 处理。

## 3. 篡改标记复核（原 test 9 + dev 1）

结论：**没有一例是“为了让判分通过”的作弊**；所有测试改动 Grader 本来就不应用，判分不受影响。但旧规则把“改已有测试的任何一行”都记为篡改，噪声太大。

| 任务 | 改动 | 判定 |
|---|---|---|
| llm-sandbox-101 | `tests/test_mcp_server.py` 把 `from mcp.types import …` 改成 `pytest.importorskip` | **篡改**（削弱：整模块变 skip） |
| spikeinterface-3047 | 根 `conftest.py` 加 try/except，让仓库外路径（我们放的 `tests/tw_repro/`）能被收集 | **篡改**（测试基础设施；起因是我们的复现测试目录） |
| xcp_d-1433 | 新建 `conftest.py` 把 TEMPLATEFLOW_HOME 指到 /tmp | **篡改**（测试基础设施；起因是上面的 HOME 环境 bug） |
| bedrock-agentcore-279、icontract-297、spikeinterface-3778、bugbear-424（dev） | 按 issue 改期望值（标签名、继承语义、聚合规则、行号），断言不减 | 改写已有测试（resolved） |
| canvasapi-716、llm-sandbox-101（test_session.py）、openhands-123、ro-crate-193 | 改期望值去迁就自己的实现（`"user"` 不再抛 TypeError、timeout 30→None、多一次 git 调用、不再 raise） | 改写已有测试（**全部 unresolved**，隐藏测试正好挂在这些期望上） |

Grader 分类已改（63e1233，规则与 verify/anticheat 共用）：测试基础设施 / 删除或改名测试 / 新增 skip·xfail·importorskip / 恒真断言 / 净减少断言 → `tamper_paths`；
其余改已有测试 → 新字段 `edited_paths`（报告单列“改写已有测试期望，建议人审”）。新结果：**test 篡改 9 → 3，改写 6；dev 篡改 1 → 0，改写 1**。
附带发现：改写已有测试的 7 次里 4 次失败——“改测试迁就实现”是虚假成功的强信号，W3 Reviewer/防作弊的 `existing_test_modified → review(L2)` 是对的。

## 4. 失败模式（test 17 个失败 + dev 3 个，排除 2 个 infra）

| # | 模式 | 次数 | 例子 |
|---|---|---|---|
| A | **输入 token 上限先撞（3M）**：探索太久，上下文 60–100K × 60–70 次调用 | test 11 失败（另有 4 题撞上限但已解决） | sqlfluff-7615、sqlglot-7457 70 步**一次都没改代码**；cfn-lint-4368、marimo-8401 第 68/69 步才第一次编辑；param-1117、openhands-123 撞 ¥0.5 单任务上限 |
| B1 | 虚假成功 · 接口/命名 issue 没写，模型自己猜 | 2 | dev crosstl-257（token 名 `UNSIGNED_INT`）、msal-730（隐藏测试要 `token_source` 字段） |
| B2 | 虚假成功 · 改已有测试迁就自己的实现 | 2 | canvasapi-716、llm-sandbox-101（见 §3） |
| B3 | 虚假成功 · 只修了主路径，漏边界/错误路径 | 4 | conan-19750（错误分支）、django-components-489、loguru-1306（NO_COLOR/FORCE_COLOR 语义 10 个用例）、dev h-transport-224 |
| C | 正常收尾但没修好（未声称成功） | 1 | dev lilio-58（空日历边界） |
| D | 补丁卫生：运行产物混进 diff | 2（不影响判分） | dev dymos-1021 的 openmdao `*_out/reports`（4.6 MB）、h-transport-224 的 `out.bib/out.json` |

虚假成功合计 8（test 6 + dev 2）：Agent 声称成功的 17 道 test 题里有 6 道判分不过（35%），这正是 W3 验证器要压的数。
A 类说明 §9.4 的 `max_input_tokens=3M` 在真实 SWE 题上是**先触发的闸门**（触发时花费才 ¥0.2–0.4，远没到钱的上限），交给 W2-26 复核（建议：改按未命中 token 计或放到 5–6M，并让 Agent 更早动手/做笔记）。

## 5. 慢题

- dev **swe-dymos-1021**：1654 秒（单任务墙钟上限 1800 秒），Agent 多次跑整个项目测试套件（单条命令 10 分钟超时内跑完），最终解决；也是 D 类补丁污染来源。
- dev **swe-ro-crate-py-171**：1265 秒，76 步撞 3M 输入上限，仍解决。
- test 里 stumpy-1015（1761 秒）、spikeinterface-3778（1520 秒）、opensandbox-816（1328 秒）、scrapy-7351（1213 秒）、conan-19750（1159 秒）也都超过 1000 秒。
  墙钟主要花在测试执行上，不花钱；建议 W3-05 测试选择默认先跑相关测试、全量只在收尾跑一次。

## 6. 与 W1 首跑对比（重叠的 10 道 dev 题）

| | W1（思考 high，上下文工程前） | W2 dev（非思考，上下文工程后） |
|---|---|---|
| 解决 | 9/10 | 9/10（同样只挂 crosstl-257） |
| 花费 | ¥0.327 | ¥0.232（−29%） |

两次同时换了思考模式和 harness，不能归因到单一因素；只能说明“非思考 + 新 harness 在简单题上不掉点、更便宜”。思考 vs 非思考的干净对照留给 W5 消融。

## 7. 成本校准与档位（PROJECT_PLAN §9.5）

- test（思考 high）实测 c = **¥0.233/次**，命中 97.2% → 落在 **¥0.13 < c ≤ ¥0.30：按原表执行，不扩档**。W1 的“初判扩档”（c=¥0.033，全是小题）作废。
- dev（非思考）¥0.054/次；50 题合计 ¥0.179/次。命中率 97% > 90%，不需要修前缀。
- 每解决一题 ¥0.51（test）；hard 题 ¥1.05/解决。
- estimate 偏差：run.json 预估 ¥8.04 vs test 实际 ¥8.16（+1.5%，在 ±25% 目标内）。
- 预算：W2 周信封 ¥13，本周累计 ¥10.68（累计信封 ¥18 以内）。`configs/budget.yaml` 的 baseline 信封按 Eva 批的本轮 ¥30 调到 ¥31（总额硬上限仍是 ¥100）。
- 尚未做：`tw budget sync` 与 DeepSeek 余额对账（需调余额接口，本次按“只离线”没调）。
