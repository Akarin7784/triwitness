# W1 退出标准核对表

对照 PROJECT_PLAN §3。✅ 已由测试覆盖 · ⏳ 需真实调用（等 Eva 批准，空闲时段） · 👤 Eva 本人负责

| # | 标准 | 状态 | 证据 |
|---|---|---|---|
| 1 | spec001 DeepSeek AC | ✅ | `tests/unit/llm/*`；6 个录制夹具 `tests/fixtures/llm/deepseek/`，回放零网络 |
| 2 | spec002 AC1–8 | ✅ | `tests/integration/sandbox/test_docker_backend.py`（`sg docker -c "uv run pytest -m integration"`） |
| 3 | spec003 AC1–7 | ✅ | `tests/unit/tools/test_tools.py`、`tests/unit/harness/test_loop.py` |
| 3 | spec003 AC8 | ⏳ | 真实 deepseek-flash 跑 dev 首个任务（`csv-blank-line`），3 次中 ≥1 次通过 |
| 4 | spec004 AC1–5、AC7 | ✅ | `tests/unit/eval/test_task.py`、`test_grade.py`、`test_runner.py`、`tests/integration/eval/test_pipeline.py`（null 0/10，oracle 10/10，tamper 0/10 且全部标记） |
| 4 | spec004 AC6 | ⏳ | `tw eval run --config configs/runs/baseline-deepseek.yaml --live` 至少解决 1 题 |
| 5 | spec005 AC1–3、AC7 | ✅ | `tests/unit/telemetry/test_trajectory.py`、`tests/unit/cost/test_report.py` |
| 6 | `docs/agent-loop.md` | 👤 | W1-35，由 Eva 手写 |
| 6 | ai-native-log ≥5 条 | ✅ | `docs/ai-native-log.md` |
| 7 | 三个熔断开关单测 | ✅ | `tests/unit/cost/test_guard_ledger.py`（单任务 guard / 全局账本 / kill 文件与环境变量） |
| 7 | 高峰拒绝启动 eval | ✅ | `tests/unit/llm/test_gate.py`、`tests/unit/eval/test_runner.py` |
| 7 | 首跑校准 | ⏳ | W1-34：用真实 token 数修正 `tw eval estimate` 的默认值 |
| 7 | 每周花费 ≤ ¥5 | ✅ | `tw budget`（目前 ¥0.0054） |

## 剩余真实调用预估（空闲价，`tw eval estimate`）

| 运行 | 默认假设（2M 入 / 30k 出） | 保守实测假设（300k / 15k） |
|---|---|---|
| dev 10 题 × 1 | ¥3.56 | ¥0.95 |
| AC8：1 题 × 3 | ¥1.07 | ¥0.29 |

单任务预算上限（合成 ¥0.3，SWE ¥0.5）把总花费硬封顶在约 ¥4.9；高峰价翻倍。
