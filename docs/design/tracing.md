# 追踪（OTel + 自托管 Langfuse）

> spec 005 §5.4 / AC4 / AC5；实现：`src/triwitness/telemetry/otel.py`（W2-17）、`deploy/langfuse/`（W2-18）。

## 1. 设计

- **span 由轨迹事件派生**：`OtelBridge` 订阅 `TrajectoryRecorder`，不在 AgentLoop 里另插桩。轨迹是唯一事实来源，trace 只是它的一个视图；回放旧轨迹也能补出 trace。
- **树结构**：`tw.task` → `invoke_agent {role}` → `chat {model}` / `execute_tool {tool}`。chat 的开始时间 = 事件时间 − `latency_ms`，工具 = 事件时间 − `duration_ms`。`state_change` / `checkpoint` / `error` 记为 task 上的 span event，`context_event` / `loop_warning` 记在 agent 上。
- **语义约定**：OpenTelemetry semantic conventions **1.44.0**（`schema_url=https://opentelemetry.io/schemas/1.44.0`；Python 包 `opentelemetry-semantic-conventions 0.66b1`）。GenAI 约定仍是 development 状态，属性名可能变，升级时改 `SEMCONV_URL` 并核对下表。

| span | gen_ai.* | tw.* |
|---|---|---|
| `tw.task` | — | task_id、run_id、repo、config_hash、harness、harness_hash、mode、prompt.<role>、status、cost_cny、cache_hit_rate |
| `invoke_agent {role}` | operation.name=invoke_agent、agent.name | — |
| `chat {model}` | operation.name=chat、provider.name、request.model、response.model、usage.input_tokens / output_tokens、response.finish_reasons | cache_hit_tokens、cache_miss_tokens、reasoning_tokens、cost_cny、thinking、peak |
| `execute_tool {tool}` | operation.name=execute_tool、tool.name | tool.ok、tool.exit_code、tool.truncated、tool.permission；失败时 `error.type` + span 状态 ERROR |

- **隐私**：默认不记录任何消息内容；`TW_TRACE_CONTENT=1` 只附加事件里已脱敏、≤200 字的 `display`。
- **降级**：没配置端点 → 不建 provider、不订阅（零开销，AC5）；导出出错只记日志，不影响任务。

## 2. 端点配置

```bash
export TW_OTLP_ENDPOINT=http://127.0.0.1:3000/api/public/otel     # 会自动补 /v1/traces
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <base64(pk:sk)>"   # Langfuse 项目密钥
```

也可以只用标准变量 `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`（发往任何 OTLP/HTTP 后端：Jaeger、Tempo、阿里云 ARMS 等）。

## 3. 本机自托管 Langfuse（无需账号）

```bash
python scripts/langfuse_local.py env      # 生成 deploy/langfuse/.env：随机口令 + 项目密钥（0600，已 gitignore，不打印）
docker compose -f deploy/langfuse/docker-compose.yml --env-file deploy/langfuse/.env up -d
uv run python scripts/langfuse_local.py smoke                          # golden 轨迹 → Langfuse，用公开 API 校验树结构
uv run --with playwright python scripts/langfuse_local.py screenshot   # 无头 Chrome 截图 → docs/images/
set -a; source deploy/langfuse/.env; set +a                             # 之后 tw run / tw eval run 自动导出 trace
```

- compose 文件来自上游 langfuse/langfuse（MIT），改动：端口只绑 127.0.0.1、口令全部来自 .env、`LANGFUSE_INIT_*` 无头初始化（组织 / 项目 / 密钥 / 本地用户自动创建）。
- 资源：Langfuse v4 = web + worker + Postgres + ClickHouse + Redis + MinIO，约 3–4 GB 内存。不用时 `docker compose ... down`（加 `-v` 清数据）。
