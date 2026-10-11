# Spec 011：检查点、断点续跑、副作用幂等与人在回路（HITL）

- 状态：草稿（W4-02；W4-09 / W4-10 已实现首版，**待 Eva 审阅**，见 §10）｜负责人：Eva｜目标周：W4｜依赖：005、006、010
- 相关文档：04-detailed-design.md §3.6（失败处理 / 检查点设计）、§3.7（HITL 审批点）；spec 010 §8 / §11
- 代码：`harness/replay.py`（事件日志重放、工具预写日志）、`harness/resume.py`（检查点、工作区快照）、
  `orchestrator/inprocess.py`（续跑接线）、`store/idempotency.py`（幂等键）、`permissions/hitl.py`、`tools/human.py`、
  `cli/tty.py`、`harness/approvals.py`

## 1. 背景

v0.3.2 已经有“继续”：每一步把改动文件全文存进 `runs/<id>/resume/`，续跑时写回工作区，再给 Executor 一段续跑说明，
**消息历史从零开始**。问题：

1. 模型忘了自己做过什么（读过哪些文件、试过哪些方案、为什么放弃），续跑常常重读、重试，浪费 token；
2. 进程被杀时如果正在执行有副作用的工具，不知道它有没有生效；
3. 对外副作用（推送分支、开 PR）重试时可能重复。

04 §3.6 的要求：**重放事件日志重建消息历史（不重复执行有副作用的工具），工作区从快照恢复；外部副作用带幂等键，先查后做。**

## 2. 目标与非目标

目标：
1. 检查点：每一步结束都是一个检查点；“历史截到这里”和“工作区恢复到这里”同时成立。
2. 续跑重放：新 run 的 Executor 以重放出来的历史为前缀继续（前缀不变 → DeepSeek 缓存可以命中），只追加一条续跑说明。
3. 不重复执行有副作用的工具：检查点之后的调用不重放、不自动重跑；正在执行时被杀的工具在续跑说明里点名。
4. 对外副作用幂等：`task/run id + 操作名 + 序号` 作键，先查后做，做过的直接返回记录。
5. HITL：把 W4-10 已实现的审批点、通道、审计、评测策略写成规范（spec 010 §8 / §11 只讲了计划确认）。

非目标：
- Temporal（W4-11/12，P2）：本 spec 的检查点 / 幂等设计与它兼容（活动 = 模型调用 / 工具调用），但不实现。
- 规划 / 验证 / 评审阶段中途被杀的“原地续跑”：这三个阶段不落检查点，续跑时重新跑（它们便宜且无副作用）。
- PR / Issue 评论命令通道（`/tw approve`，W5-05）与 Temporal Signal 通道。

## 3. 检查点与续跑

### 3.1 检查点

- **时机**：Executor 每一步（一次模型调用 + 本轮全部工具结果写完）结束时，`AgentLoop` 调 `after_step(steps, touched)`。
- **内容**（`runs/<id>/resume/resume.json`，格式 `tw-resume/1`）：
  - 工作区快照：相对起点的改动文件全文（`files/<n>`，单文件 ≤ 1MB、合计 ≤ 8MB，超了记 `skipped`）；
  - `event_seq`：此刻轨迹的下一个事件序号；`steps`；`repro_check`；NOTES.md（脱敏）；`stage`（work / await_plan_approval）。
- 本步改了工作区（touched）→ 重写快照；没改 → 只把 `event_seq` / `steps` 往后挪（`bump_checkpoint`，不重写文件）。
- 任务结束但没 done（stuck / error / cancelled / needs_human…）时再落一次。全部原子写（临时目录 + rename）。
- **与 04 的差异**：04 写的是“在沙箱里 `git commit` 到影子引用 `refs/tw/ckpt/<step>`”。我们存的是改动文件全文，放在运行目录
  （沙箱外）：docker 容器销毁后仍在、docker / none 后端通用、续跑可以换一个新沙箱。代价是大文件上限（§10 Q2）。

### 3.2 重放（`harness/replay.replay_history`）

输入：被续跑运行的目录、`event_seq`。步骤：

1. 读 `trajectory.jsonl`（最后一行写到一半时丢掉它）；
2. 若检查点之后还有 Executor 的模型调用，它的请求产物（`artifacts/<seq>-request.json`）就是检查点时刻模型看到的完整历史
   （含提醒、清理 / 压缩后的形态）→ 直接用；
3. 否则取检查点之前最后一次 Executor 调用的请求 + 响应 + 这一步的工具消息（`<seq>-tool.json`）；
4. 最后一条 assistant 里没有结果的 tool_call 补 `[未执行：…]`（与 `AgentLoop.seal_dangling` 同规则），保证历史合法；
5. 读工具预写日志（§3.3），列出检查点之后发起过的有副作用工具。

续跑（`InProcessOrchestrator`）：先在干净工作区打 start 快照（diff / 复验基线仍是原始代码），写回快照文件，打 `resumed` 快照；
重放成功 → `AgentLoop.run(restore=历史, continue_with=续跑说明)`；重放失败（旧格式没有 `event_seq`、产物缺失、
`orchestration.replay_on_resume: false`）→ 退回旧方式（新历史 + 续跑说明）。审计：新 run 写 `artifacts/replay.json`
（来源 run、截止序号、重放的模型调用数、检查点之后的副作用列表）。

续跑可以链式进行：新 run 的第一次请求就包含重放的历史，再被续跑时照样能重建。

### 3.3 不重复执行有副作用的工具

- 工具声明 `side_effects`：`none`（只读）/ `workspace`（只改沙箱工作区：write_file、edit_file、bash、run_tests、submit_repro）/
  `external`（对外：ask_human；以后的推送 / 评论）。
- **预写日志** `runs/<id>/tool-journal.jsonl`：非 `none` 的工具执行前写 `{phase: start, call_id, tool, side_effects, seq,
  summary(脱敏)}`，执行后写 `{phase: end, call_id, ok}`。
- 规则：
  - 检查点之前的调用：结果已在历史里，**不重放执行**；
  - 检查点之后的调用：不进历史、不自动重跑。`workspace` 类的效果随快照回滚（工作区回到检查点），续跑说明列出它们
    “效果已回滚，没有自动重跑”；`external` 类无法回滚，续跑说明点名“已经发起过（可能已生效），先确认再决定”；
  - start 没有对应 end = 执行中被杀，续跑说明标“执行中被打断”。
- 沙箱外的副作用（例如 bash 写了工作区以外的文件）不在回滚范围内：docker 后端每次续跑是新容器，工作区以外的状态本来就不保留；
  none 后端（本机 worktree）可能残留，属于已知限制，由 none 后端“仅开发调试”的定位兜底。

## 4. 对外副作用的幂等键（`store/idempotency.py`）

- 键：`<task 或 run id>:<操作名>:<序号>`（04 §3.6）；表 `side_effects(key, op, status, attempts, result, error, …)` 在 `TW_HOME/tw.db`。
- `SideEffectLog.run(key, do, find)`：done → 返回记录不执行；started / failed → 先 `find()` 查外部，查到补记 done；
  查不到才执行；执行前记 started、成功记 done、失败记 failed（错误摘要脱敏）。结果只存 URL / 编号，不存令牌。
- 已接入：`tw pr open`（键 `<run_id>:open_pr:0`；`open_pr` 自身还会先查 GitHub 上同分支的 open PR）。第二次调用返回
  `reused: true` 和第一次的 URL，不再推送、不再开。
- W5 接入：PR 评论、Issue 回帖、CI 回流（GitHub App 由 Eva 决定，W5）。

## 5. HITL 审批点（04 §3.7；W4-10 实现）

| 审批点 | 默认 | 触发 | 交互通道 | 非交互（无通道） | 评测 |
|---|---|---|---|---|---|
| 计划确认 | 需要 | 风险 ≥ L2、`needs_approval`、有 open_questions、动构建 / 敏感文件（spec 010 §8） | 审批卡 tool=Plan / 终端 y/N | NEEDS_HUMAN，落续跑点（Q6） | 全部自动批准（含 L3） |
| 改依赖声明 | 必须人确认 | pyproject / requirements / package.json / lock 等，或 `uv add` / `pip install` / `npm install <pkg>` | 审批卡 / 终端 y/N（`[s]` 放行本任务同类） | 拒绝并说明原因 | 不经过 |
| 改 CI / 构建配置 | 必须人确认 | .github/workflows、Makefile、Dockerfile、tox.ini、noxfile.py … | 同上 | 拒绝 | 不经过 |
| 普通命令 / 编辑 | 按权限模式（spec 006） | 规则未命中 | 审批卡 / 终端 / auto_review | 拒绝 | 不经过（完全放开） |
| ask_human | 阻塞或非阻塞 | Executor 主动提问 | 审批卡 tool=AskHuman（附言 = 回答）/ 终端输入 | 阻塞 → NEEDS_HUMAN 可续跑；非阻塞 → 按假设继续 | 不问人，按最佳判断 |
| 开 PR / 推送 | 必须点确认 | 结论卡「开 PR」 | 审批卡 → `tw pr open --yes` | — | 不开 PR |
| 超预算继续 | 不适用 | Eva 2026-10-11 去掉了金额上限；只剩非金钱上限（轮数 / token / 墙钟），到了就停 | — | — | — |
| 新出网域名 | 默认拒绝 | 沙箱默认断网 | W7 安全网关 | — | — |

- 审计：所有审批写 `approval_requested` / `approval_resolved(by=user|policy|reviewer|rule)` 事件，进 trajectory 与 tw.db。
- “人必须确认”的点（依赖 / CI / 计划）**不交给 auto_review 审核模型**；auto_review 只处理普通命令（默认模式，是否改默认由 Eva 决定）。
- 开关：`orchestration.hitl.dependency_changes / ci_changes`；`orchestration.plan_approval.*`；`tw run --no-input` 关闭终端提问。

## 6. 评测模式

- 禁止人工介入，保证可复现：AWAIT_* 按策略自动处理并写 `approval_resolved(by="policy")`；ask_human 不发出。
- Eva 2026-10-11 21:36：评测 / 基准跑分时权限完全放开（计划全部自动批准含 L3，命令不审批），只限评测；
  保留模型白名单（只用 deepseek-flash）与非金钱失控上限。
- 评测不续跑（任务失败就记失败），也不存续跑快照；工具预写日志照常写进运行目录（便于事后分析），开销可忽略。

## 7. 接口

```python
# harness/replay.py
replay_history(run_dir: Path, *, upto_seq: int | None, role="executor") -> Replay | None
replay_note(rp, *, from_run, applied, held, skipped, repro) -> str
journal_write(run_dir, entry) / read_journal(run_dir)
# harness/resume.py
save_progress(..., event_seq: int | None) ; bump_checkpoint(run_dir, *, event_seq, steps) ; ResumeState.event_seq / from_dir
# harness/loop.py
AgentLoop.run(prompt, ctx, *, continue_with=None, restore: list[Message] | None = None)
# store/idempotency.py
side_effect_key(owner, op, n=0) ; SideEffectLog(path).run(key, do, find=None) -> Outcome(result, reused, how)
```

## 8. 验收标准

- [x] AC1：子进程跑真实编排器（FakeRouter + none 后端），第 4 次模型调用前 SIGKILL；续跑后任务 done，第一次请求里有重放的
  3 步历史（4 条工具结果）+ 续跑说明，直接 finish，工作区外的副作用计数不变（`tests/unit/orchestrator/test_crash_resume.py`）。
- [x] AC2：有副作用的 bash 执行中被 SIGKILL：预写日志有 start 无 end；续跑不重放那一步、不重跑，续跑说明点名“执行中被打断”。
- [x] AC3：`replay_on_resume: false` 退回旧方式（新历史 + `<resume>` 说明）。
- [x] AC4：幂等键：done 不重复（跨进程）、started 先查后做、失败记录脱敏并可重试；`tw pr open --yes` 连续两次只开一次。
- [x] AC5：HITL 各审批点有测试（`tests/unit/permissions/test_hitl.py`、`tests/unit/cli/test_tty_approver.py`、
  `tests/unit/orchestrator/test_inprocess.py` 的计划确认 / ask_human / 评测策略）。
- [x] AC6：真实 deepseek-flash：`tw run` 中途 kill -9 → `--resume` → done，记账（§9）。
- [ ] AC7：Eva 审阅本 spec，决定 §10。

## 9. 实测记录

2026-10-11 22:2x 北京时间（周日空闲价），只用 deepseek-flash，演示仓库 `calc.py`（mean([]) 除零）：

| 运行 | 结果 | 花费 |
|---|---|---|
| `tw run --jsonl`（long-context-1m，repro-first），Executor 第 4 个工具结果后对整个进程组 `kill -9` | 状态 interrupted；`resume.json` 检查点 event_seq=14、steps=1；预写日志只有已完成的 `bash pwd` | ≈¥0.001 |
| `tw run --jsonl --resume <run_id>` | **done**：重放 1 步历史（system + 任务 + 1 轮 2 个工具结果）+ 续跑说明；第一次请求缓存命中 3328 / 3494 token；复现 → 修复 → 验证 pass | ¥0.017 |

合计 ¥0.0178（账本 ¥17.8422 → ¥17.8600），高峰调用 0。实测发现并修复：对话轮的模型调用（role=executor，在 task_started 之前）
曾被算进重放步数——重放现在只看最后一次 task_started 之后的事件（有单测）；预写日志的 summary 被二次 JSON 编码（已修）。

## 10. 待决事项（默认值可配置）

- Q1 续跑默认重放历史（`replay_on_resume: true`）。好处：模型记得做过什么、前缀缓存命中；风险：如果上次已经陷入错误思路，
  重放会把它带回来。备选：连续续跑 ≥2 次时改用旧方式（干净历史）。当前不做，等真实数据。
- Q2 工作区快照存文件全文（单文件 1MB / 合计 8MB 上限）而不是沙箱里的影子 git 引用（§3.1）。大改动（生成文件、lock 文件）
  会进 `skipped`，续跑时让模型重做。是否需要加影子引用作为补充，待定。
- Q3 规划 / 验证 / 评审阶段被杀时整段重跑（便宜、无副作用）；不单独落检查点。
- Q4 幂等记录 done 之后，用户在 GitHub 上关掉 PR 再点「开 PR」会拿到旧链接（不会重开）。是否加“强制重开”选项，待定。

## 11. 变更记录

- 2026-10-11：初稿（W4-02），同时实现 W4-09（重放 + 预写日志 + 幂等键）；HITL 部分整理自 W4-10 已实现的行为。
