# Spec 010：角色与编排（Planner / Reviewer / InProcessOrchestrator / 显式状态机）

- 状态：草稿（W4-01，已实现首版；**待 Eva 审阅**，见 §11 待决事项）｜负责人：Eva｜目标周：W4｜依赖：003、005、008、009
- 相关文档：04-detailed-design.md §2.2、§3.1–3.3、§3.6–3.7；`research/2026-10-11-claude-code-core-loop.md`（下称 CC 报告）；
  `research/2026-10-11-landscape.md`（下称行业扫描）
- 代码：`core/state_machine.py`、`roles/{contracts,planner,reviewer}.py`、`orchestrator/inprocess.py`、`store/sqlite.py`、
  `harness/loop.py`（并行只读工具、悬空调用补结果、续写返工）、`llm/http.py`（重试）

## 1. 背景

W1–W3 只有 Executor 单角色 + 确定性验证（+ 可选 Verifier 模型）。W4 把 04 §2.2 的完整流程接上：
**规划 → 复现 → 修复 → 验证 → 评审 → 打包**，并让“谁能改任务状态”变成一张可审计的表。

CC 报告的核心结论：Claude Code 的主循环没有显式状态机，结束条件是“模型不再调工具 / 上限 / Stop hook 否决停止”。
我们**保留显式状态机和 `finish` 工具**（可审计、可复跑、证据包的基础），但借鉴它的几条机制（§7）。

## 2. 目标

1. 显式状态机：合法迁移是一张表；只有编排器能迁移；每次迁移写 `state_change` 事件；非法迁移抛 `IllegalTransition`。
2. 事件持久化：任务与全部事件写 SQLite（`~/.triwitness/tw.db`，W4-15），进程重启后 `tw tasks` 能列出任务与状态；
   状态机可从事件重放（`TaskStateMachine.replay`），供断点续跑与审计使用。
3. 角色契约：`submit_plan(Plan)`、`submit_review(Review)` 两个**终止工具**；Verifier 的 `submit_verdict` 改走同一个
   结构化输出降级助手（`roles/contracts.structured_call`）。
4. Planner、Reviewer 两个角色：只读工具子集（read_file / list_files / grep / repo_map / git），在自己的 AgentLoop 里跑，
   **只通过编排器**把结构化结果交给下一个角色（不共享消息历史）。
5. `InProcessOrchestrator`：`tw run`、桌面端、`tw eval` 共用；角色开关由 harness 配置决定，关掉时行为与 W3 完全一致
   （基线可复现）。
6. 单厂商（deepseek-flash only，**永不** deepseek-v4-pro）端到端跑通；Reviewer 用“同厂商异构变体”并在证据包里标注。

## 3. 非目标（本 spec 不做）

- TemporalOrchestrator（W4-11/12，P2）、GitHub App（W5，Eva 未决定注册，跳过）、CI 回流（W5）。
- 跨厂商互审（DF-04/06，资金到位后）；`cross_vendor` 只保留路由约束与 FakeRouter 测试。
- Planner 派“调查子 Agent”（04 §3.5 子 Agent 分片）——留到 W5 以后，看评测数据是否需要。

## 4. 状态机（`core/state_machine.py`）

迁移表 = 04 §3.1，加上现有流程里已经存在的“跳过某角色”的边：

| 从 | 到 |
|---|---|
| RECEIVED | PREPARING |
| PREPARING | PLANNING、REPRODUCING、EXECUTING（不启用 Planner / 无复现要求 / 续跑） |
| PLANNING | AWAIT_PLAN_APPROVAL、REPRODUCING、EXECUTING |
| AWAIT_PLAN_APPROVAL | REPRODUCING、EXECUTING（批准）、CANCELLED（拒绝） |
| REPRODUCING | EXECUTING |
| EXECUTING | VERIFYING、REVIEWING（未开验证）、PACKAGING |
| VERIFYING | EXECUTING（验证失败且未超轮次）、REVIEWING、PACKAGING（未开评审） |
| REVIEWING | EXECUTING（阻断问题且未超轮次）、PACKAGING |
| PACKAGING | AWAIT_PR_APPROVAL、PR_OPENED、DONE |
| AWAIT_PR_APPROVAL | PR_OPENED、CANCELLED、DONE |
| PR_OPENED | CI_WATCH、DONE |
| CI_WATCH | EXECUTING、DONE |
| 任一非终态 | NEEDS_HUMAN、BUDGET_EXCEEDED、FAILED、CANCELLED |

终态：DONE、NEEDS_HUMAN、BUDGET_EXCEEDED、FAILED、CANCELLED。同态迁移、从终态迁出一律非法。

- 角色**不能**改状态：角色只返回结构化结果（Plan / FinishReport / Verdict / Review），编排器决定迁移。
- `TaskStateMachine.replay(state_changes)`：按事件顺序重放并逐条校验，得到当前状态（续跑 / 审计）；历史里有非法迁移直接报错。
- 评测模式自动审批（04 §3.1）：`eval_auto_decision(risk)` → L0–L2 批准、L3 拒绝（见 §11 Q2）。

## 5. 角色契约（`roles/contracts.py`）

| 工具 | 模型 | 谁用 |
|---|---|---|
| `submit_plan` | `PlanSubmission`（= `core.models.Plan` 去掉 task_id / model，由编排器补） | Planner |
| `submit_review` | `Review{verdict: approve / request_changes, summary, findings[ReviewFinding]}` | Reviewer |
| `submit_verdict` | `Verdict`（W3-10，不变） | Verifier |

- `SubmitTool`：终止工具（`terminal=True`），参数非法时返回带字段名的错误让模型修正（AgentLoop 的普通工具错误路径），
  成功时把校验后的对象放进 `data.submission`，AgentLoop 以 `finished` 结束并把它放进 `LoopOutcome.submission`。
- `structured_call`（单次调用 + 降级链，04 §3.3 原则 3）：`tool_choice=auto` + 提交工具 → 参数非法时回传校验错误，
  最多修复 2 次 → 模型没调工具时从 content 抽 JSON → 仍失败返回 `path=failed`。Verifier 改为调用它（请求逐字节不变，
  回放夹具不用重录）。
- 角色 Loop 里模型只说话不调工具：沿用 AgentLoop 的 `no_tool` 提醒；最终 `stuck` 时再用 `extract_json` 从最后一条
  assistant 文本里抽一次（Planner 抽不到 → 无计划继续，Reviewer 抽不到 → 记为“评审无结论”，不阻断）。

## 6. 角色

### 6.1 Planner（`prompts/planner.md`）
- 输入：Issue（`<untrusted>`）、AGENTS.md 摘要（稳定前缀）、基线失败测试数。
- 工具：read_file、list_files、grep、repo_map、git（只读）+ submit_plan。
- 输出要求：根因假设、要改的文件、**可执行的验收标准**（test / command / manual）、复现策略、步骤、风险预估、
  `needs_approval`、不确定时写 `open_questions`。
- 回合上限 `orchestration.planner.max_turns`（默认 30）。
- Plan 交给 Executor 的方式：以 `<plan>` 块拼进任务描述（Plan 由模型基于不可信 Issue 产出，按数据对待）；
  验收标准同时交给 Verifier 模型（`VerifierInput.criteria`）；`root_cause_hypothesis` 写进证据包 `root_cause`。

### 6.2 Reviewer（`prompts/reviewer.md`、`prompts/reviewer-checklist.md`）
- 输入：Issue、Plan（如有）、diff、验证结论与关键证据摘要、Executor 自述。
- 工具：只读 + submit_review。**只报有依据的问题**：每条带文件 / 行号 / 严重级别 / 修复建议，禁止风格挑刺。
- `blocker` 才会退回 Executor；major / minor / nit 进证据包，major 计入风险分（spec 009 `review_major_open`）。
- 单厂商变体（04 §5.2 规则 1，W4-08）：主评审 `adversarial`（flash 思考 effort=max + 对抗式提示，独立上下文）；
  共识模式的第二评审 `checklist`（flash 思考 effort=high + 清单式提示，独立上下文）。证据包 `review_variant`、
  `vendor_policy=single_vendor` 标注“同厂商评审”。

### 6.3 返工回路（借鉴 CC Stop hook 的“有上限的不许停”）
- Reviewer 给出 blocker 且 `review_rounds < orchestration.reviewer.max_rounds`（默认 2）→ REVIEWING → EXECUTING，
  **在同一个 Executor 上下文里续写**一条评审反馈（只追加，缓存命中；不像验证返工那样新开上下文），Executor 再次
  `finish` 后重新走 VERIFYING → REVIEWING。
- 达到上限仍有 blocker：不再返工，进入 PACKAGING；任务状态仍为 done（改动保留给用户），但证据包里 blocker 保持 open，
  风险分 +25（review_major_open）并加下限 `floor:review_blocker_unresolved = L2`，PR 正文顶部写明（§11 Q3）。
- 共识模式（行业扫描建议，可选，默认关）：`orchestration.reviewer.consensus: true` 时并行跑两个变体，
  **两个都给 blocker 才算阻断**；只有一方给的 blocker 降为 major 记入证据包。用于压低单评审误报导致的无效返工。

## 7. 来自 CC 报告的 Loop 改动（`harness/loop.py`、`llm/http.py`）

| 机制 | 做法 | 开关 |
|---|---|---|
| 只读工具并行 | 同一轮里**连续的**只读工具（read_file / list_files / grep / repo_map / git）并发执行，结果按原顺序写回；有副作用的工具保持串行，且不会越过它重排 | `loop.parallel_read_tools`（默认 true；只影响耗时，不影响消息内容） |
| 中断时补结果 | 一轮里任何调用之后提前结束（finish 在中间、NeedsHuman、沙箱错误、取消），给还没有结果的 tool_call 补一条 `[未执行：…]` 错误结果，保证消息历史合法（每个 tool_call 后面都有结果），可以续写 | 始终 |
| 续写返工 | `AgentLoop.run(..., continue_with=反馈)`：沿用已有消息历史，只追加一条 user 反馈 | 评审返工使用 |
| API 重试 | 429 / 5xx / 超时：默认重试 10 次，指数退避 1s 起、单次上限 32s、带抖动（原 2 次 1s/4s）；持久模式（`TW_LLM_PERSISTENT_RETRY=1` 或 models.yaml `retry.persistent`）下 429 / 503 一直重试（单次上限 60s，总等待上限 6h） | `configs/models.yaml` `retry` |

不采纳：用“模型不再调工具”作为结束条件（保留 finish 契约）；任务清单工具（W5 消融实测后再定）。

## 8. 编排器（`orchestrator/inprocess.py`）

```
RECEIVED → PREPARING →（planner）PLANNING →（需审批）AWAIT_PLAN_APPROVAL
        →（repro-first）REPRODUCING → EXECUTING →（verify）VERIFYING ⇄ EXECUTING
        →（reviewer）REVIEWING ⇄ EXECUTING → PACKAGING → DONE
```

- `run_task(...)` 保留为兼容入口，内部构造 `InProcessOrchestrator` 并运行；`tw run`、桌面端、`tw eval` 都经过它。
- 角色开关（harness 配置 `orchestration`）：`planner.enabled`、`reviewer.enabled` 默认 false——基线 / W2 / W3 配置哈希与行为不变；
  `configs/harness/orchestrated-1m.yaml` = `long-context-1m.yaml` + Planner + Reviewer（`tw run --harness orchestrated-1m`）。
- 所有模型调用经同一个 Router → LLMClient → 全局账本（ledger），角色 = planner / executor / verifier / reviewer，
  task 成本卡按角色分行。
- 计划审批（04 §3.7，见 §11 Q1）：`orchestration.plan_approval`
  - `min_risk`（默认 **L2**）：Plan.estimated_risk ≥ 它时需要确认；另外 `needs_approval=true`、`open_questions` 非空、
    `affected_files` 命中 risk.yaml 的 build_files / sensitive_paths 时也需要确认。
  - 交互（桌面端 / `tw run --jsonl`）：复用权限审批通道，发 `approval_requested(tool="Plan")`，用户批准 / 拒绝写
    `approval_resolved`（审计日志）；拒绝附言回给 Planner 不重规划，直接 CANCELLED。
  - 非交互（终端 `tw run`、无审批通道）：`unattended: needs_human`（默认）→ NEEDS_HUMAN；可改 `approve`。
  - 评测：按 §11 Q2 全部自动批准（含 L3），写 `approval_resolved(by="policy")`，禁止人工介入。
  - 续跑（§11 Q6）：停在计划确认时落续跑点，`--resume` 沿用原计划重新请求确认。

### 8.1 ask_human（W4-10）

- Executor 工具 `ask_human(question, blocking, options, context)`；orchestrated-1m 默认启用，回答视为用户指示（trusted_tools）。
- blocking=true：交互运行发 `approval_requested(tool="AskHuman")`；用户输入的文字（批准 / 拒绝附言）作为“用户的回答”回给模型，
  没写字时批准 = “是 / 同意”，拒绝 = “否 / 不同意”；写 `approval_resolved(by="user")`。无审批通道（非交互）→ 任务停在
  NEEDS_HUMAN 并落续跑点。
- blocking=false：不打断，工具结果要求模型按最佳判断继续，并在 finish 的 open_risks 里写明假设（问题本身暂不单独进证据包，W5 再接）。
- 评测：不允许人工介入，不发提问，写 `approval_resolved(by="policy", decision="deny")`，让模型按最佳判断继续并写明假设。

### 8.2 跨厂商评审（W4-08）

- `orchestration.reviewer.vendor_policy: cross_vendor` 时，Reviewer 的 loop 把 Executor 的厂商传给 Router，路由排除同厂商候选。
- 编排器在第一次模型调用前预检：Reviewer 路由（含 fallback）里没有异厂商模型 → 直接 FAILED（不花钱）。
- 只用 FakeRouter 测试（本轮只允许 deepseek-flash，不发真实跨厂商请求）。

## 9. 存储（`store/sqlite.py`，W4-15）

- `tasks(task_id PK, run_id, title, repo, harness, mode, state, status, cost_cny, created_at, updated_at)`、
  `events(task_id, run_id, seq, ts, kind, role, payload JSON, PK(run_id, seq))`。
- `TaskStore.observe(event)` 订阅 TrajectoryRecorder：每条事件写 events；task_started / state_change / task_finished 更新 tasks。
- 默认路径 `TW_HOME/tw.db`；WAL 模式；`tw tasks [--limit N] [--json]` 列出。服务模式的 Postgres 只留接口（`TaskStoreProtocol`）。
- 写库失败只记日志，不影响任务（trajectory.jsonl 仍是权威记录）。

## 10. 验收标准

- [x] AC1：每条合法迁移有测试；非法迁移、从终态迁出抛 `IllegalTransition`；`replay` 能重建状态并拒绝非法历史。
- [x] AC2：SQLite：写入 → 关闭 → 重新打开后能列出任务、状态与事件数。
- [x] AC3：`submit_plan` / `submit_review` 参数非法时返回带字段名的错误；Verifier 改用 `structured_call` 后原有测试与回放夹具全部通过。
- [x] AC4：FakeRouter：Planner 产出字段完整的 Plan；不确定时有 open_questions 并触发计划审批。
- [x] AC5：FakeRouter：Reviewer blocker → 返工 → 第二轮通过；连续 blocker 到上限后停止返工并在证据包标 open；共识模式只有一方 blocker 时不返工。
- [x] AC6：并行只读工具：同一轮 3 个 read 并发执行、结果顺序不变；遇到有副作用工具不越过重排。
- [x] AC7：中断补结果：finish 在一轮中间时，其后的 tool_call 有 `[未执行]` 结果，续写请求合法。
- [x] AC8：端到端（FakeRouter + 真实 none 后端 + 真 pytest）跑通 PLANNING → … → DONE 并产出 Evidence（含 review_variant、vendor_policy）。
- [x] AC9：真实 DeepSeek（deepseek-flash）端到端跑通一个 dev 任务（orchestrated-1m），花费如实记账。
- [x] AC10：Eva 决定 §11 Q1–Q6（2026-10-11 21:35 / 21:36）；Q7 默认开，待审。

## 11. 决定与待决事项

Q1–Q6 由 Eva 于 2026-10-11 21:35 决定（Q1–Q4 维持现状，Q5/Q6 按建议实现）；Q2 于 21:36 改为评测完全放开。

- Q1 计划确认阈值 — **已决定（Eva 21:35，维持现状）**：`min_risk: L2` + needs_approval / open_questions / 构建与敏感路径
  → 需确认；无审批通道时进 NEEDS_HUMAN。仍可配置（`plan_approval.min_risk`）。
- Q2 评测模式的权限 — **已决定（Eva 21:36）**：评测 / 基准跑分时权限默认完全放开——计划全部自动批准（含 L3，
  `plan_approval.eval_reject_from: never`，写 `approval_resolved(by="policy")`），命令不审批（评测工具集不挂权限闸门，
  沙箱内完全访问）。**只适用于评测**（`tw eval` / eval harness），桌面端与终端 `tw run` 不变。仍保留模型白名单
  （只用 deepseek-flash）与非金钱的失控上限（轮数、wall time、token 预算、返工轮数）。想恢复旧策略可设 `eval_reject_from: L3`。
- Q3 评审返工到上限仍有 blocker — **已决定（Eva 21:35，维持现状）**：保留改动、状态 done、证据包标 open + 风险下限 L2。
- Q4 桌面端默认 harness — **已决定（Eva 21:35，维持现状）**：仍是 long-context-1m，等 W4-14 评审消融数据再议。
- Q5 终端 `tw run` 审批通道 — **已决定（Eva 21:35）并实现**：stdin 是 TTY 时 `tw run` 弹 y/N（`cli/tty.py`）：
  命令 / 编辑 `[y] 允许一次 [s] 本次任务都允许 [N] 拒绝`，计划确认 y/N，ask_human 直接输入回答；EOF / Ctrl-D 视为无人。
  非 TTY（管道 / CI）或 `--no-input` 保持原行为（需确认的一律拒绝）。
- Q6 计划确认搁置的续跑点 — **已决定（Eva 21:35）并实现**：停在 AWAIT_PLAN_APPROVAL 时写 `progress.json(stage=await_plan_approval)`
  与 plan.json；`--resume` 走 PREPARING → AWAIT_PLAN_APPROVAL，沿用原计划重新请求确认，不再跑 Planner。
- Q7 人工确认点（W4-10，新增，**默认开，待 Eva 审**）：改依赖声明（pyproject / requirements / package.json / lock 文件，
  或 `uv add` / `pip install` / `npm install <pkg>` 等）与改 CI / 构建配置（.github/workflows、Makefile、Dockerfile、tox.ini …）
  在交互运行里必须由人确认（不交给自动审核模型，`[s]` 可放行本任务剩余同类操作）；非交互一律拒绝并说明原因；评测与 full_access 不经过。
  开关：`orchestration.hitl.dependency_changes / ci_changes`。
- 延后（Eva 21:36）：“模型自动审批”（auto_review）权限模式的实测本轮不做，不花真实调用；单测维持现状。

## 12. 实测记录（2026-10-11 21:09–21:16 北京时间，周日空闲价，只用 deepseek-flash）

演示仓库：`calc.py`（add 写成减法、mean 空列表除零）+ unittest。

| 运行 | harness | 结果 | 花费 |
|---|---|---|---|
| add bug，终端 ask 模式 | orchestrated-1m | done；Planner L1 / 4 条验收标准；Reviewer 通过；但测试命令全被权限拒绝，复现降级，Verifier inconclusive（L2） | ¥0.1640 |
| add bug，`--permission-mode auto_review` | orchestrated-1m | stuck（终端非交互仍拒绝命令，连续 5 次失败） | ¥0.0679 |
| add bug，local 规则放行 python | orchestrated-1m | **done**；复现 reproduced；Verifier pass；Reviewer 通过；19 步 | ¥0.0598 |
| mean([]) bug，终端 | orchestrated-1m-consensus | needs_human：Planner 提了 2 个待确认问题 → 计划审批 → 无审批通道 | ¥0.0087 |
| mean([]) bug，`--jsonl`（脚本按 allow 审批） | orchestrated-1m-consensus | **done**；计划审批（L2 + 3 个问题）→ 批准 → 复现 → 修复 → Verifier pass → 双评审共识通过（L0） | ¥0.0997 |

合计 ¥0.4001（本机账本 2026-W41 从 ¥17.3408 到 ¥17.7409），高峰价调用 0。真实模型下没有出现评审 blocker，返工回路只在 FakeRouter 测试里覆盖。

### 12.1 第二轮（2026-10-11 21:41–21:46 北京时间，周日空闲价，只用 deepseek-flash）：Q5 / Q6 实测

| 运行 | harness | 结果 | 花费 |
|---|---|---|---|
| mean([]) bug，终端非 TTY（stdin=/dev/null） | orchestrated-1m-consensus | needs_human：计划 L1 + 1 个待确认问题 → 无审批通道 → **落续跑点**（plan.json） | ¥0.0065 |
| 同一任务 `--resume <run_id> --jsonl`（脚本批准） | orchestrated-1m-consensus | **done**：PREPARING → AWAIT_PLAN_APPROVAL（沿用原计划，未重跑 Planner）→ 批准 → 复现 → 修复 → 验证 → 双评审 → done | ¥0.053 |
| add bug，伪终端 `tw run`（`yes y \| script` 喂输入） | orchestrated-1m | 计划 y/N 弹出并批准；跑到复现阶段时整条管道被 SIGKILL（测试驱动的问题：`yes` 无限灌 pty，未复现于下一行），作废 | 约 ¥0.01 |
| add bug，伪终端 `tw run`（pty 驱动，只在看到提示时答 y） | orchestrated-1m | **done**：终端弹出“需要你确认 · 计划 L0 · 1 个待确认问题 · [y/N]”→ y → 13 步完成 | ¥0.0303 |

本轮合计 ¥0.1013（账本 ¥17.7409 → ¥17.8422），高峰价调用 0。命令审批在这几次运行里由默认的 auto_review 模式自动批准（`configs/permissions.default.yaml`），
所以终端只弹了计划确认；auto_review 本身的实测按 Eva 21:36 决定延后，本轮没有专门测。

## 变更记录

- 2026-10-11：初稿 + 首版实现（W4-01/03/04/05/06/07/15 部分）；补 §12 实测记录与 Q5/Q6；新增 `configs/harness/orchestrated-1m-consensus.yaml`。
- 2026-10-11（晚）：Eva 21:35 / 21:36 决定 Q1–Q6（Q2 改为评测完全放开）；实现 Q5 终端 y/N、Q6 计划确认续跑点；新增 §8.1 ask_human、§8.2 跨厂商评审、Q7 人工确认点（依赖 / CI 配置）；§12.1 第二轮实测。
