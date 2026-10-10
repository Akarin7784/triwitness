# AI-native 开发日志

> 每条记录：日期（北京时间）｜任务 ID｜用了什么 AI 助手、怎么提示｜AI 做对 / 做错了什么｜人做了什么判断。

- 2026-10-10｜W1-01｜Eva 一次性采纳 ADR-0001（接口与路径）、ADR-0002（预算与模型策略）。
- 2026-10-10｜W1-04 / W1-05｜AI 生成 monorepo 骨架、CI、规格回写；桌面端从 `agent-product/apps/desktop` 复制进 `apps/desktop`（monorepo 版本为准）。
- 2026-10-10｜W1-06｜AI 按 architecture §8 + ADR-0001/0002 实现 core（models / errors / ids / events）；`Usage` 拆命中 / 未命中并校验相加，`Budget` 默认 eval 档，时间字段强制带时区。Vendor 保留 `zhipu`（沿用设计文档命名）。
- 2026-10-10｜W1-36｜AI 冻结 tw-events/1：每个 kind 一个 payload 模型（允许额外字段），导出判别式 JSON Schema；3 份 fixture 由脚本确定性生成（贴近桌面端 mock 的 Issue #87），测试检查 seq 连续、无密钥样式、只出现 deepseek-flash、空闲时段。
- 2026-10-10｜W1-07/08/11/12｜AI 实现 llm 层与成本护栏；空闲时段真调 6 次录 fixture，共 ¥0.0054（账本记录），稳定前缀命中率 94%。发现：今天 10-10 是调休上班的周六，DeepSeek 定义的高峰只算周一至周五，因此按空闲处理。
- 2026-10-10｜W1-13/W1-14｜AI 实现 Router 与批量层空闲闸门，无真实调用（¥0）。沙箱（W1-15+）按 Eva 指示暂停：她在重新考虑终端用户是否必须装 Docker。
- 2026-10-10｜ADR-0005 / spec 002 重写 / spec 006｜Eva 拍板“默认无沙箱 + 一键装 WSL2/Docker + 抄成熟权限设计”；AI 调研 Claude Code、Codex、Gemini CLI、Cline/Roo、Cursor 官方文档后起草（只借鉴概念；Claude Code、Cursor 为专有许可）。tw-events/1 加审批事件桩。无真实调用（¥0）。
- 2026-10-10｜W1-15/16/39/40｜AI 实现沙箱后端协议与选择、docker 后端、规则解析、权限引擎（分层配置、默认规则、审计），并按 Eva 新增的 `unrestricted`（勇士模式）补规格、引擎与 `mode_changed` 事件。AI 写测试时发现并修复：解析器遇 `f() {` 死循环、8.3 短名正则漏判 `PROGRA~1\x`、路径转义规则无法匹配、Bearer 短令牌未脱敏、超时标记竞态。无真实调用（¥0）。
