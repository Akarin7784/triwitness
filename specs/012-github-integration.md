# Spec 012：GitHub 集成（推送分支、开 PR、按风险决策、CI 回流）

- 状态：草稿（W5-01；W5-04 / W5-05 前半 / W5-06 已实现首版，**待 Eva 审阅**，见 §10）｜负责人：Eva｜目标周：W5｜依赖：006、008、009、010、011
- **GitHub App 暂缓**（Eva 未决定是否注册）：本版只走 `gh` CLI 或个人令牌（PAT）。App 相关内容（Webhook、Issue 标签触发、
  评论命令、安装令牌）列在 §8，接口已留好，实现顺延。
- 相关文档：04-detailed-design.md §2.2 步骤 1 / 9 / 10、§3.6、§3.7、§4.6、§7.2；spec 011 §5（幂等键）
- 代码：`github/pr.py`（v0.3.2：计划 / 推送 / 开 PR）、`github/publish.py`（W5：编排器发布器、风险策略）、
  `github/ci.py`（W5：CI 观察与失败日志）、`orchestrator/inprocess.py`（`_publish`）、`harness/config.py`（`GithubConfig`）、
  `harness/local_run.py`（`PublishOptions`）、`cli/main.py`（`tw run --open-pr`）

## 1. 背景

v0.3.2 已经能“审批后开 PR”：`tw pr plan`（不联网，生成审批卡）→ `tw pr open --yes`（REST 或 gh，先查同分支已有 PR 再开）。
但那是任务结束后的手动步骤，状态机里的 `PR_OPENED`、`CI_WATCH` 没有接上；CI 失败也不会回到 Executor。

## 2. 目标与非目标

目标：
1. 状态机接线：`PACKAGING →（AWAIT_PR_APPROVAL）→ PR_OPENED → CI_WATCH →（失败）EXECUTING → PACKAGING → PR_OPENED → … → DONE`，
   每次转换写进事件流（可审计、可重放）。
2. 按风险等级决定开不开 PR、要不要确认、是否 Draft（§4）。
3. CI 回流：观察 PR 分支的 CI，失败时把精简后的失败日志（不可信数据）交给 Executor 返工，最多 N 轮（§5）。
4. 所有对外副作用带幂等键（spec 011 §5），重复触发不产生重复 PR / 重复推送。
5. 只用 `gh` 或 PAT，不需要注册 App。

非目标：
- GitHub App、Webhook、Issue 标签触发、PR / Issue 评论命令（§8，App 决定后再做）。
- 回帖 Issue（需要知道来源 Issue；本地 `tw run` 没有来源 Issue）。
- 自动合并 PR（永远由人合并）。

## 3. 认证与推送

- 认证来源按顺序（`pr.detect_auth`）：`GITHUB_TOKEN` 环境变量（桌面端从系统凭据库取出后注入）→ 本机 `gh auth login`（推送走 `gh auth git-credential`，开 PR 用 `gh pr create`）。
- 最小权限（PAT 细粒度令牌）：只授权目标仓库；Contents 读写、Pull requests 读写、Checks 只读、Actions 只读（取失败日志）。
- 令牌只在推送 / API 调用时以 `GIT_CONFIG_*` 环境变量（`http.https://github.com/.extraheader`）或请求头注入，**不写进 remote URL、日志、轨迹、产物**（`pr.redact`）。
- 分支：`tw/<run_id>`（none 后端的 git worktree 分支）。`commit_branch` 用 `--no-verify` 提交（不跑仓库 hooks），排除 `.tw/` 等运行时目录；
  没有新提交就不推送。
- 只支持 none 后端（本地 worktree）；docker 后端的改动要先导出补丁（`tw pr plan`），`run_local` 遇到不支持的沙箱只记警告、不发布。
- 评测模式**永远不发布**（不推送、不开 PR）。

## 4. 风险策略（W5-05 前半）

配置 `github.pr_policy`（`harness/config.py`），默认：

| 风险 | 动作 | 含义 |
|---|---|---|
| L0 | confirm | 弹确认，同意后开 PR |
| L1 | confirm | 同上 |
| L2 | draft | 弹确认，同意后开 **Draft PR** |
| L3 | none | 不开 PR，分支保留，提示人工接手 |

- 动作取值：`auto`（不问直接开）/ `confirm` / `draft` / `none`。04 §3.7 原设计是“L0 可配置自动开”，但开 PR 是对外可见的动作，
  默认改为 L0 也确认；Eva 可在配置里把 L0 改成 `auto`（§10 Q1）。
- 风险来源：确定性验证的证据包 `risk_level` → 没有验证时用计划的 `estimated_risk` → 都没有时按 `github.unknown_risk`（默认 L2）。
- 确认走 HITL 通道（spec 011 §7）：`ApprovalRequested(tool="OpenPR")`，选项 `allow_once / deny`；终端 `tw run` 是 TTY 时问 `[y/N]`。
  没有审批通道（非交互）时不开 PR，收尾标签写“需要确认，可稍后在桌面端或 `tw pr open` 开”。
- PR 标题取 FinishReport 摘要首句（≤72 字），正文用证据包（`verification.pr_body`）；没有验证时正文写明“没有证据包”。

## 5. CI 回流（W5-06）

- 观察：`CI_WATCH` 轮询 PR 头提交的 check runs（`ci.watch`）。
  - gh 路径：`gh api repos/<o>/<r>/commits/<sha>/check-runs`（gh 2.46 没有 `pr checks --json`，所以直接调 API）；
    失败日志 `gh run view --job <id> --log-failed`，取不到时退回 `--log`。
  - 令牌路径：REST `check-runs` + `actions/jobs/<id>/logs`（httpx）。
  - 状态：`none`（宽限 `no_checks_grace_s` 内一直没有 check → 视为仓库没配 CI）/ `pending` / `failure` / `success` / `timeout`。
    失败结论 = `failure`、`timed_out`、`startup_failure`。
- 日志精简（`condense_log`）：去 ANSI 与时间戳，保留含 error / failed / assert / Traceback 的行及上下 2 行 + 末尾 40 行，
  上限 `log_max_chars`（默认 6000 字）。
- 返工：失败日志用 `<untrusted source="ci:...">` 包装（不可信数据），追加说明“修复代码让 CI 通过；不要修改 CI 配置、不要跳过或删除测试”，
  同一个 AgentLoop 续上（前缀不变，缓存可命中）。返工后提交并推送（`push:<n>`），再回 `CI_WATCH`。
- 上限 `github.ci.max_fix_rounds`（默认 2，0–5）；超过仍失败 → DONE，标签写“CI 仍失败（已返工 N 轮）”，PR 保留给人看。
- 简化：返工轮不重跑确定性验证与 Reviewer（CI 本身就是验证）；§10 Q2 待定。
- 改 CI 配置文件仍受 spec 010 `hitl.ci_changes` 约束（默认需要人确认）。

## 6. 幂等与审计

- 幂等键（spec 011 §5，`SideEffectLog`，TW_HOME/tw.db）：`<run_id>:open_pr:0`、`<run_id>:push:<n>`。先查后做；开 PR 前还会查同分支已有 PR，
  命中就沿用（`PrRef.reused`），不重复开。
- 产物：`pr.json`（url、编号、仓库、分支、sha、draft、是否沿用、风险）、`ci-<n>.json`（每轮 CI 结果）。
- 错误事件：`PublishFailed`（推送 / 开 PR 失败，任务结论不变，改动留在分支）、`CiWatchFailed`（取不到 CI 状态）。
- `run_local` 的 `summary.json` 增加 `pr`、`ci` 字段；`TaskResult` 同步增加。

## 7. 入口

- 终端：`tw run --open-pr [--pr-base main] [--pr-remote origin] [--watch-ci/--no-watch-ci]`；`--demo` 与 `--open-pr` 互斥。
- 桌面端：沿用 v0.3.2 的“审批后开 PR”（`tw pr plan` / `tw pr open`）；接入编排器流程放到桌面端 W6 迭代。
- 手动补开：`tw pr open`（与编排器共用幂等记录）。

## 8. 暂缓：GitHub App（W5-02 / W5-03 / W5-05 后半 / W7-08）

App 决定后再做，接口已留：
- 安装令牌：`Publisher` 只依赖“能推送 + 能开 PR + 能读 check runs”，换成 App 安装令牌只需新的认证来源（`detect_auth` 增加一档），
  令牌按任务申请、任务结束作废（W7-08）。
- Webhook（`webhook.py`，签名校验）：`issues.labeled`（标签 `triwitness`）→ 创建 Task（Issue 正文作为不可信内容）→ 交给编排器；
  `check_run.completed` 替代轮询。
- 评论命令：`/tw approve`、`/tw reject <原因>` 映射到同一个 HITL 请求（`request_id` 写在 PR 正文隐藏注释里），写审计日志。
  没有 Webhook 时只能轮询评论，噪声与延迟都差，所以不在 PAT 路径上做。
- 回帖 Issue：开 PR 后在来源 Issue 回帖链接（幂等键 `<task_id>:comment:<n>`）。

## 9. 测试

- `tests/unit/github/test_ci.py`：check run 解析、状态汇总、日志精简、超时 / 无 CI 宽限、gh 与令牌两条路径（假 runner / MockTransport）。
- `tests/unit/orchestrator/test_publish.py`：L3 不开、auto + CI 成功、无审批通道、Draft + 拒绝、CI 失败 → 返工 → 推送（返工请求里有
  untrusted 包装的日志）、返工上限 0、评测模式不发布；真实 `GitHubPublisher` + 本地裸仓库 + MockTransport：推送、开 PR 只开一次、`push(1)`。
- 待做（需要 Eva 授权一个测试仓库）：真实仓库上制造一次 CI 失败并被自动修复（W5-06 验收）。

## 10. 待 Eva 决定

1. **L0 默认动作**：现在是 `confirm`（开 PR 对外可见）；要不要改成 `auto`？
2. **CI 返工后是否重跑验证 / Reviewer**：现在不重跑（省钱、CI 即验证）；如果 CI 覆盖弱，可能放过回归。
3. **GitHub App**：是否注册（单仓库安装、最小权限）；不注册则 §8 全部保持暂缓，W5-14 Demo 改为“`tw run --open-pr` 开出带证据包的 PR”。
4. **测试仓库**：W5-06 验收需要一个可推送的测试仓库（建议私有、只给细粒度 PAT）。
