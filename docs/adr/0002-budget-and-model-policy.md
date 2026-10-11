# ADR-0002：预算与模型策略（v0.1）

- 状态：**已采纳**（Eva，2026-10-10 北京时间）；2026-10-11 修订：预算控制已去掉（见文末）

## 决定
1. **模型白名单**：只允许 `deepseek-flash`（= `deepseek-v4.1-flash`；旧别名 `deepseek-v4-flash` 按 Flash 计费），思考 / 非思考两种模式。**永不**使用 `deepseek-v4-pro`；Router 拒绝白名单外的模型。
2. **单厂商**：v0.1 只测 DeepSeek，`vendor_policy=single_vendor`。评审采用“同厂商异构评审”（独立上下文、不同思考强度 / 提示 / 温度），README 如实说明；跨厂商互审是资金到位后的里程碑。多厂商接口（Vendor 枚举、ModelAdapter 协议、`cross_vendor` 策略）保留。
3. **预算**：LLM API 总额 ¥100（本地账本到 ¥100 硬停，80% 告警）；每次 `tw eval` 默认 `--max-total-cny 10`。单任务默认（eval）：`max_cost_cny=0.8`、`max_input_tokens=3M`、`max_output_tokens=100K`、`max_turns=100`、`max_wall_seconds=1800`、`warn_ratio=0.8`；`tw run` / dogfooding：¥1.0、2700s。评测默认每配置 1 次，校准后再扩档。
4. **空闲时段**：DeepSeek 高峰 = 北京时间周一至周五（不含法定节假日）9:00–12:00、14:00–18:00，价格为空闲的 2 倍。所有 live / 批量调用默认只在空闲时段；高峰启动需 `--allow-peak` 显式确认。来源：https://api-docs.deepseek.com/zh-cn/quick_start/pricing （2026-10-10 核对）。
5. **测试不花钱**：单测与 CI 强制 `TW_LLM_MODE=replay`；`live` 测试只手动运行。
6. **密钥**：`DEEPSEEK_API_KEY` 只从环境变量读取；不打印、不写入文件 / fixture / 事件 / 日志。
7. **节奏**：W1–W8 是按进度推进的相对阶段，不锁日历；W1+W2 为地基块。

## 修订 2026-10-10（W2-26）

W2-25 里 `max_input_tokens=3M`（含缓存命中）在真实 SWE 题上总是先触发（35 题中 12 题撞线，撞线时只花 ¥0.2–0.4，未命中仅约 10 万）。改为：总输入 6M 作兜底 + 新增 `max_uncached_input_tokens=400K`（按真正计价的未命中输入），`max_cost_cny` 仍是真正的闸门。同时 Executor 流程默认 harness 改为 repro-first（`HarnessConfig.default()`）；显式指定 `configs/harness/baseline.yaml` 的 RunConfig（W2-25 基线）不变，新增 `configs/runs/w2-26-deepseek{,-nothink}.yaml`。

## 修订 2026-10-11（0.3.2，去掉预算控制）

Eva（2026-10-11 19:14 北京时间）：“可以把预算控制相关功能去掉了”。决定 3、4 中的**控制**部分作废，其余不变：

- **去掉**：¥100 总额与类别信封的拦截（`GlobalLedger.precheck`）、STOP 文件 / `TW_KILL_SWITCH` 熔断、单任务 ¥ 上限（`Budget.max_cost_cny` 读入后忽略，`--max-cost` 隐藏且无效）、高峰闸门与 `--allow-peak`（调用级与评测级都不再拒绝，`PeakGate` 只做标注）、`tw eval` 按预估金额拒绝启动（`--max-total-cny` 隐藏且无效）、桌面端设置里的单任务上限滑块 / 总预算 / “高峰时段也允许真实调用”开关、桥接错误码 `peak_blocked`。
- **保留**：本地账本（改称用量日志，`tw usage` / `tw usage --json`，按类别 / 周 / 模型统计；`tw budget` 作为隐藏别名）、每条消息 / 每个任务的花费显示（结论卡实付、悬停名义价）、缓存命中统计、高峰价调用计数；非金钱安全上限（`max_turns`、`max_wall_seconds`、`max_input_tokens`、`max_uncached_input_tokens`、`max_output_tokens`，`warn_ratio` 改为按这些上限提醒收尾）；模型白名单（永不使用 `deepseek-v4-pro`）；测试 / CI 不花钱（replay / 本机模拟服务）。
- **迁移**：桌面端偏好里的 `maxCost` / `allowPeak` 读入时丢弃并立即改写存储；旧前端传来的 `maxCost` / `allowPeak` 被 Rust `Choices` 与核心忽略；旧链接 `section=budget` 跳到“用量”页；`CostReport.budget_cny` 改为可选（旧轨迹照常读）。`configs/budget.yaml` 只剩安全上限与统计类别。
- 研究工具 `tw eval reverify --max-total-cny` 是显式传入的一次性上限，保留。

## 修订 2026-10-11（1M 上下文档）

Eva（2026-10-11 20:26 北京时间）批准默认工作预算直接用约 950K（窗口 1,048,576 − Executor 输出预留 64K − 3%）。防失控上限跟着工作预算推导（仍不含金额）：`max_input_tokens` = 100 轮 × 工作预算 × 0.63 ≈ 60M（原 6M），`max_uncached_input_tokens` = 3 × 工作预算 ≈ 2.85M（原 400K）；`configs/budget.yaml` 写 `auto`。失控时的名义最坏花费约 ¥4.4 / 任务（错峰），只统计不拦截。见 spec 007 §12。

