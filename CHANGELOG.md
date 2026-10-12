# 更新记录

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。桌面端版本号用 SemVer（`0.5.0-preview`），核心 Python 包用 PEP 440（`0.5.0a1`）。
发布流程（`.github/workflows/release.yml`）会把下面对应版本的整节内容作为 GitHub Release 说明。

## [Unreleased]

### Known issues（第 2 批）
- 演示回放会话里的步骤标题不跟「长时阅读字号」变化（该设置只作用于对话正文与用户气泡）。

## [0.5.1-preview] - 2026-10-13

UI 批次 1：电子书 / Typora 式浅色简约界面（Eva 定向「选浅色简约风格，参考 typora 等 markdown 编辑器」，蓝色大肥鱼主导，真用户阿验两轮走查）。计划见 `apps/desktop/docs/ebook-ui-plan.md`。

正式安装包 = GitHub Release（草稿）附件 `TriWitness_0.5.1-preview_x64-setup.exe`，sha256 `dda66b861e13ed9ae847a12418144d7fb4c67fc9eef812baba4aa96ce8cab642`（标签 v0.5.1-preview 的 release 工作流构建）。

### Changed
- **浅色主主题**：底 `#f7f5f2`、正文 `#3a3632`（11:1）；删除纸纹（不留开关）；正文 16px / 1.7 行高；Markdown 标题 / 引用 / 表格 / 代码贴近 Typora 的克制样式。夜间为次要主题，卡片正文 `#c4b59c`（7.41:1）。
- **代码块降饱和语法高亮**（highlight.js core 本地打包、懒加载，11 种语言）：日夜两套色板，各 token 对代码底 ≥4.73:1；未知语言按纯文本。
- 默认减少动效：日志即时出字、不重放；完整焦点环（工具行 / 输入框）；结论出现前状态不显示完成；夜间错误红调柔。
- 右栏分节标签 14px、夜间用正文浅色；增删统计、`→ N failed` 结果、`$ write_file` 路径不拆行（长路径中间省略，悬停看全路径）。
- 侧栏：长标题中间省略；同名会话加稳定序号 ·1/·2/·3（按会话第一轮时间，后续活动不重排），悬停显示完整标题与 id。

### Fixed
- 流式输出：未闭合的反引号 / 粗体 / 代码围栏不再露出原始 Markdown（显示时临时补齐）；光标贴在最后一段末尾，不单独占行。
- 切换会话不再从头重播日志：按会话缓存事件与右栏滚动位置，切回已完成会话停在原处。

### Added
- 开发版 UI 走查样例页 `?gallery=1`（与 `?source=fixture:*` 配合）；发版前包检查保证样例页不进 release。

### Known issues（P2，放第 2 批）
- 「(+18 −4)」整体换到下一行（不再拆开，但不和路径同行）。
- 标准动效下，最后两行逐字书写时仍可能断开 token。
- 流式结束后段距有一次轻微跳动。
- 演示回放较慢（>25s）。
- 右栏「复验未通过：test_concurrent_refresh 仍失败」末字孤行。
- 夜间设置页导航 / 分段控件对比度偏低。
- 「安全上限」状态比最终结论行略早出现。
- 夜间 keyword 色与正文接近。
- 夜间 API Key 弹窗与遮罩几乎同色，禁用按钮难辨。
- 结论卡阴影偏重；夜间「风险」「干净环境」标签偏淡。
- 样例页分区标题偏暗。
- 设置页小字（计划第 2 批长读模式一并处理）。

## [0.5.0-preview] - 未发布

### Changed
- **GitHub App 永久不做**（Eva 2026-10-12）：取消 W7-08 / W5-02（及依赖 Webhook 的 W5-03）。v1 只走本地分支 `tw/<run_id>` + `pr.md` / 可选 `tw pr open`（gh·PAT）。见 `specs/012-github-integration.md` §8、`docs/release/known-limitations.md`。

### Fixed
- **所选文件夹不是 git 仓库时自动初始化**（Eva 2026-10-13）：开始仓库工作前若文件夹不是仓库、也不在任何仓库里，自动 `git init` → 缺 user.name / user.email 时只写本仓库兜底身份 `TriWitness <triwitness@local>` → `git add -A`（遵守已有 .gitignore）→ 提交 `TriWitness: initial snapshot`（空文件夹用 `--allow-empty`）；已是仓库或在仓库里的绝不改动。桌面端运行时间线显示“已自动初始化 git 仓库”。`harness/repo_init.py`。
- **docker 沙箱准备卡住**（run 停在 `start_repo_work` 之后、没有 `task_started`）：`git archive` 改走 `run_capture`（输出写临时文件、stdin 为空、超时杀进程树，同 v0.3 local.py 的 Windows git 启动器修复）并放进 `asyncio.to_thread`；拉镜像放线程里、默认上限 600s（`TW_DOCKER_PULL_TIMEOUT` 可改）；auto 模式下 docker 准备失败 / 超时（总上限 900s）回退 none 后端并发可见警告，显式 `--backend docker` 仍直接报错。
- **核心日志落盘**：`$TW_HOME/logs/core.log`（2 MB × 5 份轮转，`core.N.log`），logging 与 stderr 同写一份，写前脱敏；`tw diag export` 原本就收 `logs/`。`TW_LOG_DIR` 改目录、`TW_NO_LOG_FILE=1` 关闭。

### Added
- **tw-events/1 新事件 `sandbox_progress`**（只增不改）：`stage`（git_init / archive / pull_image / container / fallback）、`status`（running / done / failed / warn）、`message`、`backend`；桌面端在书写推流和对话流里显示（同阶段 running→done 原地替换，failed 赭红、warn 警示）。
- **W8-01 终测一键脚本**：`scripts/windows/run-final-eval.ps1`（test 35 题 × 单 Executor 基线 / orchestrated-1m 各 1 次，flash 非思考，冻结配置 `configs/runs/final-*.yaml`；续跑、磁盘检查、超 24MB 自动拆分 zip）+ `scripts/final_eval.py plan|run|report|bundle|reproduce`。
- **W8-01 终测结果** 入库 `evals/baselines/2026-10-12-final-w8/`；**W8-02 静态 Leaderboard** `site/`（`scripts/build_leaderboard.py` 生成 data.json，GitHub Pages 工作流 `pages.yml`）；面试材料与 README 回填终测数字。
- **W8-05 `tw eval reproduce <run>`**：按旧 run.json 的任务 / 配置 / 模型 ID 重跑（默认回放 ¥0，`--live` 真调），逐题对比写 `reproduce.md`，提示服务端模型可能已更新。
- **W8-03 轨迹导出**（`tw traj export`）：OpenAI messages（SFT）、轨迹+奖励（RLVR）、Harbor 结果目录、单文件 HTML 回放；样例在 `evals/fixtures/traj_export/`。
- **W5-13 外部对照第三轮（box，10 题 × 3，2026-10-12 13:32–14:31 UTC+8，Eva 批 `--allow-peak`，账本 ¥3.0144）**：`evals/baselines/2026-10-12-harbor-tb2-r3/`。30/30 完成、0 异常，**解决 28/30 = 93.3%**（Wilson 79%–98%）。超时守卫默认 `timeout_guard=block`：overfull-hbox 1/3→3/3，cobol / polyglot 均 3/3。fix-git 1/3 是判分环境 apt 镜像 500/404（Agent 已给出合理 merge，不是回归）。缓存命中 98.1%；比 r2 贵主要因高峰价（496/890）与 polyglot 三次偏贵。
- **W7 安全网关首版（spec 014 / 015）**：Docker `network=allowlist` = internal 网络 + 出网网关 sidecar（域名白名单、SSRF / 元数据 / IP 直连 / DNS 外泄拦截；凭证按域名+方法+路径注入，沙箱只有 `tw-placeholder-*`；审计不记密钥）。MCP 代理（2026-07-28 无状态核心：白名单、版本固定、工具元数据指纹、第 N 次变脸隔离、返回包 untrusted）。参数级策略引擎 fail closed（分类器 uncertain→deny）。回收区 / git 只推 `tw/*` / 外部破坏性操作延迟可撤销。跨 agent 委托注入扫描 + HITL 审批令牌。红队 39 用例确定性开/关对比 39/39（¥0）。
- **W6 spec 013 §10**：六个开放问题落成可逆默认值后，**Eva 于 2026-10-12 全部确认**（人工审核 repo 级 Skill；事实仅 `accept`；`tw run` 默认读记忆；门禁点估计 + underpowered；每周门禁约 ¥4；回滚 −15pp；导出仅三目录且不写用户仓库）。桌面端“本次用了哪些记忆”记为 UI TODO（`apps/desktop/STATUS.md`）。

## [0.3.2-preview] - 未发布

### 变更（不兼容）
- **去掉预算控制**（Eva 2026-10-11 19:14）：不再有 ¥100 总额 / 类别信封拦截、STOP / `TW_KILL_SWITCH` 熔断、单任务 ¥ 上限、高峰闸门（调用级和评测级都不拒绝，高峰只标注）、`tw eval` 按预估金额拒绝启动；桌面端去掉单任务上限滑块、总预算、“高峰时段也允许真实调用”开关和 `peak_blocked` 提示。`--max-cost` / `--allow-peak` / `--max-total-cny` 隐藏且无效（旧脚本不报错）。
- **保留**：本机账本改作用量日志（`tw usage [--json|--md]`，按类别 / 周 / 模型；`tw budget` 为隐藏别名），设置里的“预算”页改为只读的“用量”页，状态栏显示累计已花；每条消息 / 每个任务的实付、缓存命中、高峰价调用数照常显示；防失控的非金钱安全上限（100 轮、墙钟、输入 / 未命中输入 / 输出 token）不变，收尾提醒按这些上限的 80%；模型白名单（永不用 v4-pro）不变。
- 迁移：桌面端偏好里的 `maxCost` / `allowPeak` 自动丢弃；旧链接 `section=budget` 跳到“用量”；`CostReport.budget_cny` 改为可选，旧轨迹照常显示。详见 ADR-0002 修订 2026-10-11。

### 变更
- **核心架构面向 1M 上下文**（Eva 2026-10-11 20:26）：默认 harness 改为 `long-context-1m.yaml`（继承 repro-first），Executor 工作预算按模型窗口推导 ≈ 950K（窗口 1,048,576 − 输出预留 64K − 3%）；清理线 50% → 清到 25%，压缩线 75%，保留最近 16 条工具结果，原样尾部 ≤ 120K，摘要输入 120K / 输出 10K。`configs/models.yaml` 新增模型窗口 / 最大输出与每个角色显式的 `max_tokens`。`baseline.yaml` / `repro-first.yaml` 冻结（W2 的 harness_hash 不变）。
- **防失控上限随窗口放大**：单任务累计输入 ≈ 60M、未命中 ≈ 2.85M（原 6M / 400K），由工作预算推导，仍不含金额。
- **长上下文实测**：`scripts/probe_long_context.py` 只用 deepseek-flash，测针召回和首字延迟。2026-10-11 的结果放在 `evals/baselines/2026-10-11-long-context-probe/`：约 900K 时召回全对，冷请求首字约 19 s，热请求约 5 s。本机账本新增类别 `long_context_probe`。

### 新增
- **W4 多角色编排（spec 010，初稿待 Eva 审）**：`tw run --harness orchestrated-1m` 走 Planner → （计划确认）→ 复现 → Executor → 验证 → Reviewer → 整理结果；全部 deepseek-flash（永不 v4-pro）。默认 harness 仍是 long-context-1m（角色关闭，行为与之前一致）。
  - 显式状态机 `core/state_machine.py`（04 §3.1 迁移表，非法迁移抛 `IllegalTransition`，可从事件重放）；编排器 `orchestrator/inprocess.py`，`harness/run.py` 只剩兼容入口。
  - 角色契约 `roles/contracts.py`：`submit_plan` / `submit_review` 终止工具 + 结构化输出降级助手（auto → 修复 ×2 → 正文抽 JSON），Verifier 也改用它（回放夹具不变）。
  - Planner（只读工具、可执行验收标准、open_questions）与 Reviewer（只报有依据的问题，文件 / 行号 / 严重级别 / 建议）；同厂商异构变体 adversarial（思考 max）/ checklist（思考 high + 清单式提示），证据包标注 `review_variant` 与 `vendor_policy=single_vendor`。
  - 评审 blocker → 在同一个 Executor 上下文里返工（有上限，默认 2 轮）；到上限仍有 blocker 时保留改动、发现标 open、风险至少 L2。可选共识模式（`orchestrated-1m-consensus`）：两个变体都报 blocker 才返工。
  - 计划确认：风险 ≥ L2、Planner 要求确认、有待确认问题或动构建 / 敏感文件时等待确认（桌面端走审批卡，终端无审批通道 → needs_human；评测当时为自动批准 L0–L2、拒绝 L3），阈值可配置（spec 010 §11 Q1，待 Eva 定）。
  - 任务库：任务与事件写 `TW_HOME/tw.db`（SQLite），`tw tasks [--json]` 列出（W4-15）。
  - **Eva 决定（2026-10-11 21:35 / 21:36，spec 010 §11）**：Q1–Q4 维持现状；评测 / 基准跑分时权限完全放开（计划全部自动批准含 L3、命令不审批，只限评测；仍保留模型白名单与非金钱上限）；“模型自动审批”权限模式的实测延后。
  - **终端 `tw run` 交互审批（Q5）**：stdin 是 TTY 时弹 y/N——命令 / 编辑 `[y] 允许一次 [s] 本次任务都允许 [N] 拒绝`、计划确认 y/N、ask_human 直接输入回答；管道 / CI 或 `--no-input` 保持“需要确认的一律拒绝”。
  - **计划确认续跑点（Q6）**：停在计划确认时保存续跑点，`--resume` 沿用原计划重新请求确认，不再重跑 Planner。
  - **人工确认点（W4-10，默认开，待 Eva 审）**：改依赖声明（pyproject / requirements / package.json / lock，或 `uv add` / `pip install` 等）与改 CI / 构建配置（.github/workflows、Makefile、Dockerfile …）在交互运行里必须由人确认，不交给自动审核模型；非交互拒绝；评测不经过。开关 `orchestration.hitl`。
  - **ask_human 工具**：Executor 可以问人（阻塞 / 非阻塞）；没有审批通道时任务停在 needs_human 并可续跑；评测里不问人、按最佳判断继续。orchestrated-1m 默认启用。
- **W4-09 事件日志重放续跑 + 幂等键（b482cdd）**：每个 Executor 步骤结束都是检查点（resume.json 记 `event_seq`）；`--resume` 从轨迹重放到检查点的模型上下文（命中前缀缓存），检查点之后的调用不重放、不重跑，执行中被打断的工具调用补成“未执行”；有副作用的工具先写 `runs/<id>/tool-journal.jsonl` 预写日志，续跑说明里列出“已回滚的工作区操作”和“已经发起过、需先确认的对外操作”。对外副作用用幂等键（`<run_id>:open_pr:0`，`TW_HOME/tw.db` 表 `side_effects`）：`tw pr open` 重复执行返回同一个 PR（`reused`）。开关 `orchestration.replay_on_resume`（默认开）。进程 SIGKILL 崩溃续跑有子进程测试。
- **spec 011 检查点与人工确认（W4-02，初稿待 Eva 审）**：`specs/011-checkpoints-and-hitl.md`，AC1–AC6 已验收，AC7 待 Eva；§10 列 Q1–Q4 待定问题。
- **W4-13 评审者注入缺陷集**：`evals/reviewer/`，20 个任务的金标准补丁 × {原样, 注入一个缺陷} = 40 题（11 类缺陷，blocker / major），标准答案含文件 / 行号 / 类别；`scripts/build_reviewer_defects.py gold|build|check` 重建与校验（40 题全部能 apply 到基线）。
- **W4-14 评审者消融**：`scripts/reviewer_ablation.py prepare|run|score|bundle`，臂 = none / same（新提示 `reviewer-plain`，思考 high）/ adversarial（思考 max）/ checklist 非思考 t=0.3 / t=1.0，事后算共识；检出率 / 误报率带 Wilson 95% 区间、按类别拆分。Windows 一键脚本 `scripts/windows/run-reviewer-ablation.ps1`（克隆 / 更新 → `evals/reviewer/Dockerfile` 构建 → 容器内并发 4 → 结果 + 账本打成一个 zip；密钥只从本机环境变量透传）。只用 deepseek-flash，账本类别 `reviewer-ablation`。
- **W4-14 评审者消融全量结果（Eva 本机，2026-10-11 23:52–00:26 UTC+8，空闲价，账本 ¥8.715）**：`evals/baselines/2026-10-12-reviewer-ablation/`，40 题 × 4 臂 × 1 次 = 160 次全部完成。位置检出 / 干净误报：same 85% / 15%，adversarial 85% / 25%，checklist_t03 75% / 35%，checklist_t10 90% / 25%，共识（事后）70–75% / 20%；对 adversarial 的配对比较全部无显著差异（n=20，可检出差距约 28 个百分点）。14% 的评审用完 20 轮没下结论（大仓库题为主，编排器里等于放行）。建议默认评审改 checklist_t10（质量不差、花费与耗时约 1/3），共识保持关闭；默认配置未改，待 Eva 定。新增 `scripts/reviewer_ablation_posthoc.py`（没下结论敏感性、按类别 Wilson、账本口径成本与耗时）。
- **默认评审改为 checklist + “没结论 ≠ 通过”（Eva 2026-10-12 01:01，ADR-0007，spec 010 §6.2 / §6.2.1 / Q8）**：
  - `orchestration.reviewer.variant`（默认 `checklist`：清单式提示、deepseek-flash 非思考、temperature 1.0）；共识模式仍默认关，其第二评审同样改为非思考 t=1.0。`LLMRequest.thinking_override` 让角色变体覆盖路由的思考开关。
  - `reviewer.force_submit`（默认开）：最后一次允许的调用追加提醒并强制 `tool_choice=submit_review`，这一次关思考（DeepSeek 思考模式不接受强制 tool_choice；适配器兜底降为 auto）。box 实测 1 次 ¥0.0015 通过。
  - 仍无结论：证据包 `review_status=inconclusive` + `floor:reviewer_inconclusive`（风险下限 L2）；交互发审批卡 `ReviewInconclusive`（同意 → done，拒绝 → failed，无通道 → needs_human）；评测记为未解决（`TaskResult.review_inconclusive`，LLMAgent 不算声称成功）。
  - **修复上限那次调用丢失**：调用后记账触发安全上限时，`BudgetExceeded.response` 带回这次已付费回复，照常写 model_call，回复里的终止工具（finish / submit_*）照常执行。修掉 W4-14 结果比账本少 ¥0.14 的缺口（22 次没结论运行各少记 1 次调用）。
  - W4-14 第二轮准备：`run-reviewer-ablation.ps1 -Arms adversarial,checklist_t10 -Repeats 3`（补 r1 / r2，约 ¥10，已有 r0 跳过；找不到 r0 拒绝运行除非 `-Force`）；消融关 `force_submit` 保持协议一致；结果 JSON 加 `task_id`、`verdict_on_last_call`；结果包默认只带没结论 / 出错的轨迹；`reviewer_ablation_posthoc.py` 加逐次稳定性、按题聚类 bootstrap 与第一轮口径复算。
- **W4-14b 评审者消融第二轮（Eva 本机，2026-10-12 01:32–02:16 UTC+8，空闲价，账本 ¥10.2728，代码 `2220244`）**：adversarial 与 checklist_t10 在同样 40 题上补 r1、r2，160 次全部完成、0 出错，结果与账本逐条对上（记账缺口已修好）；与第一轮合并为每臂 120 次，入库 `evals/baselines/2026-10-12-reviewer-ablation/`。checklist_t10 − adversarial：检出 +0%（按题聚类 95% −18%～+18%）、干净放行 −2%（−5%～+0%）、没下结论 −13%（−23%～−5%，20% → 7%）；按题多数 McNemar 三个指标 Holm p 全部 1.000；¥/次 0.030 对 0.097、耗时中位 27s 对 95s。**ADR-0007 确认**，默认值不变；逐题互有长短（adversarial 在 wrong_regex 上 5/6 对 1/6）。`reviewer_ablation_posthoc.py` 加没下结论率、按题多数 / 逐次合并 McNemar + Holm、逐题对比。
- **W5 GitHub 集成（spec 012 草稿，GitHub App 暂缓，只走 gh / PAT）**：状态机接上 `PACKAGING →（AWAIT_PR_APPROVAL）→ PR_OPENED → CI_WATCH ⇄ EXECUTING → DONE`。
  - `tw run --open-pr [--pr-base] [--pr-remote] [--watch-ci/--no-watch-ci]`：任务完成后按风险等级决定开不开 PR（`github.pr_policy`，默认 L0 / L1 确认后开、L2 确认后开 Draft PR、L3 不开；没有验证结论按 L2）；终端 TTY 问 `推送分支并开这个 PR？[y/N]`，非交互不开，可稍后 `tw pr open`。评测模式永远不发布。
  - CI 回流（`github/ci.py`）：轮询 PR 头提交的 check runs（`gh api` 或令牌 REST），失败时取失败日志（`gh run view --log-failed`）、精简到 6000 字、包成不可信数据交给同一个 Executor 返工，提交并推送后再等 CI，最多 2 轮（`github.ci.max_fix_rounds`）；没配 CI 的仓库宽限 2 分钟后视为无 CI。
  - 推送 / 开 PR 带幂等键（`<run_id>:open_pr:0`、`<run_id>:push:<n>`），产物 `pr.json`、`ci-<n>.json`，`summary.json` 增加 `pr` / `ci`。评论命令 `/tw approve|reject`、Webhook、Issue 标签触发等 App 决定后再做。
- **W5-08 消融统计库 `eval/ablation.py`**：OFAT 配置生成（与基线相同的水平自动跳过）、McNemar 精确检验、Holm 校正、bootstrap / 配对 bootstrap 区间、Wilson 区间、可检出差异（MDE）、对比表；只有 Holm p < 0.05 且区间不含 0 才写“更好 / 更差”。评审者消融的 `score` 增加与 adversarial 的配对比较。
- **W5-09/10/11 第一轮 OFAT 消融（脚本已备好，待 Eva 本机跑）**：`evals/ablations/w5-round1.yaml`（dev 15 题；基线 = flash 非思考；因素：上下文 3 档、工具 2 档、思考 low / high、repro-first、Planner）+ `scripts/ofat_ablation.py plan|run|report|bundle` + 新配置 `configs/harness/planner-only.yaml`。Windows 一键脚本 `scripts/windows/run-ofat-ablation.ps1`（`evals/runner/Dockerfile` 镜像，挂载宿主 docker.sock 起任务沙箱，并发 3）；预估 1 次 ≈ ¥11、3 次 ≈ ¥33。账本类别 `ofat-ablation`；box 上只做了 1 题冒烟（¥0.0083）。
- **W5 评测防作弊加固（landscape §4.2）**：`eval/task_hardening.py`；任务工厂新建任务默认匿名 ID（`t-<10 位哈希>`，原实例 ID 只留在 task.toml 元数据）、清洗 Issue 正文里的提交 / PR / 对比链接和 40 位 SHA、镜像禁用 git hooks（源码本来就来自无 `.git` 的归档包，比单提交仓库更严）；评测沙箱 `GIT_ALLOW_PROTOCOL=file`，开网时把 GitHub / GitLab / Gitee / HF 等代码托管域名解析到 0.0.0.0。`task_factory.py audit` 只读审计：现有 109 个任务 0 error（warn：未匿名 109、未禁用 hooks 104、Issue 含链接 18；不改已有任务和隐藏测试）。
- **密钥清洗 + 仓库级密钥扫描（2026-10-12，GitHub secret scanning 告警 #1）**：ext 任务 `t-d465a62f2f`（dstl/Stone-Soup 上游公开 Issue）正文里有一条 CircleCI 产物的 S3 预签名链接，带第三方临时 AWS 访问密钥 ID（`ASIA…`），随 36c894a 入库。
  - `task_hardening.redact_secrets()`（`sanitize_instruction()` 先调用它）：预签名链接（`X-Amz-*` / `X-Goog-*` / Azure SAS `sig=` / CloudFront `Signature` / `token=` 等）保留主机和路径、查询串换成 `?[已移除签名链接]`；AWS 访问密钥 ID、GitHub `ghp_` / `github_pat_`、Slack `xox*`、`sk-` 风格密钥、Google API key、带正文的私钥块换成 `[已移除密钥]`；只记种类不记原文。`audit_task` 新增 error `instruction_secret`。
  - 重新清洗 ext / ext-reserve 全部 109 个任务的 Issue 正文：只有 `t-d465a62f2f` 命中（1 条签名链接），只改 instruction.md，镜像不受影响（镜像标签只哈希 environment/）；`evals/suites/ext.yaml` digest 随之更新（59c5885d06be9a49 → c56b07a7feb1fbc7），ext-reserve 不变。dev / test 的 Issue 正文 0 命中，未改。
  - 新增 `scripts/secret_scan.py` + `scripts/secret_scan_allow.txt`（白名单只放测试夹具里的假密钥，不允许覆盖 evals/）：扫 `git ls-files` 全部文本文件，CI python 作业在 ruff 前先跑；单测 `test_repo_is_clean` 也会兜住。没有改写 git 历史。
- **W5 第二批（Eva 未答复 3 个问题，按可撤回的默认做，23:21）**：
  - L0 开 PR 仍需确认（不变）。
  - **CI 修复返工后先重跑验证器（不重跑评审者）再推送**：发布流程 `CI_WATCH → EXECUTING → VERIFYING → PACKAGING → 推送`；验证不通过就不推送，任务以“CI 修复未通过验证，未推送”结束（spec 012 §5）。
  - 不新建任何 GitHub 仓库；真实仓库上的 CI 修复验收等 Eva 提供 / 批准仓库后再做。
- **W5-12 扩充任务集 ext（完成）**：`task_factory.py mine --exclude-existing --fetch-filtered N` 跳过所有已尝试过的实例，从 SWE-rebench 2025-01…2026-03 与 filtered 子集挖出 185 个新候选（每仓库总数 ≤ 2）；全部加固构建（匿名 ID、hooks 关闭、删 `.git`），**109 个通过** null 0 / oracle 1 ×3 校验。`split-ext --size 50`：最新 50 个冻结为 `evals/suites/ext.yaml`（dev 15 + test 35 + ext 50 = 100），其余 59 个冻结为 `ext-reserve.yaml`；dev / test 不动、无重叠、审计 0 发现。新增磁盘占用率守卫（≥ 65% 不开新构建）。失败原因见 spec 016 §5.4。
- **W5-13 Harbor 集成**：我们的任务目录与 Harbor 格式兼容（oracle 1 / nop 0）；新增 `triwitness.integrations.harbor_agent:TriWitnessAgent` + `HarborSandbox`，`harbor run -a ...` 让 TriWitness（deepseek-flash）解 Harbor 任务，box 实测 1 题解决、¥0.0126。Terminal-Bench 2.0 的 10 题子集脚本 `scripts/harbor_external.py` + Windows 一键 `scripts/windows/run-harbor-tb2.ps1`（WSL2）待 Eva 本机跑（box 的 Docker 自定义网络无 DNS，TB2 verifier 联网失败）。见 `docs/design/harbor-integration.md`。
- **W5-13 外部对照结果（Eva 本机 WSL2，2026-10-12 03:10–03:26 UTC+8，空闲价，账本 ¥0.6893）**：`evals/baselines/2026-10-12-harbor-tb2/`。Terminal-Bench 2.0 10 题子集 × TriWitness（baseline harness，flash 非思考）各 1 次：10/10 完成、0 异常，**解决 9/10**（Wilson 95% 60%–98%），每题中位 ¥0.045、缓存命中 97.5%、0 次上下文压缩。唯一失败 polyglot-c-py 是我们的复现测试 `tests/tw_repro/` 残留在产物目录（verifier 要求目录里只有 main.py.c），不是能力问题。子集是挑过的、n=10，只作外部参照，不和公开榜单或 dev / test 比较。顺带发现：轨迹里 `thinking` 记的是请求默认值（非思考运行也记 true）；artifact 脱敏偶尔会弄坏 JSON 引号。
- **W5-13 第一轮的三处修复 + 重复运行**：①外部（Harbor）任务默认把复现测试指到 `/tmp/tw_repro/`（提示里写明），结束时再清掉运行期间新出现在任务目录里的 `tw_repro/`、`.pytest_cache/`、`__pycache__/` 和由此变空的新 `tests/`（运行前已有的不动）；agent kwargs `repro_dir=none` / `repro_cleanup=false` 可关，元数据记录删了什么。仓库模式（SWE）不变，复现测试仍是证据。②轨迹的 `thinking` 记实际发出去的值（客户端从请求载荷读回，`effective_thinking`），不再记请求默认值。③脱敏的值匹配止于反斜杠，不再吃掉 JSON 转义；结构化 artifact 先逐字段脱敏再序列化，保证是合法 JSON。④`run-harbor-tb2.ps1 -Repeats 3 -Tag r2`：每次重复一个 Harbor job（`jobs/r2/rep0..2`），已完成的跳过、半途的 `harbor jobs resume`，报告加按题 k/3 表。
- **W5-13 外部对照第二轮（box，10 题 × 3，2026-10-12 04:41–05:48 UTC+8，空闲价，账本 ¥1.8624）**：`evals/baselines/2026-10-12-harbor-tb2-r2/`。30/30 完成、0 异常，**解决 26/30 = 86.7%**（Wilson 70%–95%），和第一轮 9/10 没有可见差别；每题至少一次解决 10/10，三次全过 7/10。polyglot-c-py 从 0/1 变成 2/3：30 次都把复现脚本写在 `/tmp/tw_repro/`，任务目录里没有残留；剩下的失败是步数上限，以及题面 gcc 命令生成的 `cmain`。新出现的失败是 overfull-hbox 2 次撞到 750s Agent 超时、cobol 1 次用完 100 步。轨迹 924 次 `thinking=false`，2903 份 JSON artifact 全部合法。缓存命中 97.9%，每次 ¥0.062。box 的自定义 Docker 网络不通，原因是 iptables-legacy 里残留的 FORWARD DROP；在 legacy `DOCKER-USER` 里加了一条 ACCEPT，没有重启 dockerd，也没改 daemon.json。
- **W5-13 第三轮准备：超时循环守卫 + 外部任务时间预算**（针对 r2 的 4 次失败）：新增 `harness/timeouts.py` 和 `HarnessConfig.timeout_guard`。功能：命令超时后注入提醒（放后台轮询、缩小规模、更短的 timeout_s、更便宜的做法）；与已超时命令几乎相同的命令（数字归一后 token Jaccard ≥ 0.8）默认拦截不执行（`warn` 模式照常执行、附警告），显式调大 timeout_s 且剩余时间够时放行；单条命令的 timeout_s 压到剩余墙钟以内（留 45 秒）；墙钟用到 50% / 75% / 90% 时提示已用和剩余时间。默认关：仓库模式（SWE）行为不变，默认值不进 harness_hash。Harbor Agent 默认打开（`--ak timeout_guard=block|warn|off`），并从试验目录的 config.json + task.toml 读该题 Agent 超时（`--ak time_budget=auto|秒数|none`）：墙钟上限 = 预算 − max(60s, 10%)，步数上限按 5 秒一步折算、夹在 100–200（750s → 150 步 / 675s，900s → 180 / 810s，1200s → 200 / 1080s；`--ak max_turns=N` 可覆盖）；提示里写明限时，并提醒删掉自己编译出的可执行文件（r2 polyglot 留下的 `cmain`）。
- **W6 记忆与 Skill（spec 013 草稿，待 Eva 审）**：
  - 记忆仓库 `TW_HOME/memory/<仓库>/`（不写进用户仓库）用 Agent Memory Repo 格式：`MEMORY.md`（仓库事实 + `## Index`）、`episodes.md`（经验片段）、`skills/<名>/SKILL.md`；每条一行，带 `[source: tw://run/<id>; added: 日期; id; kind]`；每次写入一次 git 提交，`tw memory forget` 撤销；按 origin 远端隔离（同仓库不同克隆共享）。密钥命中直接拒，不存脱敏版。
  - 使用：仓库事实 + 技能目录（只有 name + description）进 Executor 稳定前缀，Planner 前缀只放事实，Planner 输入追加按 Issue 检索的 3 条经验（`<memory source="episodes">`）；新工具 `load_skill` 按需读正文。没有记忆时前缀逐字节不变。`tw run` 默认读（有才读，`--no-memory` 关），评测 / Harbor / 基线不读不写。
  - Skill 按 Agent Skills 规范（版本、状态、来源、范围放 `metadata` 的 `tw-*` 键），候选池 `pool/<名>/v<N>/` 带合入 / 拒绝 / 回滚历史。
  - 蒸馏 `tw memory distill <run> --live`：只接受验证通过的 run，新角色 reflector（flash 非思考）出 JSON 候选，全部带来源、过静态检查，只进候选区（事实 / 经验 `tw memory accept`，Skill 必须过门禁）。
  - 静态检查：长度、密钥、绕过（忽略指令 / --no-verify / 关检查 / 删测试 / 提权 / 谎报）、外传、任务答案（diff、来源补丁代码行、判分测试名）、Skill 命名，每条规则有正反例。
  - A/B 门禁：ext-reserve 上选 held-out（排除来源、可按来源日期做时间切分、repo / global 范围、不足 8 个不跑），有 / 无 Skill × 2 次配对，成功率提升且单次成本不超 5% 才合入，报告自动生成（McNemar、Wilson、bootstrap）。`tw memory gate plan|fake` ¥0；真跑 `scripts/skill_gate.py run --yes`（约 ¥4，需确认，本轮未跑）。
  - 监控：`tw run` 结束记录每个注入 Skill 的结果，真正读过正文的样本 ≥ 8 且成功率低于门禁 A 臂 15 个百分点以上时自动回滚。导出 `tw memory export --format memory-repo|agents-md|claude-skills|opencode|agents-skills`。
- **W5-09/10/11 第一轮 OFAT 消融（Eva 本机，2026-10-12 00:36–07:20 UTC+8，空闲价，账本 ¥9.9213，代码 `c6e32c0`）**：`evals/baselines/2026-10-12-ofat-w5/`。dev 15 × 10 配置 × 1 次，150/150 完成、infra_error 0。**10 个配置逐题结果完全相同（12/15，同样 3 题不过）**，McNemar 不一致对全 0；dev 15 已饱和（即使 15/15 也只有 p=0.25），解决率上只能作探索性结论。唯一站得住的差别是成本：thinking=high ¥0.138/题、Planner ¥0.143/题，约为基线 ¥0.042 的 3.3–3.4 倍（配对 bootstrap 区间不含 0），解决率无收益；repro-first 最便宜（¥0.040）。上下文策略在 128K 下基线 0 次清理 / 压缩，单次最大输入 101K，远低于 1M 档清理线 ≈476K，所以在默认 long-context-1m 下几档完全等价。默认配置不改；下一轮改用 ext-reserve、少臂。结果包缺 `.z06`（44 个逐题目录的轨迹丢失，不影响结论）。
- CI：Windows 作业解析 `scripts/windows/*.ps1`（PowerShell 5.1 语法 + BOM / CRLF 检查）。
- 默认权限模式仍是 `auto_review`（未改，等 Eva 决定）。
  - **跨厂商评审（W4-08，只用假模型测）**：`vendor_policy: cross_vendor` 时 Reviewer 路由排除 Executor 的厂商；开工前预检，凑不出异厂商直接失败（不花钱）。
- **Agent 循环（借鉴 Claude Code 核心循环）**：同一轮里连续的只读工具（read_file / list_files / grep / repo_map / git）并发执行，结果顺序不变；中途结束 / 中断时给没执行的工具调用补“未执行”结果，续写请求始终合法；API 重试默认 10 次指数退避（1 s 起、32 s 封顶、带抖动），`TW_LLM_PERSISTENT_RETRY=1` 时 429 / 503 一直重试（单次 ≤ 60 s、总计 ≤ 6 h）。
- **上下文保护**：请求前估算超过窗口硬上限时先强制清理 / 压缩，仍超就体面结束（`context_overflow`）；厂商报上下文超限时压缩后重试一次；连续 2 次压完仍超压缩线就停下（`context_thrash`），不再无限压缩；压缩后重读最近修改的 5 个文件。
- **断点续跑**：任务每一步把改动文件全文、复现结论、NOTES 存进 `runs/<id>/resume/`；停止 / 失败 / 中断（进程退出）的任务轮显示「继续」，新开一轮从上次进度接着做（`tw run --jsonl --resume <run_id>`）。复现测试已被接受就沿用，没被接受只恢复测试侧文件、重新复现。
- **开 PR（审批后）**：结论卡「开 PR」先弹审批卡（仓库 / `tw/<run_id>` → 目标分支 / 标题 / 提交与改动文件 / 授权方式），确认后才推送分支并在 GitHub 上创建 PR，结论卡显示 PR 链接；同一分支已有 PR 时直接返回，不重复开。核心 `tw pr plan`（不联网）/ `tw pr open --yes`（REST API 或本机已登录的 `gh`）；结果记在 `runs/<id>/pr.json`。GitHub 令牌在 设置 → 连接器 填写，存系统凭据库（`github-token`），只注入 `tw pr` 子进程（推送用环境变量里的 `GIT_CONFIG_*` 头，不进命令行、文件或日志）；附最小权限指引：细粒度令牌、只选这个仓库、只给 Contents 与 Pull requests 读写、设过期时间。
- **诊断包**：设置 → 关于「导出诊断包」（日志 + 最近 3 次运行）、结论卡「诊断包」（只收这次运行），`tw diag export [--run <id>] [--out <zip>]`。zip 里是 system / 用量 / 日志 / 运行目录的文本文件 + MANIFEST，常见密钥形态和本机环境里的真实密钥值都替换为 `***`，家目录换成 `~`；不收 LLM 缓存、worktree、二进制、超过 2 MiB 的文件。只存在本机 `$TW_HOME/diagnostics/`，不上传。

### 修复
- **长输入不再被悄悄截断**：附件按任务分配内联（以前超过约 2.4 万字符的附件中段会被二次头尾截断）；NOTES.md 在压缩后 / 续跑时完整带回（以前只带 6000 / 4000 字符）；AGENTS.md 不再写死 4000 字符上限。
- **结论卡金额与账本一致**：显示实付（本机缓存命中不联网也不计费，记 ¥0），名义价放在悬停提示里；任务成本包含本轮对话阶段的调用（结论卡 = 轮次合计 = 账本）。
- **审核模型的花费记入 `reviewer` 类别**（之前混在 dogfood 里），并作为 `role=reviewer` 的 model_call 计入运行成本。

## [0.3.1-preview] - 2026-10-11

### 变更（不兼容）
- **正式版移除演示模式**：安装包（前端 + 内置 `tw.exe`）不再包含演示适配器、演示运行方式、侧栏里的录制回放和任何「演示」选项 / 签；设置里的“运行方式”去掉，应用始终用真实模型（deepseek-flash）。脚本化模型 / 回放只留在源码里给测试和开发构建用（PyInstaller 排除并在构建时校验，前端只在 `import.meta.env.DEV` 下，CI 扫描正式版前端包）。打包后的 `tw.exe run --demo` 直接报“正式版不含演示模式”。
- **需要 DeepSeek API 密钥**：首次打开（凭据库里没有密钥）会弹出引导，粘贴密钥存进系统凭据库，附“去 DeepSeek 开放平台创建密钥”链接；没填密钥就发送也会弹它，而不是让任务失败。

### 新增
- **对话轮（像 Claude 一样）**：每条消息先由模型决定直接回答还是开始干活。问候 / 感谢 / 问题直接回复（没有工具、补丁、证据、结论卡，状态签显示“已回复”）；明确要求修改且已选仓库才转成仓库任务；没选仓库就请你先选一个。提示词 `prompts/chat.md`（v1），对话调用记入账本（类别 `chat`），受高峰闸门与预算上限约束。
- **多轮会话**：同一会话里继续发消息就是跟进，核心沿 `turn.json` 链带上最近 20 轮历史（`tw run --jsonl --parent-run <run_id>`）；之前各轮显示在上面，重试 / 编辑只作用于最后一轮。
- 事件 `user_message` / `turn_finished`（tw-events/1 新增 kind，旧轨迹照常显示）；桥接结果多了 `kind`（`chat` / `task`）和 `reply`。
- 高峰时段被拒时给出可操作的提示（桥接 `error.code = peak_blocked`，去 设置 → 预算 允许高峰调用）。
- 测试用本机 OpenAI 兼容模拟服务（`packaging/mock_llm.py`）+ 仅限 127.0.0.1 的 `TW_LLM_BASE_URL_OVERRIDE`：CI 和打包冒烟用它跑真实适配器 → SSE 流式 → 对话轮 → Executor 全链路（「你好」直接回复、多轮复述、未选仓库、一个小任务），¥0、不需要密钥。

### 修复
- `submit_repro`：复现命令自身跑不起来（exit 126/127「command not found」、没装 pytest、pytest 用法错误 / 没收集到测试）不再算“复现成立”，而是拒绝并提示先确认解释器和测试框架（`error_code=repro_cmd_broken`）。真实 key 首跑发现：机器上没有 `python` 时，`python -m pytest` 的 127 被当成复现失败，修复后复验两边都“失败”，结论变成“复验未过”。

### 验收（真实 key，首次）
- 在开发机上用真实 DeepSeek 密钥（deepseek-flash，经账本）从正式版前端包 + 开发桥 + 打包核心跑通：「你好」直接回复、多轮跟进复述、verses 小任务（询问模式、自动审核模式）均“复验通过”。自动审核模式下 5 次命令由审核模型自动批准（每次约 ¥0.0004），1 次访问工作区外路径升级给人批准。截图 `docs/images/v0.3.1/`（均为真实模型输出）。合计实际花费见 `apps/desktop/STATUS.md`。

### 移除
- 前端的演示 / 回放 / 压测来源和“运行方式”设置（开发构建仍可用）。

## [0.3.0-preview] - 2026-10-11

第一个公开预览版。

### 新增
- **安装包自带核心**：核心用 PyInstaller 打成 onedir（`tw.exe` + `_internal/`），作为 Tauri 资源装到 `<安装目录>\core\`。桌面端先找内置核心，找不到再退回 `TW_CORE` / PATH 上的 `tw` / `python -m triwitness`（开发用）。不需要另装 Python。
- **预算页接真实账本**：设置 → 预算 和状态栏余额改为读本机 `~/.triwitness/ledger.sqlite`（新命令 `tw budget --json`，只读、不联网）；没连上核心时显示“—”，不再显示示例数据。
- **结论卡交付按钮**：“复制 PR 说明”“打开运行目录”。
- **检查更新**：打开 GitHub Releases 页面（预览版不自动更新）。
- Windows 打包 CI（`package-windows.yml`）：在 windows-latest 上构建核心和 NSIS 安装包，对打包后的 `tw.exe` 做冒烟（`--version`、`budget --json`、两次 `run --demo --jsonl` 往返），再静默安装一遍、对装好的核心再冒烟一次，安装包和 sha256 作为 artifact 上传。
- 打 `v*` 标签时的发布流程（`release.yml`）：构建安装包，从本文件取说明，创建**草稿** Release（附安装包和 `.sha256`）。
- ADR-0006（单厂商路由与默认 harness）采纳。

### 变更
- **如实表述交付**：界面、README、文档统一为“生成本地分支 + PR 说明”；状态名“待批 PR / PR 已开”改为“待确认交付 / 分支已就绪”。TriWitness 目前不推送、不在 GitHub 上创建 PR。
- 版本号：桌面端 0.2.1 → 0.3.0-preview；核心 0.0.1 → 0.3.0a1。界面版本号集中在一处。
- README 重写（安装、SmartScreen、快速开始、权限模式、成本、已知限制、路线图）。

### 修复
- 冻结（打包）后的核心能正确找到 `configs/`（风险策略、模型、价格），也能用 `tw.exe -m unittest` 跑演示仓库的测试。
- 预算页账本按时间从新到旧排序。
- Windows：核心在 PowerShell / 桌面端环境里起任务时可能卡在“查找 Git Bash”（`git --exec-path` 超时后被管道拖住，永不返回）；现在先按 PATH 上的 git 位置和常见安装目录找 bash.exe，最后才问 git，并且不再用管道读它的输出。

## [0.2.1] - 2026-10-11

Eva 0.2.0 真机反馈的 5 个问题和 3 条建议（权限四种模式、仓库选择对话框、纸书配色深色模式、长会话性能等），见 `apps/desktop/STATUS.md`。

## [0.2.0] - 2026-10-10

第一个 Windows 安装包（内部试用，不含 Python 核心）。
