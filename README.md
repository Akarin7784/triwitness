# TriWitness（三证）

验证优先的后台 Coding Agent：Issue → 计划 → 复现 → 修复 → 干净沙箱复验 → 评审 → 带**证据包**的 PR，并附带一个可复现的评测与消融平台。

> 状态：**pre-alpha（W1 地基阶段）**。目前只有骨架、数据模型、事件协议和桌面端外壳（数据为回放 / mock）。

## v0.1 的真实范围（如实说明）

- **只用 DeepSeek `deepseek-flash`**（思考 / 非思考两种模式），永不使用 `deepseek-v4-pro`；多厂商接口保留，Qwen / GLM 在资金到位后接入。
- **评审是“同厂商异构评审”**（独立上下文 + 不同思考强度 / 提示），**不是**跨厂商互审；跨厂商互审是后续里程碑。
- 总 API 预算 ¥100；批量调用只在 DeepSeek 空闲价时段运行（北京时间工作日 9:00–12:00、14:00–18:00 为高峰）。

## 快速开始

```bash
uv sync
uv run pytest            # 单测，不联网、不调 API
uv run tw --version
cd apps/desktop && npm ci && npm run build   # 桌面端前端构建（不打安装包）
```

## 目录

| 路径 | 内容 |
|---|---|
| `src/triwitness/` | Python 包（core / llm / sandbox / harness / tools / cost / telemetry / eval / cli / serve） |
| `apps/desktop/` | Tauri 2 + React 19 桌面端（Windows） |
| `specs/` | 规格（SDD），动手前先读 |
| `docs/` | 架构、ADR、设计说明、ai-native-log |
| `configs/` | 模型、价格、预算、harness、评测运行配置 |
| `evals/` | 评测任务、套件、事件 fixture；`evals/results/` 不进仓库 |
| `schemas/` | 由 pydantic 导出的 JSON Schema（如 `tw-events-1.schema.json`） |

AI 编程助手请先读 [`AGENTS.md`](AGENTS.md)。许可证：Apache-2.0。
