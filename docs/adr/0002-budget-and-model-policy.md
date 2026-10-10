# ADR-0002：预算与模型策略（v0.1）

- 状态：**已采纳**（Eva，2026-10-10 北京时间）

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
