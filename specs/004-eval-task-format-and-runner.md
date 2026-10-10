# Spec 004：评测任务格式与运行器

- 状态：草稿｜负责人：Eva｜目标周：W1（v0，10 个任务）→ W2（30–50 个任务）｜依赖：002、003
- 相关文档：04-detailed-design.md 第六节

## 1. 背景

评测平台从第一周就要有：没有评测，任何 harness 改动都只是"感觉更好"。任务格式兼容 Harbor（Terminal-Bench 2.0 使用的框架），方便互通，也方便以后直接跑公开数据集。

## 2. 目标

1. 定义任务目录格式（Harbor 兼容 + TriWitness 扩展字段）。
2. `tw eval` 命令：按套件 × 配置批量运行，支持并发、断点续跑、重复次数。
3. Grader：在 Agent 结束后，把隐藏测试放进**新的**干净沙箱判分。
4. 指标与报告 v0：Resolved@1、每任务成本、每解决任务成本、步数、耗时，输出 JSON + Markdown。
5. 10 个 dev 任务（W1）。

## 3. 非目标

- 任务自动采集工厂（spec 016，原规划编号 006 让给权限 spec，见 ADR-0005）。
- 统计检验与消融矩阵（W5）。
- Leaderboard 网页（W8）。

## 4. 任务格式

```text
evals/tasks/<suite>/<task-id>/
├── task.toml
├── instruction.md            # 给 Agent 的问题描述（类似 Issue 正文）
├── environment/
│   └── Dockerfile            # 构建任务镜像：固定提交的仓库 + 依赖
├── tests/                    # 隐藏测试，Agent 不可见
│   ├── test.sh               # 判分入口，写 /logs/verifier/reward.txt
│   └── ...                   # F2P / P2P 测试文件
└── solution/
    └── solve.sh              # 参考解，用于校验任务本身有效
```

`task.toml`：

```toml
schema_version = "1.3"             # Harbor 字段（不是 version）；只接受 1.x

[task]
name = "triwitness/dev-001-csv-empty-rows"   # org/name；name 部分必须与目录名一致（即任务 id）
description = "..."
keywords = ["python", "bugfix"]

[metadata]                         # Harbor 自由字段；TriWitness 约定如下
source = "synthetic"            # synthetic | github-issue | swe-rebench | ...
repo = "https://github.com/<owner>/<repo>"
base_commit = "<sha>"
difficulty = "easy"              # easy | medium | hard
tags = ["python", "bugfix"]
created_at = "2026-10-12"        # 必填，用于防污染（与模型发布日期比较）

[agent]
timeout_sec = 1800

[verifier]
timeout_sec = 600

[environment]
network_mode = "no-network"      # Harbor：public（默认）| no-network | allowlist；TriWitness 任务必须 no-network
cpus = 2
memory_mb = 4096
workdir = "/workspace/repo"
# docker_image = "..."           # 可选：用现成镜像代替 environment/Dockerfile

[tw]                             # TriWitness 扩展（Harbor 忽略）；未知键报错
test_cmd = "pytest -q"
fail_to_pass = ["tests/test_io.py::test_empty_rows"]   # 不能为空
pass_to_pass = ["tests/test_io.py"]
max_cost_cny = 0.8
```

> Harbor 字段名以 [Harbor 文档](https://www.harborframework.com/docs/tasks) 为准；实现时先对照官方示例任务校验，不一致的地方以官方为准并更新本 spec。

`test.sh` 约定：运行 F2P 和 P2P；全部通过写 `1`，否则写 `0` 到 `/logs/verifier/reward.txt`；同时把明细写到 `/logs/verifier/`（示例任务用 pytest 自带的 `--junitxml=/logs/verifier/junit.xml`，不引入额外依赖）。

## 5. 接口

```python
class EvalTask(BaseModel):
    id: str
    path: Path
    meta: TaskMeta
    tw: TwExt


class RunConfig(BaseModel):
    name: str  # 例如 "baseline-deepseek"
    models: dict[Role, str]  # 覆盖 configs/models.yaml
    harness: dict  # 覆盖 configs/harness/baseline.yaml
    seed_note: str | None = None


class TaskResult(BaseModel):
    task_id: str
    config: str
    attempt: int
    resolved: bool
    agent_status: str  # finished / budget_exhausted / stuck / error
    agent_claimed_success: bool  # Agent 自己说"修好了"
    cost_cny: float
    tokens_in: int
    tokens_cached: int
    tokens_out: int
    steps: int
    wall_s: float
    trajectory_id: str
    error: str | None = None


class EvalRunner:
    async def run(
        self,
        suite: str,
        configs: list[RunConfig],
        *,
        attempts: int = 1,
        concurrency: int = 4,
        limit: int | None = None,
        resume: bool = True,
    ) -> Path: ...  # 返回结果目录
```

CLI：

```bash
tw eval --suite dev --config configs/runs/baseline-deepseek.yaml --attempts 1 --concurrency 4
tw eval report evals/results/2026-10-14T21-00-00/        # 重新生成报告
tw task validate evals/tasks/dev/dev-001-*      # 校验任务有效性
```

## 6. 行为细节

1. **任务校验**（`tw task validate`）：构建镜像 → 不打补丁跑 `test.sh`，reward 必须为 0 → 应用 `solve.sh` 后跑，reward 必须为 1。两项都满足才算有效任务。
2. **运行**：构建/复用镜像（按 Dockerfile 内容哈希打 tag）→ 创建沙箱（不含 tests/、solution/）→ 跑 AgentLoop → 导出 diff。
3. **判分**：新建干净沙箱（同镜像）→ 应用 diff → 复制 `tests/` 进去 → 执行 `test.sh` → 读 reward。**Agent 的沙箱永远看不到 tests/ 和 solution/。**
4. **结果目录**（ADR-0001 #6）：`evals/results/<时间戳>/<config>/<task-id>/<attempt>/{result.json, patch.diff, trajectory.jsonl, verifier.log}`；时间戳为 Asia/Shanghai；目录不进仓库。单次 `tw run` 的轨迹写在 `~/.triwitness/runs/<run_id>/`（`TW_HOME` 可配）。
5. **断点续跑**：已有 `result.json` 的跳过。
6. **成本预估**：开始前按"任务数 × 配置数 × 尝试次数 × 历史平均每任务成本"估算并打印，超过 `--max-total-cny`（默认 10）或本周预算信封时不开始；DeepSeek 高峰时段拒绝启动（`--allow-peak` 需显式确认，ADR-0002）。
7. **评测模式**：路由器使用 `mode="eval"`（禁止回退）。
8. **报告 v0**：每个配置一行：Resolved@1、解决数/总数、总成本、每任务平均成本、每解决任务成本、平均步数、平均耗时、**虚假成功数**（`agent_claimed_success and not resolved`）。

## 7. 验收标准

- [x] AC1：`evals/tasks/dev/` 下有 10 个任务，全部通过 `tw task validate`。
- [x] AC2：Agent 沙箱内 `ls /` 和全盘 `find` 都找不到 tests/ 和 solution/ 的内容（集成测试）。
- [x] AC3：用"什么都不改"的空 Agent 跑 dev 套件，Resolved = 0；用"直接执行 solve.sh"的作弊 Agent，Resolved = 10（验证判分管线）。
- [x] AC4：中途 Ctrl-C 后重跑，已完成的任务不再执行。
- [x] AC5：报告 Markdown 包含第 6.8 节所列所有列，数值与 result.json 汇总一致（单测）。
- [ ] AC6：`configs/runs/baseline-deepseek.yaml` 齐全，在空闲时段至少跑通 1 个任务（三家版本 ⏸）。
- [x] AC7：成本预估超过上限时不开始运行。

## 8. 测试计划

- 单测：task.toml 解析、报告聚合、成本预估、断点续跑逻辑。
- 集成：AC2、AC3（空 Agent 和作弊 Agent 不调模型，免费）。
- 手动：AC6（花钱，W1 末尾跑一次）。

## 9. 评测影响

这就是评测本身。任何改动 Grader 的 PR 都必须重跑 AC3。

## 10. 开放问题

- 10 个 dev 任务从哪来？→ W1：自己构造 5 个合成 bug（小型 Python 库）+ 从 SWE-rebench 等公开集挑 5 个小任务（注意许可证）；W2 扩展到 30–50 个。
- 是否直接用 Harbor 作为运行器？→ W1 自写轻量 Runner 以便讲清原理；同时保证格式兼容，W5 评估接入 Harbor 跑 Terminal-Bench。

## 11. AI 实施提示

- 先写空 Agent 和作弊 Agent，判分管线验证通过后再接真实 Agent。
- 镜像构建慢：按 Dockerfile 哈希缓存；CI 中只跑 2 个最小任务。
- 不要让 Grader 复用 Agent 的沙箱。

## 12. 变更记录

- 2026-10-10：初稿
- 2026-10-10：按 ADR-0001（W1 接口与路径）与 ADR-0002（预算与模型策略）修订：结果目录 evals/results/、--config 指向 configs/runs/*.yaml、--max-total-cny 默认 10 + 空闲闸门、AC6 只要求 DeepSeek。
- 2026-10-10：按 ADR-0005 修订：评测强制 docker 后端、非交互（权限 ask 视为 deny）、只用 default 层 + 运行配置中的权限规则，规则集哈希计入 config_hash；none 后端运行不进入报告。
- 2026-10-10（W1-26 实现）：对照 Harbor 官方文档（docs.harborframework.com/tasks/configuration）改字段：`version` → `schema_version`（1.x）；任务 id 从 `[metadata] id` 移到 `[task] name = "org/<id>"`（id = 目录名）；`network = "none"` → `[environment] network_mode = "no-network"`（Harbor 默认 public，所以 TriWitness 要求显式写）；新增可选 `workdir`、`docker_image`；`created_at` 必填；`[tw]` 未知键报错，其余表允许 Harbor 未来新增字段。`tw task validate` 实现：镜像 tag = `tw-task/<id>:<environment/ 内容哈希，换行无关>`，已存在则复用；验证容器 `network_mode=none`、带 `tw.managed` 标签、跑完即删；`--static` 只查格式（不需要 Docker）。第一个示例任务 `evals/tasks/dev/csv-blank-line`。
- 2026-10-10（W1-28～W1-32 实现）：① test.sh 约定改为**把隐藏测试复制进仓库再跑**（与 SWE-bench 相同；合成任务放 `tests/test_*_hidden.py`，导入任务放 `tests/files/<原路径>`），这样仓库自己的 conftest / 配置会生效，防作弊必须靠 Grader；`load_task` 静态检查 F2P/P2P 每个 id 都在 test.sh 里、对应文件存在。② Grader 应用 diff 前**丢弃测试基础设施改动**（conftest.py、pytest.ini、tox.ini、setup.cfg、pyproject.toml、sitecustomize/usercustomize、*.pth、已有测试文件；新增测试文件忽略但不算篡改），结果记 `tamper_paths` / `ignored_paths`；任务可用 `[tw] protected` 追加 glob。Grader 以 uid 1000 跑 test.sh（沙箱 cap_drop ALL）。③ 除 §11 的空 Agent / 作弊 Agent（执行 solve.sh）外新增**篡改 Agent**（只放让所有测试“通过”的 conftest.py 并声称成功）：必须判 0、计入虚假成功；集成测试同时证明不过滤时该攻击确实能拿到 reward 1。④ CLI 为 `tw eval run --suite dev --config … | --agent null|oracle|tamper [--live] [--allow-peak] [--max-total-cny 50] [--out 目录续跑]` 与 `tw eval report <dir>`；默认离线（llm Agent 走回放缓存，未录制则该 attempt 记 ReplayMiss，不联网）；TW_LLM_MODE 非 replay 而未加 --live 拒绝启动；--live = record 模式。⑤ 费用护栏只在 live 生效：高峰拒绝启动、预估（历史平均每任务成本，无历史时按 2M 输入 / 3 万输出估）> 上限不开始、全局账本与类别信封（默认 baseline）预检、跨入高峰停止派发（未跑的留给续跑）。⑥ 基础设施错误（Docker 等）不写 result.json，续跑时重试，记录在 errors.json。⑦ 报告 v0 另加缓存命中率（<90% 告警）与篡改列。⑧ dev 套件 10 个：5 个合成 + 5 个 SWE-rebench（`scripts/import_swe_rebench.py` 可复现：GitHub tarball @ base_commit、依赖按数据集 pip freeze 固定、镜像无 .git）。AC1–AC5、AC7 通过；AC6 需真实调用，待 Eva 确认。
