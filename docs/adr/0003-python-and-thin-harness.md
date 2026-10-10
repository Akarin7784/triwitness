# ADR-0003：用 Python + 自研薄 harness

- 状态：已采纳（2026-10-10，沿用设计文档 docs/architecture.md §2.4 的技术选型）

## 背景
需要一个能逐行讲清楚、便于做消融实验的 agent 内核，同时保持模型无关（v0.1 只接 DeepSeek，后续接 Qwen / GLM）。

## 决定
1. **语言：Python 3.12**（uv、pydantic v2、asyncio）。LiteLLM、Temporal、Langfuse / OTel、MCP SDK、tree-sitter 都有一等 Python 支持；目标岗位里 Python 最常见。桌面端单独用 Tauri + React（`apps/desktop`），只通过 `tw-events/1` 与 core 交互。
2. **Harness：自研薄 harness**（核心目标 1500–2500 行）：循环 + 工具 + 上下文管理 + 完成契约。参考 OpenHands Software Agent SDK 与 mini-swe-agent 的抽象，**不直接依赖**。
3. **编排**：先做进程内 asyncio 编排（评测 / CLI）；Temporal 后台编排排在后面，时间不够时第一个砍。

## 理由
- 消融实验需要能单独开关工具、截断阈值、上下文策略；自己的薄 harness 每个开关都在配置里（spec 003 §8）。
- 极简 harness 在成本 / 成功率上可以处于帕累托前沿（设计文档引用的 HarnessTax 研究）；稳定前缀和缓存命中由我们自己控制，直接决定 ¥100 预算能跑多少评测（ADR-0002）。
- 面试与写作需要逐行讲清核心模块。

## 没选的方案
| 方案 | 为什么不选 |
|---|---|
| 直接用 OpenHands SDK | 依赖面大，难以逐行解释；消融粒度受其抽象限制。保留为参考实现 |
| LangGraph / OpenAI Agents SDK 等通用框架 | 不含编程专用工具和沙箱抽象；状态图对单循环 agent 是额外复杂度。适合做外层编排，不适合内层 harness |
| fork Qwen Code / 其他 CLI agent | TypeScript 技术栈；许可证与上游跟进成本高 |
| TypeScript 后端 | 评测与可观测生态（Harbor、LiteLLM、Langfuse Python SDK）在 Python 侧更完整 |

## 影响
- `src/triwitness/core/` 只放数据模型与事件，其他包只依赖 core（AGENTS.md §3）。
- 任何引入外部 agent 框架的提议需要新 ADR。
