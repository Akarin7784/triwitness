# ADR-0001：W1 接口与路径默认值（NOTES #2–#9）

- 状态：**已采纳**（Eva，2026-10-10 北京时间）
- 背景：starter specs 与设计文档（docs/architecture.md，原 04）在工具命名、完成契约、Tool 协议、成本字段、结果目录、`.tw/` 位置、复现测试路径、`--config` 上互相矛盾（规划 NOTES #2–#9）。原则：偏向设计文档，同时让 AI 编程助手和被驱动的模型都容易理解。

## 决定

| # | 议题 | 决定 |
|---|---|---|
| 2 | 工具命名与数量 | W1 8 个：`read_file`、`write_file`（仅新建）、`edit_file`、`list_files`、`grep`、`bash`、`run_tests`、`finish`。W2 增加 `git`、`notes`（= 9 个核心工具 + `finish`）。`repo_map`、`lsp` 只作消融开关；`ask_human` 在 W4。shell 工具叫 `bash`（不用设计文档的 `run`）：模型最熟悉，且不与 `run_tests` 混淆 |
| 3 | finish 契约 | 采用设计文档 §3.4：`summary`、`changes: [{path, kind, note}]`、`repro: {path, cmd} \| null`、`tests_run`、`tests_passed`、`confidence: float (0–1)`、`open_risks` |
| 4 | Tool 协议 | `name`、`description`、`Params`（pydantic 模型 → JSON Schema）、`side_effects: none \| workspace \| external`、`refetchable: bool`、`terminal: bool`；`async run(params, ctx) -> ToolResult` |
| 5 | 成本字段 | `Usage{input_tokens, cache_hit_tokens, cache_miss_tokens, output_tokens, reasoning_tokens}`；`CostLine{role, vendor, model, calls, usage, cost_cny, peak_calls}`；`CostReport{task_id, lines, total_cny, sandbox_cost_cny, budget_cny, cache_hit_rate, pricing_version, estimated}`，提供 `to_flat()` |
| 6 | 结果目录 | 评测：`evals/results/<北京时间戳>/<config>/<task>/<attempt>/`（不进仓库）；单次 `tw run`：`~/.triwitness/runs/<run_id>/`（`TW_HOME` 可配）；二者都含 `trajectory.jsonl` |
| 7 | `.tw/` 位置 | 沙箱内 `/workspace/.tw/`（在 `/workspace/repo` 之外），放 `NOTES.md` 与 `outputs/`；仓库内的 `.tw/` 一律排除出 diff |
| 8 | 复现测试路径 | 目标仓库内 `tests/tw_repro/test_issue_<n>.py`；没有 Issue 号时用 task_id 短码 |
| 9 | `--config` | `tw eval --config configs/runs/<name>.yaml`；RunConfig 再引用 `configs/harness/*.yaml` |
| 12 | 许可证 | Apache-2.0 |
| 15 | 模型 ID | 配置用别名 `deepseek-flash`；运行时记录 `served_model`；Leaderboard 展示快照名 |

## 影响与回写
- specs/002（#7）、003（#2 #3 #4、Budget）、004（#6 #9）、005（#5、事件格式）已在“变更记录”中注明。
- 事件格式 = UI↔core 契约 `tw-events/1`，见 `docs/design/event-protocol.md`。
