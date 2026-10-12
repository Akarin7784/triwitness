# 轨迹导出样例（W8-03）

源运行：`evals/results/2026-10-10T13-10-16/baseline-deepseek/csv-blank-line/1`（已解决，reward=1）。

| 文件 | 格式 |
|---|---|
| `openai-messages.json` | OpenAI Chat messages（SFT） |
| `trajectory-reward.json` | 逐步轨迹 + 标量奖励（RLVR） |
| `harbor-trial/` | Harbor 风格 trial（`result.json` + `verifier/reward.txt` + `agent/trajectory.jsonl`） |
| `replay.html` | 单文件 HTML 回放 |

生成：`tw traj export <run_dir> --out evals/fixtures/traj_export`（¥0）。
