# ADR-0006：W2 后单厂商路由与默认 harness（W2-26）

- 状态：**已采纳**（2026-10-11，Eva；草稿同日起草，依据 W2-25 基线与已合入代码）
- 取代 / 补充：ADR-0002 中「单任务输入上限」与「默认 harness」相关条目；白名单与永不 v4-pro 仍以 ADR-0002 为准

## 背景

W2-25（2026-10-10）在 test 35（思考 high）+ dev 15（非思考）上实测：

- test Resolved@1 = 16/33 ≈ 48%（CI 33%–67%；2 题 infra 不计分母）
- 命中率 97%；结果合计约 ¥8.97，总账约 ¥10.68；c ≈ ¥0.233/次 → §9.5 **不扩档**
- 重叠 10 道 dev 题：W1 思考 high 9/10 vs W2 非思考 9/10，非思考便宜约 29%（同时换了 harness，不能单归因）
- 失败主因：`max_input_tokens=3M`（含缓存命中）先于 ¥ 上限触发（test 约 11 题撞线，撞线时往往只花 ¥0.2–0.4）

输入上限与默认 harness 的代码改动已合入（见 ADR-0002「修订 2026-10-10（W2-26）」）。本 ADR 冻结**路由叙事**与仍待拍板的 live 复跑。

## 决定（建议默认，待确认）

1. **继续 `vendor_policy=single_vendor`**：v0.1 仍只路由 `deepseek-flash`。理由：预算 ¥100、三家真跑与跨厂商互审仍在 DF；接口与 `cross_vendor` 单测保留，资金到位只改配置（DF-04）。
2. **角色路由保持 ADR-0002 / `configs/models.yaml`**：
   - Executor / Planner / Verifier：`deepseek-flash` 思考（Executor effort=high）
   - Reviewer：思考 max + 对抗式提示 + 独立上下文（变体）；另保留非思考清单式变体供 W4 消融
   - Summarizer / Classifier：非思考
3. **Executor 默认 harness = repro-first**（`HarnessConfig.default()` → `configs/harness/repro-first.yaml`）。显式引用 `baseline.yaml` 的历史 RunConfig（含 W2-25）不变。新增对照配置：`configs/runs/w2-26-deepseek.yaml`、`w2-26-deepseek-nothink.yaml`。
4. **思考 vs 非思考**：默认仍用思考 high 跑难 SWE；非思考在简单重叠题上不掉点、更便宜，干净对照留给 W5 消融，本 ADR **不**把默认改成非思考。
5. **W2-26 live 复跑（test+dev，预估约 ¥12–15，空闲时段）**：**推迟**，等加服务器与充值后再批预算。在此之前不擅自 `--live`。

## 理由

- 单厂商是预算与诚实叙事，不是架构终局；README / 博客须继续写明「同厂商异构评审」。
- 3M 总输入把「命中缓存的长前缀」也算进闸门，真实 SWE 上误伤；已改为 6M 总输入兜底 + 400K 未命中，¥ 上限才是真闸门（ADR-0002 修订）。
- repro-first 把「先写必失败的复现测试」变成默认产品行为，与验证器 / 证据包叙事一致；基线可比性靠显式 baseline 配置保留。
- 思考 vs 非思考差一分钱面值与一分成功率，需要 OFAT，不在 W2-26 拍板。

## 影响

- 文档：本 ADR；必要时回写 PROJECT_PLAN §9.4 / NOTES 路由表一句「见 ADR-0006」。
- 代码：已合入部分无需再改；live 复跑仍要 Eva 显式批准与预算上限。
- 评测：未复跑前，对外引用数字仍以 `evals/baselines/2026-10-10-w2` 与 W3 verifier 结果为准，并注明输入上限规则已变。

## 回写清单

- [x] Eva 2026-10-11 采纳（随 v0.3 公开预览发布切分一起批准）
- [ ] 若修改角色 effort / 默认 thinking，同步 `configs/models.yaml` 与本 ADR
- [ ] live 复跑获批后，结果写入 `evals/baselines/` 并更新本 ADR「后续」一节
