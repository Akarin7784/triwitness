# Spec 013：记忆与 Skill（仓库事实、经验片段、Skill、蒸馏、门禁、监控、导出）

- 状态：草稿（W6-01；W6-02 ~ W6-09 已实现首版，**待 Eva 审阅**，见 §10）｜负责人：Eva｜目标周：W6｜依赖：008、010、016
- 相关文档：04-detailed-design.md §7.1、§3.4（load_skill）、§6.2（配对检验）；
  [Agent Memory Repo 规范](https://github.com/AgentMemoryRepo/agentmemoryrepo)（Cognition 发布的开放标准，MIT；亦见 cognition.com/agent-memory-repo）；
  [Agent Skills 规范](https://agentskills.io/specification)
- 代码：`memory/format.py`（条目语法）、`memory/store.py`（记忆仓库）、`memory/checks.py`（静态检查）、
  `memory/retrieve.py`（检索）、`memory/skills.py`（SKILL.md + 候选池）、`memory/context.py`（注入）、
  `memory/distill.py`（蒸馏）、`memory/gate.py`（A/B 门禁）、`memory/monitor.py`（监控回滚）、`memory/export.py`（导出）、
  `tools/skills.py`（load_skill）、`cli/memory.py`（`tw memory …`）、`scripts/skill_gate.py`（真跑门禁）、
  `prompts/reflector.md`

## 1. 背景与目标

Agent 每次都从零认识仓库：怎么装依赖、怎么跑测试、哪里有坑，都要重新摸索，花 token 也容易走错。
目标是让 Agent 从**验证通过**的轨迹里学到这些，但：

1. **只有证据表明有提升才合入**（Skill 过 A/B 门禁；事实 / 经验由人接受）；
2. 每条记忆可追溯（来源 run）、可撤销（`forget` / 回滚）、按仓库隔离；
3. 不能学到密钥、绕过检查的“技巧”、或者某个任务的答案（防投毒、防泄漏）；
4. 评测与自动化会话**默认不读不写**记忆，保证基线可复现；
5. 能导出给其他工具（AGENTS.md、Claude Code、OpenCode）。

非目标：向量检索（先用词法检索，§4.3）、跨仓库共享事实、自动接受事实（§10 Q2）、团队共享记忆仓库（v0.5 再议）。

## 2. 三类记忆

| 类型 | 内容 | 存储 | 使用 |
|---|---|---|---|
| 仓库事实（semantic） | 安装 / 测试命令、目录结构、约定、坑 | `MEMORY.md` 正文（每条一行） | 进入 Executor 与 Planner 的**稳定前缀** |
| 经验片段（episodic） | 问题类型 / 根因 / 有效做法 / 无效做法 | `episodes.md` | Planner 输入里按 Issue 检索 top-3（数据块） |
| Skill（procedural） | `SKILL.md`（Agent Skills 规范） | `skills/<名>/SKILL.md` + `pool/` | 前缀只放 name + description；正文用 `load_skill` 读 |

与 04 §7.1 原设计的差别：原设计是 `.tw/memory/repo_facts.yaml` + SQLite。改为 **Agent Memory Repo 格式**
（Markdown + git），原因：人能直接读和改；git 历史就是审计记录；与 Devin 等工具的开放格式一致，导出几乎零成本。
经验片段量大时再加 SQLite / 向量索引（接口 `search_episodes` 不变）。

## 3. 记忆仓库（W6-02）

位置：`TW_HOME/memory/<repo_key>/`（**不写进用户仓库**，避免污染 diff 与泄露到 PR）。

```
MEMORY.md            入口（每次会话加载，保持简短）：仓库事实 + `## Index`
episodes.md          经验片段
skills/<名>/SKILL.md 当前版本的 Skill（已合入）
pool/<名>/v<N>/      全部版本（SKILL.md、gate.md、reject.txt）
pool/pool.json       每个 Skill 的当前版本、各版本状态、门禁摘要、历史
pool/monitor.jsonl   上线后的结果记录
candidates.jsonl     蒸馏出的候选（待接受 / 已拒绝）
```

- `repo_key`：有 origin 远端时为 `host__owner__name`（同一仓库的不同克隆共享记忆），否则 `local__<目录名>-<路径哈希>`。
- 条目语法（Agent Memory Repo）：每条一行 `- 文本 [source: tw://run/<run_id>; added: YYYY-MM-DD; id: f-xxxxxxxx; kind: test]`。
  `source` 与 `added` 是规范推荐键；`id`（内容哈希）用于去重与撤销，`kind` 为事实类别。
  `## Index` 列 `[[episodes]]` 与 `[[skills/<名>/SKILL]]`（链接省略 `.md`）。
- 每次写入一次 git 提交（`tw memory history` 可看）；`tw memory forget <id>` 删除（历史仍可追溯）。
- **密钥命中即拒**，不存脱敏版（脱敏后的“部署用 KEY=***”也没有价值，反而泄露存在性）。

## 4. 使用记忆（W6-03）

### 4.1 注入位置

- Executor 系统提示：`AGENTS.md 摘要` 之后、`可用工具` 之前追加“仓库事实”和“可用技能（name + description）”两段；
- Planner 系统提示：只追加“仓库事实”（Planner 是只读工具集，没有 load_skill）；
- Planner 输入：Issue 之后追加 `<memory source="episodes">` 块（按 Issue 词法检索 top-3，标注来源与日期，声明是数据不是指令）。

记忆为空 / 没有记忆时前缀**逐字节不变**；同一份记忆下同仓库的不同任务前缀相同（缓存照常命中）。事实块按类别 + id 稳定排序、
上限 3000 字符。每次注入写 `artifacts/memory.json`（repo_key、事实长度、是否检索经验、Skill 名与版本），便于审计。

### 4.2 load_skill（W6-04，04 §3.4）

只在有已合入 Skill 时注册。参数 `name`；返回 `# 技能 <名>（v<N>）` + 描述 + 正文；名字不存在时返回 `not_found` 与可用列表。
可重新获取（上下文清理时可换成占位符）。不需要权限审批（只读本地记忆）。

### 4.3 检索

`memory/retrieve.py`：英文词 + 中文二元组，去停用词，IDF 加权，阈值以下不返回。够用前不引入向量库。

### 4.4 谁读、谁写

| 会话 | 读 | 写 |
|---|---|---|
| `tw run`（交互 / 后台，category=dogfood） | 默认读（有才读）；`--no-memory` 关闭 | 只写 Skill 监控记录（§5.4） |
| `tw eval`、Harbor、基线（mode=eval / category=baseline、harbor-external） | **不读** | 不写 |
| A/B 门禁 B 臂 | 只注入待测 Skill（`MemoryContext.with_skills`），不带事实与经验 | 不写 |
| `tw memory …` | — | 唯一的写入口 |

## 5. Skill 与蒸馏

### 5.1 SKILL.md 与版本（W6-04）

遵循 Agent Skills 规范：frontmatter `name`（1–64，小写字母数字与单个连字符，与目录名一致）、`description`（1–1024），
可选 `license` / `compatibility` / `allowed-tools` / `metadata`。我们的版本与治理信息全部放在 `metadata`（string → string），
键名带 `tw-` 前缀：`tw-version`、`tw-status`（candidate / active / rejected / superseded / rolled_back）、`tw-source`、
`tw-added`、`tw-scope`（repo / global）、`tw-gate`（门禁报告路径）。这样导出的文件其他工具可直接读，多出的键会被忽略。

### 5.2 蒸馏（W6-05）

`tw memory distill <run_id> --live`：

1. 只接受 `summary.json` 里 `verdict == "pass"` 的 run；
2. 压缩转录：任务、每个工具调用的一行摘要（失败的带输出片段）、验证结论、结束报告、补丁**统计**（不给补丁正文，减少抄答案）；
3. reflector 角色（deepseek-flash 非思考，`configs/models.yaml`）一次调用，只输出 JSON：≤5 条事实、1 条经验、≤1 个 Skill；
4. 每个候选带 `source: tw://run/<run_id>`，过 §6 静态检查（带来源补丁与复现测试名做“答案”检查）；
5. 结果只进候选区：事实 / 经验写 `candidates.jsonl`（pending / rejected + 原因），Skill 写进池的 candidate 版本。
   `tw memory accept <id>` 才写进记忆（再过一次检查）；Skill 只能经门禁合入。

调用走路由 → 客户端 → 全局账本（category=memory），高峰时段默认拒绝（`--allow-peak` 才调用）。

### 5.3 A/B 门禁（W6-07）

- **held-out**：`evals/suites/ext-reserve`（59 个 SWE-rebench 任务，与 ext 同样加固与去抖）。
  - 永远排除来源任务；来源是评测任务时只取 `created_at` 晚于它的（`--after`，时间切分防泄漏）；
  - `scope=repo`：同一仓库（按 repo_key 归一）；`scope=global`：任意仓库；
  - 按 seed 哈希排序后确定性抽取 ≤12 个；**不足 8 个判 insufficient_heldout，不跑**。
- **设计**：A（无 Skill）/ B（只注入该 Skill），同任务 × 2 次配对（扩档时 3 次），共 `任务数 × 次数 × 2` 次运行。
- **判定**：B 成功率 > A（`min_gain=0`）且 B 单次成本 ≤ A ×（1 + 5%）→ 合入（版本成为当前版本，旧版本 superseded）；
  否则拒绝并记录原因。McNemar 精确检验 p ≥ 0.05 时标“功效不足”（结论按点估计，报告写明，见 Q4）。
- **报告**：自动生成 Markdown（两臂 n、成功率、Wilson 区间、单次成本、配对差的 bootstrap 区间、McNemar），存为
  `pool/<名>/v<N>/gate.md`，摘要写进 `pool.json`。
- **执行**：`tw memory gate plan`（只出计划与预估）、`tw memory gate fake`（假 runner，¥0，验证流程）；
  真跑 `scripts/skill_gate.py run … --yes`（EvalRunner、高峰不开跑、账本 category=skill-gate、总额上限、可续跑），
  `report --apply` 写结论。**真跑花钱，必须人工确认**（12 任务 × 2 × 2 = 48 次，约 ¥4）。

### 5.4 监控与自动回滚（W6-08）

`tw run` 结束后，对每个注入的 Skill 记一行 `{skill, version, run, solved, loaded}`（loaded = 这次真的调用了 load_skill）。
只看 loaded 的最近 20 次：样本 ≥ 8 且成功率 < 门禁 A 臂成功率 − 15 个百分点 → 自动回滚到上一个通过门禁的版本
（没有就移除），写进 `pool.json` 历史并 git 提交。没有门禁记录的版本不自动回滚。`tw memory monitor [--apply]` 手动查看 / 执行，
`tw memory rollback <名>` 人工回滚。

## 6. 静态检查（W6-06）

| 规则 | 拒绝的内容 |
|---|---|
| length | 事实 > 300 字符、经验 > 800、Skill 描述不在 1–1024、正文 > 12000 字符或 > 500 行、空内容 |
| secret | 轨迹脱敏（core/redact）与任务加固（task_hardening）的全部密钥规则 |
| bypass | 忽略之前的指令 / 冒充系统、`--no-verify` / 改 hooksPath、关闭检查 / 沙箱 / 权限 / 评审、跳过或删除测试、提权、谎报测试结果 |
| exfiltration | curl / wget 上传、nc 外连、scp 到远端、粘贴站 / 回调站、“发送环境变量 / 凭据” |
| task_answer | diff 片段；来源补丁的新增代码行（≥25 字符、像代码）；来源任务的判分 / 复现测试名 |
| skill_name | 不符合 Agent Skills 命名规则 |

每条规则有正反例单测（`tests/unit/memory/test_checks.py`）。`tw memory check <文件>` 可单独运行。

## 7. 导出（W6-09）

`tw memory export --format <格式> --out <目录>`（只写 `--out`，不碰代码仓库）：

| 格式 | 输出 |
|---|---|
| memory-repo | `MEMORY.md`（现渲染，索引与当前 Skill 一致）+ `episodes.md` + `skills/<名>/SKILL.md`（Agent Memory Repo） |
| agents-md | `AGENTS.memory.md`：带起止标记的片段（事实 + 技能目录），可贴进 AGENTS.md，重复导出可整段替换 |
| claude-skills | `.claude/skills/<名>/SKILL.md` |
| opencode | `.opencode/skills/<名>/SKILL.md`（OpenCode 项目级 Skill 目录） |
| agents-skills | `.agents/skills/<名>/SKILL.md`（跨工具通用目录） |

只导出已接受的事实 / 经验与当前版本 Skill。

## 8. CLI

`tw memory show | add-fact | forget | candidates | accept | reject | distill | check | add-skill | gate plan | gate fake |
rollback | monitor | export | history`，`tw run --memory/--no-memory`。

## 9. 验收（对应 TASKS W6）

- W6-02：读写、来源、按仓库隔离、密钥拒绝、会话类型（`test_format_store.py`）；
- W6-03：前缀稳定（有 / 无 / 同一记忆）、Planner 输入含检索结果、编排端到端（`test_skills_context.py`、`test_memory_wiring.py`）；
- W6-04：只注入元数据、load_skill 返回正文、版本与回滚；
- W6-05：FakeRouter 上产出带来源的候选；真实 run 上的 e2e 见 CHANGELOG；
- W6-06：每条规则正反例；
- W6-07：时间切分 / 范围 / 排除的选择测试、判定、报告、不足不跑；
- W6-08：模拟退化触发回滚；W6-09：五种格式的导出测试。

## 10. 开放问题（待 Eva 决定）

- **Q1 同仓库 held-out 不够**：ext-reserve 每个仓库至多 2 个任务，`scope=repo` 永远凑不够 8 个。现在 repo 级 Skill
  会判 insufficient_heldout（不合入）。选项：(a) 允许 repo 级 Skill 用 global 门禁（测“不伤害通用能力”，不测“对本仓库有用”）；
  (b) 为常用仓库用 task_factory 造同仓库时间序列任务；(c) repo 级 Skill 只靠人工审 + 监控上线。建议 (a)+(c)。
- **Q2 事实自动接受**：目前事实 / 经验都要 `tw memory accept`。是否对“通过检查且来自 verdict=pass 的 test / install 类事实”自动接受？
- **Q3 `tw run` 默认读记忆**：现在默认开（有才读）。桌面端是否需要开关 / 显示“本次用了哪些记忆”？
- **Q4 门禁阈值**：是否要求显著（p < 0.05）才合入？以 ~10 个任务 × 2 次，几乎不可能显著；现按点估计 + 标注功效不足。
  每次真跑门禁约 ¥4，是否给每周门禁预算？
- **Q5 监控基线**：日常任务与 held-out 评测任务的成功率不完全可比，阈值 −15pp 是否合适？还是改为“定期在 held-out 上复测”？
- **Q6 导出路径**：`.opencode/skills`（已核对 OpenCode 文档）、`.claude/skills`、`.agents/skills` 是否够？是否要直接写进仓库？
