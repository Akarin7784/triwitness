# Spec 016：任务工厂

- 状态：草稿（实现已完成，Eva 延后审阅，按默认采纳）｜负责人：Eva｜目标周：W2｜依赖：004
- 相关文档：04-detailed-design.md 第 6.1 节；实现说明 docs/design/task-factory.md；`scripts/task_factory.py`、`scripts/import_swe_rebench.py`、`src/triwitness/eval/suites.py`

## 1. 背景

W1 只有 10 个任务，统计上无法区分两个配置。W2 需要 30–50 个**可复现、低污染、许可证干净**的 Python 任务，并冻结 dev / test 切分，避免在 test 上调参。

## 2. 目标

1. **挖掘**：从公开数据集挑选“已合并、关联 Issue、同时改源码和测试”的 PR，优先较新的（污染风险低）。
2. **构建**：每个任务一个可复现镜像（依赖钉死版本）。
3. **校验去抖**：空 Agent 必须 0 分、参考解必须 1 分，各 3 次全对才收录。
4. **切分冻结**：dev / test / dev-smoke 写入 `evals/suites/*.yaml`，带内容 digest；test 需要 `--allow-test`。
5. **资源守卫**：磁盘不足时不开始新构建，构建后清理镜像。

## 3. 非目标

- 自己挖 GitHub PR（W2 直接用 SWE-rebench，它已经做了 Issue ↔ PR 关联与环境配置；自挖留到需要更新任务时）。
- 模型辅助写 Dockerfile（规则模板已足够；失败的直接丢弃）。
- 非 Python / 非 pytest 仓库。

## 4. 数据与产物

| 产物 | 内容 |
|---|---|
| `evals/factory/candidates.json` | 过滤后的候选（仓库、PR、许可证、合并日期、来源拆分） |
| `evals/factory/build_log*.json` | 每个候选的构建 / 校验状态（ok / fail / error + 原因） |
| `evals/factory/reserve.json` | 通过校验但未入选的备用任务 |
| `evals/tasks/{dev,test}/<id>/` | Harbor 格式任务（task.toml、instruction.md、environment/Dockerfile、tests/、solution/） |
| `evals/suites/{dev,test,dev-smoke}.yaml` | 冻结套件：id、source、created_at、difficulty、license、digest |

## 5. 行为细节

### 5.1 挖掘过滤（`mine`）

来源：`nebius/SWE-rebench-leaderboard`（月度拆分 2025-10～2026-03）+ `nebius/SWE-rebench` filtered。拒绝条件：非 pytest；需要系统包 / conda；安装命令复杂或依赖过重（torch / tensorflow / jax、uv sync、submodule 等）；Python 不在 3.9–3.13；源码改动 > 3 个文件或含非 .py；补丁 > 80 行；测试补丁改了非测试文件；F2P 不在 1–10、P2P 不在 3–400；测试 id 不是 pytest 节点；Issue 长度不在 150–6000 字；许可证不在宽松清单（SPDX 规范化）；同仓库最多 2 个。任务文本用 Issue 原文。

### 5.2 构建与校验（`build`）

1. 阶段一：按数据集安装命令装依赖，`pip freeze` 得到钉死版本。
2. 阶段二：用钉死版本生成最终 Dockerfile 并构建（tag = 内容哈希）。
3. 校验：null Agent → reward 0，oracle（参考解）→ reward 1，各 3 次；仓库已不存在的 P2P 用例（`not found`）自动剔除后重验。
4. 守卫：剩余磁盘 < `MIN_FREE_GB`（15G）或已用 ≥ `MAX_USED_PCT`（65%，box 规则 < 70% 留余量）不开始新构建，记 `error`，可 `--retry error` 续跑；每个任务完成后删自己的镜像并清 1 小时前的悬空层；批次结束 `docker image prune -f`。

### 5.3 切分（`split`）

- test = 最新的 leaderboard 任务（不足时用 filtered 较新的补齐，报告分开列）。
- dev = W1 的 10 个 + filtered 最旧的 5 个（污染风险最高，只用来调参）。
- dev-smoke = dev 中固定 5 个，每周冒烟防模型漂移。
- 难度为启发式（改动行数 / 文件数），人工抽检延后。
- `check_suite` 发现任务内容 digest 变化即报错；可重复运行 `split`（已搬运的任务复用）。

### 5.4 扩充套件 `ext`（W5-12，2026-10-11）

- 目的：把冻结套件里的有效任务从 50（dev 15 + test 35）扩到 ~100，**不改动已冻结的 dev / test**（跨周可比性）。
- `mine --exclude-existing --fetch-filtered N`：跳过所有已尝试过的实例（`evals/factory/**/build_log*.json` 与 task.toml 元数据），
  filtered 子集额外取 N 页；每仓库总数（含已有任务）≤ 2。
- 构建一律加固（匿名 ID、清洗 Issue 正文、禁用 hooks、删 `.git`），与 dev / test 不重叠。
- `split-ext --log evals/factory/ext/build_log.json --name ext --size 50`：把通过校验的任务搬到 `evals/tasks/ext/`，
  created_at 最新的 50 个写冻结套件 `evals/suites/ext.yaml`，其余写 `ext-reserve.yaml`（同样冻结、备用）；
  digest 同 5.3；失败任务留在被 git 忽略的 `_staging_ext/`。
- 2026-10-12 结果：185 个候选 → **109 个通过**（null 0 / oracle 1 各 3 次），ext 50（leaderboard 33 + filtered 17，
  2023-08…2026-02）+ ext-reserve 59（2016-11…2023-07）；dev 15 + test 35 + ext 50 = **100**。
  失败 76：构建 28（依赖安装 / 钉版本冲突 21、拉源码归档网络超时 4、缺 make / poetry 2、超时 1）、
  校验 39（缺测试依赖 15、测试 ID / pytest 参数不匹配 9、用例联网或环境失败 8、覆盖率门槛 4、版本漂移 3）、
  格式错误 9（test.sh 没跑到参数化用例 / 缺测试文件 6、绝对路径软链接 1、网络 2）。审计：ext 109 个 0 发现。
- 污染提示：filtered 子集里有 2016 年起的老实例，ext 只作补充样本（扩大 n、降低 MDE），报告里与 test 分开列。

## 6. 验收标准

- [x] AC1：候选 ≥ 80（138），含仓库、PR、许可证、合并日期（a71aa56）。
- [x] AC2：通过三次去抖校验的任务 ≥ 30（leaderboard 23 + filtered 18）。
- [x] AC3：dev 15 / test 35 / dev-smoke 5 冻结，digest 校验，test 需 `--allow-test`（e48010d、2227e22）。
- [x] AC4：磁盘守卫与镜像清理（4783bd1、2c62253）。
- [ ] AC5：难度人工抽检（延后：Eva 决定先完成功能，文档后补）。

## 7. 测试计划

`tests/unit/eval/test_suites.py`（冻结、digest、--allow-test）；`tw task validate` 在任务镜像上的集成测试；`scripts/task_factory.py` 是一次性脚本，靠构建日志复核。

## 8. 评测影响

- 报告按来源（leaderboard / filtered）分开列 Resolved@1，用于判断污染。
- test 集只在出报告时跑；所有调参只用 dev。

## 9. 开放问题

- ext 是否也设为“只出报告”（像 test 一样要 `--allow-test`）：目前允许在 ext 上跑消融（扩大 n），待 Eva 定。

- leaderboard 新月份发布后是否滚动替换 test（会破坏跨周可比性；倾向新增 test-v2 而非替换）。
- 自挖 GitHub PR 的必要性：等 SWE-rebench 无法覆盖目标仓库类型时再做。

## 10. 变更记录

- 2026-10-12：ext 50 + ext-reserve 59 冻结（5.4）。
- 2026-10-11：W5-12 扩充套件 ext（5.4）与磁盘占用率守卫（65%）。
- 2026-10-10：初稿（W2-05），实现 W2-20～23 已完成（a71aa56 … 2227e22），见 docs/design/task-factory.md。
