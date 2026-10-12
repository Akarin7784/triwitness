# 事件协议 tw-events/1（UI↔core 契约）

- 状态：**已冻结 v1**（W1-36）｜实现：`src/triwitness/core/events.py`｜Schema：`schemas/tw-events-1.schema.json`（脚本导出，勿手改）｜Fixture：`evals/fixtures/events/{success,failure,budget_exceeded}.jsonl`

## 1. 原则
- **唯一事实来源**：spec 005 的 `TrajectoryEvent`（JSONL，一行一个事件）。桌面端是只读订阅者；控制动作（取消、审批）走 `tw serve` 的 POST 接口（W2 以后）。
- **只增不改**：v1 只允许新增可选字段或新的 `kind`；读取方遇到不认识的 `kind` 直接忽略，payload 中不认识的字段也忽略。破坏性修改升到 `tw-events/2`。
- **安全**：事件里永远不出现 API key；工具输出只放引用（`output_ref`），不内联原文；`display` 写入前先脱敏。

## 2. 信封

```json
{"v":1,"seq":12,"ts":"2026-10-10T02:41:07Z","task_id":"t_01…","run_id":"r_01…","role":"executor",
 "kind":"tool_call","payload":{"tool":"run_tests","ok":false,"exit_code":1,"duration_ms":4210,
 "output_ref":"artifacts/12-output.txt","truncated":true,
 "display":"$ run_tests tests/test_auth.py → 1 failed","role_hint":"executor"},"trace_id":null,"span_id":null}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `v` | `1` | 信封版本 |
| `seq` | int ≥ 0 | 每个 run 内从 0 连续递增；SSE 的 `id` |
| `ts` | RFC 3339，带时区 | 存 UTC；UI 显示转北京时间 |
| `task_id` / `run_id` | str | `t_` / `r_` + ULID |
| `role` | Role \| null | planner / executor / verifier / reviewer / summarizer / classifier |
| `kind` | 见 §3 | |
| `payload` | object | 按 kind 校验；公共可选字段 `display`（≤200 字、一行人话、已脱敏）与 `role_hint`（planner / executor / verifier / reviewer / system，用于推流配色） |
| `trace_id` / `span_id` | str \| null | OTel 关联（W2） |

## 3. kind、payload 与 UI 呈现

| kind | payload 必填（可选） | UI 呈现 |
|---|---|---|
| `task_started` | `issue_title`、`repo`、`config_hash`（`issue_number`、`mode`、`harness`、`harness_hash`、`prompt_versions`、`memory`：`{fact_ids,episode_ids,skills}` 可选 stub） | 侧栏新会话；对话首条；记忆芯片可读 `memory` 或 `artifacts/memory.json` |
| `state_change` | `from`、`to`（TaskState） | 推流状态点颜色与角色点亮；标题栏状态 |
| `model_call` | `model`、`thinking`、`usage{input_tokens,cache_hit_tokens,cache_miss_tokens,output_tokens,reasoning_tokens}`、`cost_cny`、`latency_ms`（`served_model`、`peak`、`finish_reason`、`request_ref`、`response_ref`） | 推流一行；状态栏累计 ¥ 与命中率；`peak=true` 标红 |
| `tool_call` | `tool`、`ok`、`duration_ms`（`exit_code`、`output_ref`、`truncated`、`error_type`、`permission`、`permission_rule`、`message_ref`） | 推流 `$ tool …`；失败用赭红 |
| `context_event` | `action`（clear / compact）、`tokens_before`、`tokens_after`（`cleared`、`summary_chars`、`notes_chars`、`failures_recorded`、`summarizer`：model / fallback） | 推流细行“上下文清理 N 条” / “上下文压缩”（spec 007） |
| `checkpoint` | `label`（`ref`） | 推流细分隔线 |
| `loop_warning` | `signal`（repeat_action / consecutive_failures / no_progress）、`level`（1–3）（`detail`） | 推流警示行 |
| `hitl_request` | `request_id`、`question`、`options`（`blocking`） | 审批卡片（UI-13，W4 以后） |
| `hitl_response` | `request_id`、`answer`、`by` | 卡片结案 |
| `approval_requested` | `request_id`、`tool`（类别 Bash/PowerShell/Read/Edit/Fetch/Mcp）、`action`（已脱敏）、`reason`（`rule`、`rule_source`、`risk`、`options`、`suggested_rule`、`backend`、`timeout_s`） | 权限审批卡片：允许一次 / 本次任务内允许 / 总是允许 / 拒绝（spec 006 §7） |
| `mode_changed` | `from_mode`、`to_mode`、`risk`（normal / high）（`scope`、`by`、`backend`、`reason`） | `risk=high` 时显示常驻红色顶部横幅与红色模式徽标，直到下一条 `risk=normal` 的 `mode_changed` |
| `approval_resolved` | `request_id`、`decision`（allow / deny）、`by`（user / policy / timeout / cancelled）（`scope`、`saved_rule`、`comment`） | 卡片结案；`by=policy` 显示为“策略拒绝” |
| `verification` | `verdict`（pass / fail / inconclusive）（`evidence_ref`、`tests_passed`、`risk_level`、`clean_env`、`unverified_reason`） | 证据包卡片（UI-12）；`clean_env=unverified` 标“未在干净环境验证” |
| `review` | `model`、`variant`（`vendor_policy`，默认 single_vendor；`findings[]`） | 评审行，标“同厂商·变体” |
| `task_finished` | `status`（done / failed / budget_exceeded / stuck / needs_human / cancelled）（`finish_report`、`cost_report`） | 对话末条：summary、置信度、¥ |
| `error` | `type`、`message` | 红色行 |
| `reasoning_delta` | `call_id`、`index`、`text` | 对话流里的“思考”块：流式写入，正文开始后收成“思考了 N 秒”（UI-20） |
| `model_delta` | `call_id`、`index`、`text` | 对话流里的助手正文：逐片淡入 + 软光标，Markdown 渲染（UI-20）；书写推流不显示 |
| `sandbox_progress` | `stage`（git_init / archive / pull_image / container / fallback）、`status`（running / done / failed / warn）、`message`（`backend`） | 推流一行 + 对话流工具行（同阶段原地替换）；failed 赭红、warn 警示（0.5.0） |

增量事件（UI-20）只在交互运行（`tw run --jsonl`）里写；片段在 core 里按约 50ms / 48 字合并，已脱敏；按 `call_id` 归到同一次模型调用，`index` 从 0 连续。调用结束后照常有 `model_call`（带同一个 `call_id`），之后的 `tool_call` 也带 `call_id`，以及 `args_preview` / `output_preview`（各截断、已脱敏），供对话流里的工具行展开。eval / 批量运行不写增量。

## 4. 传输分三步

| 阶段 | 来源 | 任务 | 花费 |
|---|---|---|---|
| ① fixture | `evals/fixtures/events/*.jsonl` → 前端 `FixtureSource` | W1-36 → UI-09 | 0 |
| ② 回放 | `tw serve --replay <fixture>` → SSE → `SseSource` | W2 `tw serve` → UI-10 | 0 |
| ③ live | `tw serve` 读 `~/.triwitness/runs` 与 `evals/results` | 之后 | 计入预算 |

`tw serve`（W2 实现，接口先冻结）：只绑定 `127.0.0.1`、随机端口，令牌和端口写 `~/.triwitness/serve.json`（0600）；`GET /v1/health`、`GET /v1/runs?limit=`、`GET /v1/runs/{run_id}/events`（SSE，`id`=`seq`，支持 `Last-Event-ID`）、`GET /v1/budget`、`POST /v1/runs/{run_id}/cancel`；W4 加 `POST /v1/hitl/{request_id}`。

## 5. 维护
- 改模型 → `uv run python scripts/export_schema.py`；改 fixture 内容 → `uv run python scripts/make_event_fixtures.py`。测试会检查二者是否过期。
- W1-24（TrajectoryRecorder）完成后，用 FakeRouter 真实跑出 3 条轨迹替换手写 fixture，diff 只允许时间戳与 ID 不同。

变更：2026-10-11 新增 `model_delta` / `reasoning_delta`；`model_call`、`tool_call` 增加可选 `call_id`，`tool_call` 增加可选 `args_preview` / `output_preview`（UI-20，只增不改，v 仍为 1）。2026-10-10 新增 `mode_changed`（勇士模式，ADR-0005 §3.6）。2026-10-10 新增 `approval_requested` / `approval_resolved`，`tool_call`、`verification` 增加可选字段（ADR-0005，只增不改）。2026-10-10 `model_call` 增加 `request_ref` / `response_ref`、`tool_call` 增加 `message_ref`（W1-24 轨迹回放，只增不改）。

变更：2026-10-12 `task_started.memory` 可选 stub（桌面端「本次用了哪些记忆」）；权威列表仍是 `artifacts/memory.json`。
