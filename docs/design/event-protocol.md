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
| `task_started` | `issue_title`、`repo`、`config_hash`（`issue_number`、`mode`） | 侧栏新会话；对话首条 |
| `state_change` | `from`、`to`（TaskState） | 推流状态点颜色与角色点亮；标题栏状态 |
| `model_call` | `model`、`thinking`、`usage{input_tokens,cache_hit_tokens,cache_miss_tokens,output_tokens,reasoning_tokens}`、`cost_cny`、`latency_ms`（`served_model`、`peak`、`finish_reason`） | 推流一行；状态栏累计 ¥ 与命中率；`peak=true` 标红 |
| `tool_call` | `tool`、`ok`、`duration_ms`（`exit_code`、`output_ref`、`truncated`、`error_type`、`permission`、`permission_rule`） | 推流 `$ tool …`；失败用赭红 |
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

v1 是**行级**事件；书写动画由 UI 的 WritingStream 自己生成。逐 token 推流（`model_delta`）以后作为可选 kind 再加。

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

变更：2026-10-10 新增 `mode_changed`（勇士模式，ADR-0005 §3.6）。2026-10-10 新增 `approval_requested` / `approval_resolved`，`tool_call`、`verification` 增加可选字段（ADR-0005，只增不改）。
