# Harbor 集成（W5-13）

[Harbor](https://harborframework.com)（0.24.0）是 Terminal-Bench 团队的评测框架：起任务容器、跑 Agent、在同一容器里跑 verifier 写奖励。
TriWitness 用它做**外部对照**，不替换自己的评测流水线（`tw eval`：diff 判分、冻结套件、账本）。

## 两个方向

1. **我们的任务 → Harbor**：`evals/tasks/**` 的目录格式本来就和 Harbor 一致（`task.toml`、`instruction.md`、
   `environment/Dockerfile`、`tests/test.sh` 写 `/logs/verifier/reward.txt`、`solution/solve.sh`）。box 上实测：
   `harbor run -p evals/tasks/dev/csv-blank-line -a oracle` 奖励 1.0，`-a nop` 0.0。
2. **TriWitness Agent → Harbor 任务**：`triwitness.integrations.harbor_agent:TriWitnessAgent`（`BaseAgent` 子类）。
   Agent 循环在宿主进程里跑，工具调用经 `HarborSandbox`（`integrations/harbor_sandbox.py`）进容器执行：
   `exec` 外包 `timeout -k 5 N bash -c`、输出截断；读文件走 `base64`，写文件走 `upload_file`；不支持快照 / diff
   （终端类任务不是 git 仓库，判分由 Harbor 做）。只用 deepseek-flash，`run_task(mode="eval")`，账本类别 `harbor-external`。
   box 实测：csv-blank-line 奖励 1，10 步，¥0.0126，缓存命中 87%。

```
uv run --with harbor==0.24.0 harbor run -p evals/tasks/dev/csv-blank-line \
  -a triwitness.integrations.harbor_agent:TriWitnessAgent [--ak harness=baseline] [--ak thinking=true] -o /tmp/hjobs
```

Harbor 不是依赖（只在 `uv run --with` 时出现）；`harbor_agent.py` 在没装 harbor 时不可导入，单测只测 `HarborSandbox`。

## Terminal-Bench 2.0 子集（Eva 本机）

- 数据：laude-institute/terminal-bench-2（Apache-2.0）固定提交 `2fd12b88aafd`，89 题；取 10 题（easy 4 + 专家估时 ≤ 30 分钟、
  无 GPU、不下载大模型的 medium 6），列表在 `scripts/harbor_external.py`。
- 为什么不在 box 上跑：TB2 的 verifier 运行时联网装 uv / pytest，Harbor 用 docker compose 自定义网络，而 box 的 Docker
  自定义网络没有 DNS（默认 bridge 正常），oracle 在 box 上也拿 0 分。
- 运行：Windows `scripts/windows/run-harbor-tb2.ps1 [-Smoke]` → WSL2 里 `scripts/wsl/run-harbor-tb2.sh`
  （Docker Desktop 的 WSL 集成；密钥经 `WSLENV=DEEPSEEK_API_KEY/u` 透传）；高峰不开始；结果 `report.md` + 账本打包成 zip。
- 预估：10 题约 ¥0.5–2（粗估每题 ¥0.05–0.2，终端题步数多；以账本为准），冒烟 1 题 ≈ ¥0.05–0.2。
- 解读：n = 10，只作外部参照；TB2 是有状态终端任务，与 dev / test 的 SWE 类补丁任务不可直接比较。
