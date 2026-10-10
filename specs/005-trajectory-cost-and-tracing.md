# Spec 005：轨迹、成本账本与追踪

- 状态：草稿｜负责人：Eva｜目标周：W1（事件日志 + 成本）→ W2（OTel + Langfuse）｜依赖：001、003
- 相关文档：04-detailed-design.md 第 3.7、4.5、8 节

## 1. 背景

可观测性是这个项目的"证据"来源：PR 上的成本账单、评测报告里的每解决任务成本、失败分析、可公开的数据集，都来自同一份轨迹。轨迹必须是**追加写的事件日志**，既能回放、断点续跑，也能导出。

## 2. 目标

1. `TrajectoryRecorder`：把每一步写成事件，追加到 JSONL（本地）/ SQLite 表。
2. `CostLedger`：按调用、角色、模型、厂商汇总 token 和人民币成本，计算缓存命中率；生成 `CostReport`。
3. OTel 追踪：遵循 GenAI 语义约定，导出到 Langfuse（自托管）。
4. 导出：`tw traj export` 输出脱敏后的轨迹（JSONL），供公开数据集使用。
5. PR 成本账单的 Markdown 渲染。

## 3. 非目标

- Postgres 存储（服务模式，W4）。
- 网页版轨迹查看器（用 Langfuse 自带界面）。
- 训练数据格式转换（以后再做）。

## 4. 数据模型

与设计文档第八节保持一致（以 `src/triwitness/core/models.py` 为准），这里列出本 spec 用到的部分：

```python
class TrajectoryEvent(BaseModel):
    seq: int  # 单调递增
    ts: datetime  # 带时区，存储用 UTC，展示转 Asia/Shanghai
    task_id: str
    run_id: str
    role: Role | None
    kind: Literal[
        "task_started",
        "model_call",
        "tool_call",
        "state_change",
        "checkpoint",
        "loop_warning",
        "hitl_request",
        "hitl_response",
        "verification",
        "review",
        "task_finished",
        "error",
    ]
    payload: dict
    trace_id: str | None = None
    span_id: str | None = None


class Usage(BaseModel):  # ADR-0001 #5：命中 / 未命中分开记
    input_tokens: int  # 总输入（含命中）
    cache_hit_tokens: int
    cache_miss_tokens: int
    output_tokens: int
    reasoning_tokens: int | None = None


# 下面是初稿字段；以 ADR-0001 #5 为准：CostLine 改为嵌套 usage: Usage，CostReport 增加 task_id / sandbox_cost_cny / budget_cny，并提供 to_flat()。
class CostLine(BaseModel):
    role: Role
    vendor: Vendor
    model: str
    calls: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int | None
    cost_cny: float
    peak_calls: int = 0  # DeepSeek 高峰时段调用次数


class CostReport(BaseModel):
    lines: list[CostLine]
    total_cny: float
    cache_hit_rate: float  # cached_input / input
    pricing_version: str  # pricing.yaml 的 verified_at
    estimated: bool = True  # 本地计价，非厂商账单
```

`model_call` 事件 payload：`model`、`served_model`、`vendor`、`usage`、`cost_cny`、`peak`、`latency_ms`、`finish_reason`、`degraded`、`request_ref`（指向完整请求/响应文件，不内联）。

`tool_call` 事件 payload：`tool`、`args`、`ok`、`exit_code`、`duration_ms`、`output_ref`、`truncated`。

## 5. 行为细节

1. **写入**：每个事件写完立即 flush；JSONL 路径 `evals/results/.../trajectory.jsonl`（评测）或 `~/.triwitness/runs/<run_id>/trajectory.jsonl`（`tw run`）；事件格式即 UI↔core 契约 `tw-events/1`（`docs/design/event-protocol.md`），信封新增 `v: 1`，payload 可选 `display`（≤200 字、已脱敏）与 `role_hint`；完整请求/响应写到 `artifacts/<seq>-request.json`、`<seq>-response.json`。
2. **回放**：`Trajectory.load(path)` 能重建消息历史，用于断点续跑（spec 011）和调试。
3. **成本**：每次 `model_call` 由 `pricing.price_call` 计价；`CostLedger` 订阅事件流实时累加，供 Budget 检查（spec 003）。
4. **OTel**：
   - 每个任务一个根 span `tw.task`；每个角色运行一个 `invoke_agent` span；每次模型调用一个 `chat {model}` span；每次工具调用一个 `execute_tool {tool}` span。
   - 属性使用 OTel GenAI 语义约定（如 `gen_ai.operation.name`、`gen_ai.provider.name`、`gen_ai.request.model`、`gen_ai.response.model`、`gen_ai.usage.input_tokens`、`gen_ai.usage.output_tokens`），自定义属性用 `tw.` 前缀（如 `tw.cost_cny`、`tw.cached_input_tokens`、`tw.role`）。
   - 语义约定仍处于发展阶段，**实现时以当时的官方文档为准**，并在 `docs/design/tracing.md` 记录所用版本。
   - 消息内容默认不进 span（只记录引用），通过 `TW_TRACE_CONTENT=1` 开启。
   - 导出：OTLP HTTP → Langfuse（`docker compose` 提供自托管 Langfuse）；未配置时静默降级为只写本地 JSONL。
5. **脱敏导出**：去掉 API key 模式（`sk-`、`ghp_` 等正则）、邮箱、宿主机绝对路径；保留结构和 token 统计。
6. **PR 账单渲染**：

```markdown
### 💰 成本（本地估算，非厂商账单）
| 角色 | 模型 | 调用 | 输入（命中） | 输出 | 费用 |
|---|---|---|---|---|---|
| executor | deepseek-flash | 23 | 1.6M（82%） | 41K | ¥1.05 |
| ... |
**合计 ¥x.xx**｜缓存命中率 xx%｜价格表版本 2026-10-10
```

（以上数字仅为格式示意。）

## 6. 验收标准

- [x] AC1：用 FakeRouter 跑一个 5 步任务，JSONL 中事件 `seq` 连续、种类正确，能用 `Trajectory.load` 重建出相同的消息列表。
- [x] AC2：进程在第 3 步被杀，JSONL 至少包含前 2 步的完整事件（每行都是合法 JSON）。
- [ ] AC3：`CostReport` 的总额等于各 `model_call` 事件 `cost_cny` 之和（误差 < 0.0001）；缓存命中率计算正确。
- [ ] AC4：配置 Langfuse 后，一个任务在 Langfuse 中显示为一棵 trace 树：task → agent → chat / execute_tool（手动验证，截图放进 docs）。
- [ ] AC5：未配置 OTel 端点时，运行不报错、不阻塞。
- [ ] AC6：导出文件中不包含任何 `sk-`、`ghp_` 前缀的字符串和宿主机 home 路径（单测用注入的假密钥验证）。
- [ ] AC7：PR 账单 Markdown 渲染快照测试通过。

## 7. 测试计划

- 单测：事件序列化、回放、成本汇总、脱敏、Markdown 快照。
- 集成：用 OTel 的内存导出器（InMemorySpanExporter）断言 span 结构和属性名。
- 手动：Langfuse 截图（AC4）。

## 8. 评测影响

评测报告的所有成本数字都来自 `CostReport`；`pricing_version` 写入每条结果，价格变动后旧结果仍可解释。

## 9. 开放问题

- 推理 token（reasoning tokens）各家是否单独返回、是否单独计价？→ 以 spec 001 的 fixture 实测为准；目前按输出 token 计价。
- 是否同时导出到阿里云 ARMS / 其他国内 APM？→ OTLP 标准，理论可行，作为文档示例而非功能。

## 10. AI 实施提示

- 事件写入用简单的追加文件 + `os.fsync`（可配置关闭以提速），不要过早引入消息队列。
- OTel 依赖：`opentelemetry-sdk`、`opentelemetry-exporter-otlp-proto-http`；不要引入厂商专有 SDK 作为硬依赖。
- 所有时间存 UTC，展示时转换为 Asia/Shanghai。

## 11. 变更记录

- 2026-10-10：初稿
- 2026-10-10：按 ADR-0001（W1 接口与路径）与 ADR-0002（预算与模型策略）修订：Usage 拆命中/未命中、CostLine 嵌套 usage；轨迹路径；事件格式 = tw-events/1（v、display、role_hint）。
- 2026-10-10：按 ADR-0005 修订：tw-events/1 新增 `approval_requested` / `approval_resolved`；`tool_call` 增加 `permission`、`permission_rule`；`verification` 增加 `clean_env`、`unverified_reason`（均可选，只增不改）；权限审计日志见 spec 006 §10。
- 2026-10-10：W1-24 实现 `telemetry/trajectory.py`（TrajectoryRecorder、Trajectory.load）与 `harness/run.py`（单角色任务驱动，产出 task_started → … → task_finished）。tw-events/1 只增不改：`model_call` 加 `request_ref` / `response_ref`，`tool_call` 加 `message_ref`（回放用）；display 与所有产物写盘前脱敏。新增 golden fixture `recorded.jsonl` 由真实代码路径（FakeRouter + FakeSandbox、固定时钟）生成，桌面端测试同时读取。CostReport 先由 `cost/report.py` 从事件汇总（W1-25 再做实时账本与 PR 账单）。
