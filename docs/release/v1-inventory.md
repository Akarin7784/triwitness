# 第一版公开发布 · 功能清单（核心 + 桌面端）

- 日期：2026-10-11（北京时间）｜基线提交：7be1d84（桌面 0.2.1）
- **v0.3 更新（同日）**：Eva 批准 v0.3 公开预览切分后，B1 / B4（方案①）/ B5 / B6 / B8（链接）/ B9 / B10 已完成，相关行已改状态并标“v0.3”；B2、B3 等 Eva。
- 核对方式：以**代码**为准（`src/triwitness/`、`apps/desktop/src*`、`tw --help`），再对照 `apps/desktop/docs/claude-parity.md`、`apps/desktop/STATUS.md`、`agent-product/plan/tracker.csv`（82 done / 4 doing / 106 todo / 15 延后）、specs、ADR、README。文档写“done”但代码或验证不支持的，按实际降级。
- 测试现状：Python 567 个测试函数（默认跳过 `integration`（需 Docker）和 `live`（花钱））；桌面 vitest 104 项；e2e 脚本 shoot-replay / test-guards / shoot-ui21 / shoot-ui21c / shoot-review 全过（全部在 Linux headless + 演示适配器下）；CI 三个 job（python / desktop / windows-latest pytest）绿。

图例：
- ✅ 完成可用：端到端跑通且有测试；
- 🟡 部分 / 只在演示模式或 Linux 验证：代码在，但没真跑过真实模型、没在 Windows 真机上验证，或功能不完整；
- ⚪ 只有入口：界面上有按钮，点了提示“即将推出”；
- ❌ 未做。

## 1. Agent 核心

| 功能 | 状态 | 依据 / 说明 |
|---|---|---|
| Agent 循环（工具调用、停止条件、finish 契约） | ✅ | `harness/loop.py`；W1/W2 评测真实跑过（DeepSeek live，50 个 attempt） |
| 工具：read/write/edit_file、grep、list_files、git（只读）、bash / PowerShell、run_tests、notes、submit_repro、repo_map | ✅ | `tools/`；单测 + 评测实跑 |
| Windows 下 bash 走 Git Bash，找不到退回 PowerShell | 🟡 | `sandbox/local.py`；CI windows-latest 真跑，但用户真机未验 |
| lsp 工具（定义 / 引用 / 诊断） | ❌ | W2-09 todo |
| edit_file 失败时给候选 / replace_all | ❌ | W2-11 todo |
| 上下文工程：稳定前缀、`<untrusted>` 包装、工具结果清理、压缩 + NOTES.md | ✅ | `harness/context.py`；W2 上下文真实验证（¥0.99，命中 95%） |
| 前缀缓存纪律（确定性序列化） | ✅ | 测试锁定前缀逐字节不变；实测命中 95–97% |
| repro-first（先写复现测试再修） | ✅ | 默认 harness（ADR-0006 草稿）；W2/W3 实跑 |
| 死循环检测（三种信号 + 提醒 / stuck） | 🟡 | W1 版完成；第二级“回滚到最佳快照”未做（W2-16） |
| 防失控安全上限：轮数、墙钟、输入 / 未命中输入 / 输出 token（0.3.2 起不再有金额上限和熔断） | ✅ | `cost/guard.py`；单测；0.3.2 按 Eva 决定去掉 ¥ 上限 / 信封 / STOP 熔断（ADR-0002 修订 2026-10-11） |
| 全局账本（SQLite，用量日志）、`tw usage`（旧名 `tw budget`）、余额对账 `tw usage sync` | ✅ | 0.3.2 起只统计不限制；sync 只在 W1 做过一次 |
| 高峰时段标注（北京时间工作日 9–12、14–18，2× 价） | ✅ | `llm/gate.py`；0.3.2 起只标注不拦截 |
| Planner / Reviewer 角色、编排状态机、返工回路 | ❌ | W4-01…07 todo；目前是 **Executor 单角色 + 确定性验证（可加 Verifier 模型）** |
| 检查点与断点续跑 | ✅ | 0.3.2：`runs/<id>/resume/` + `tw run --resume`；桌面端「继续」；真实 key e2e（截图 `docs/images/v0.3.2/resume-*.jpg`） |
| HITL（计划确认、依赖升级审批、ask_human） | 🟡 | 只有**工具级权限审批**（审批卡）；计划级 HITL 未做 |
| 附件、用户说明 / 项目知识文件进任务 | ✅ | `harness/inputs.py`；`--attach`、`--guidance-file`；e2e 覆盖（演示） |
| 轨迹记录（JSONL + artifacts） | ✅ | `telemetry/trajectory.py` |
| 轨迹脱敏导出 `tw traj export` | ❌ | W2-19 todo |
| OTel / Langfuse 追踪 | 🟡 | `telemetry/otel.py` + `deploy/langfuse`；W2 跑过，发布版默认不开 |
| 记忆 / Skills（W6） | ❌ | 未开始 |
| `tw serve`（HTTP + SSE） | ❌ | `serve/` 是空包；桌面端改走 stdio 桥（够用） |

## 2. 验证与证据

| 功能 | 状态 | 依据 / 说明 |
|---|---|---|
| 干净沙箱复跑复现测试（基线必须失败、打补丁后必须通过） | ✅ | `verify/rerun.py`；W3-14 在 48 个补丁上实跑（Docker） |
| none 后端的复跑（第二个 worktree，标“未沙箱”） | ✅ | W3-20；单测 |
| 回归对比（只算新增失败）+ flaky 重跑 | ✅ | `verify/pipeline.py` |
| 相关测试选择（命名 + 导入图） | ✅ | `verify/test_select.py` |
| 静态检查（ruff / pyright / bandit / 密钥扫描） | 🟡 | `verify/static_checks.py`；依赖用户机器上装了这些工具，否则跳过 |
| 防作弊 7 条（改测试、skip/xfail、削弱断言、改 conftest/CI…） | ✅ | `verify/anticheat.py`；W3 规则复核 |
| Verifier 模型（多数票，取保守） | ✅ | `--verify model`；W3-14 实跑 ¥2.94 |
| 验证档位：off / deterministic（默认，¥0）/ model | ✅ | 数据：deterministic 精确率 85%、拦下 5/8 假成功 |
| 风险分级 L0–L3（因子表、阻断规则） | ✅ | `verify/risk.py` + `configs/policies/risk.yaml` |
| 证据包 + PR 正文（pr.md） | ✅ | `verify/evidence.py`；桌面端结论卡 + 作品栏可看 pr.md；v0.3 结论卡“复制 PR 说明 / 打开运行目录”，界面与文档如实写“生成本地分支 + PR 说明” |
| 完整证据页（桌面） | 🟡 | 只有结论卡（UI-12 部分） |
| 向 GitHub 开 PR / 推分支（审批后） | ✅ | 0.3.2：`tw pr plan` / `tw pr open --yes`（REST 或 gh），审批卡 + 凭据库令牌 + 最小权限指引；真实临时仓库验收（gh 授权）。回帖 Issue / GitHub App 仍未做；令牌路径只有模拟测试；Windows 凭据库未真机验 |
| CI 回流修复 | ❌ | W5-06 |

## 3. 沙箱与权限

| 功能 | 状态 | 依据 / 说明 |
|---|---|---|
| none 后端（本机 + git worktree + Job Object） | 🟡 | CI windows-latest 真跑；用户真机未验 |
| docker 后端 | ✅ | 开发 / CI / 评测在用；CI 有集成测试。**注意：盒子上的 Docker 在重置中丢了，本地暂时跑不了集成测试** |
| wsl2 后端 | ❌ | W3-21 todo |
| `tw doctor --json`（Docker / WSL / winget 检测） | ✅ | 单测覆盖 UTF-16、无权限 |
| 一键安装 Docker Desktop / WSL2（UAC、进度） | 🟡 | UI-19 部分：代码在，**Windows 真机从未走通**；重启后续装未做 |
| 权限规则 `Tool(specifier)`、deny→ask→allow、分层配置、默认 54 deny / 38 ask | ✅ | `permissions/`；AC1–AC12 单测 |
| 四种模式：只读 / 询问 / 模型自动审批（默认）/ 完全访问 | ✅ | 0.2.1；核心 + CLI + 桥（TS / Rust）+ 设置页 + 迁移 + 测试 |
| 模型自动审批：审核模型 DeepSeek Flash（不思考）、计费、没把握就问人 | 🟡 | 演示模式用规则审核（FakeReviewer）跑通；**真实审核模型从未调用过** |
| 完全访问：两步确认、红色横幅、任务结束回退、CI / 非交互拒绝 | ✅ | 单测 + e2e（演示） |
| 审批卡：允许一次 / 本次任务 / 总是（写 permissions.local.yaml）/ 拒绝 + 附言 | ✅ | e2e 覆盖（演示） |
| 规则编辑器（用户层可增删改，核心实时校验） | ✅ | e2e 覆盖 |
| 审计日志 | ✅ | `permissions/audit.py` |
| 出网控制 / 凭证注入 / MCP 网关（W7） | ❌ | 未开始；目前靠“密钥不进子进程” + 默认 deny 规则 |

## 4. 模型

| 功能 | 状态 | 依据 / 说明 |
|---|---|---|
| DeepSeek 适配器（deepseek-flash，思考 / 非思考，reasoning_content 回传） | ✅ | W1/W2/W3 评测真实调用，总账约 ¥13.6 |
| 录制 / 回放缓存（replay / record / live） | ✅ | `llm/replay.py` |
| 流式（SSE → delta 事件） | 🟡 | 只用合成 SSE 夹具测试，**真实流式从未调用** |
| 思考强度 关 / 低 / 中 / 高 | 🟡 | 参数映射有单测；桌面端真实模式未跑 |
| 白名单（只允许 deepseek-flash，永不 v4-pro） | ✅ | 核心 + 桌面双重限制 |
| 价格表 + 高峰 2× | ✅ | `configs/pricing.yaml`（带核对日期） |
| 单厂商路由（各角色思考档位） | ✅ | 已实现；ADR-0006 已采纳（2026-10-11，Eva） |
| Qwen / GLM / 跨厂商互审 | ⚪ / ❌ | 桌面端灰显“稍后”；适配器未做（DF-01…06，等资金） |
| LiteLLM 传输、`tw doctor` 连通性检查 | ❌ | W2-01 / W2-02 |
| API 密钥存系统凭据库（Rust keyring） | 🟡 | 代码 + 单测在；**Windows 凭据管理器真机未验** |

## 5. 桌面端交互（Tauri 2 + React 19）

| 功能 | 状态 | 依据 / 说明 |
|---|---|---|
| **桌面端驱动核心（stdio 桥）** | ✅ | v0.3：安装包内置 PyInstaller onedir 核心，桌面端优先用它；CI windows-latest 对打包核心和静默安装后的核心都跑了演示往返；用户真机待验（B3） |
| 真实模式（`--live`）从 App 发起 | 🟡 | 0.3.1 起是唯一模式（演示模式已从正式版移除）；真实适配器 → SSE → 对话轮 → Executor 全链路在 CI / 本机用模拟服务跑通（`packaging/mock_llm.py`）；**用真实 DeepSeek 密钥从 App 发起尚未跑**（box 上没有密钥） |
| 对话轮：问候 / 问题直接回复、要动手才转任务、没仓库先请选（0.3.1） | ✅ | `harness/chat.py` + `prompts/chat.md`；单测（意图 5 例、无工具回复无产物、桥接往返）+ 打包冒烟 + e2e 截图（模拟服务） |
| 多轮会话（`--parent-run`，turn.json 历史，之前各轮只读显示）（0.3.1） | ✅ | 单测 + 冒烟 + e2e（模拟服务） |
| 首次使用密钥引导（凭据库，没密钥发送也弹）（0.3.1） | 🟡 | 浏览器 / 开发桥无法访问凭据库（unsupported 不弹）；**Windows 真机未验** |
| 输入框（自动增高、Enter / Shift+Enter、每会话草稿、附件、粘贴 / 拖放） | ✅ | e2e |
| 仓库选择（原生文件夹对话框 / 最近 / 手动） | 🟡 | 0.2.1；对话框只在 Tauri 里有，**Windows 真机未验** |
| 模型选择 + 思考强度子菜单 | ✅ | e2e |
| 流式消息、Markdown、思考折叠、工具行、书写推流面板 | ✅ | e2e + 性能压测（500 轮 59.5 fps） |
| 审批卡、结论卡、完全访问横幅 | ✅ | e2e（0.3.1 起用模拟服务，不再用演示适配器） |
| 停止 / 刷新后续上 / 编辑重发 / 重试 / 版本切换 / 复制 / 反馈 | ✅ | e2e |
| 侧栏（近期、星标、重命名、删除、收起、按项目分组）、会话页（排序 / 搜索 / 批量删除） | ✅ | e2e |
| 搜索面板 Ctrl+K、快捷键表 Ctrl+/ 及其余快捷键 | ✅ | e2e |
| 项目（说明、知识文件、项目里开会话） | ✅ | e2e（数据存 localStorage） |
| 作品栏 / 作品页（patch.diff、pr.md） | ✅ | e2e |
| 导出：复制 Markdown / 导出 Markdown / 导出 PDF | ✅ | 只在本机 |
| 风格（预设 + 自定义） | ✅ | e2e |
| 设置：常规 / 个人资料 / 模型 / 权限 / 沙箱 / 隐私 / 关于 | ✅ | e2e |
| 设置 · 用量页（0.3.2 前叫预算页） | ✅ | 只读：读真实账本（`tw usage --json`），状态栏显示累计已花 |
| 中文 / English | ✅ | i18n 覆盖测试 |
| 浅色 / 深色（纸书配色，AA） | ✅ | 0.2.1 |
| 浏览器默认行为屏蔽、自绘标题栏 / 右键菜单 | ✅ | test-guards 21 项 |
| 换行 / DPI（100/125/150%）检查 | ✅ | shoot-review dpi 遍（headless 模拟缩放） |
| Windows 真机：ClearType、DPI、边缘拉伸、贴靠、多显示器 | 🟡 | Eva 装过 0.2.0 并反馈了 8 条（已修）；UI-08 清单未逐项过 |
| Win11 Snap Layouts（WM_NCHITTEST） | ❌ | UI-14 |
| 语音输入、“+” 菜单（截图 / 网页搜索 / 深度研究 / 技能 / 连接器 / 插件）、更多模型、连接器（GitHub / GitLab / Gitee）、帮助 | ⚪ | 点了提示“即将推出” |
| Chat / Cowork 切换、扩展 | ❌ | 未定义 |
| 分享（云端链接） | ❌ | 分享菜单只做本机导出 |

## 6. 评测

| 功能 | 状态 | 依据 / 说明 |
|---|---|---|
| Harbor 兼容任务格式、`tw task validate` | ✅ | |
| 任务工厂（挖 PR → Dockerfile → F2P/P2P 去抖 → 落盘） | ✅ | dev 15 + test 35 冻结（digest 校验） |
| `tw eval` 运行器、Grader、报告（Resolved@1 + bootstrap CI）、`tw eval estimate` | ✅ | |
| DeepSeek 基线 | ✅ | test 思考 high 16/33 = 48%（CI 33–67%），¥0.233/任务；dev 非思考 12/15 |
| Verifier 三档对比 | ✅ | W3-14 |
| 消融（上下文 / 工具 / repro-first / Planner）、Reviewer 注入缺陷集 | ❌ | W4/W5 |
| 红队集、Leaderboard 站点、HF 数据集发布、`tw eval reproduce` | ❌ | W7/W8 |

## 7. 发布工程

| 功能 | 状态 | 依据 / 说明 |
|---|---|---|
| Windows NSIS 安装包 | ✅ | v0.3：CI（windows-latest）构建，内置核心；Linux 交叉编译仍可出无核心版；没有 MSI |
| 代码签名 | ❌ | UI-16 延后（要花钱）；SmartScreen 会拦“未知发布者” |
| 自动更新 | ⚪ | v0.3：“检查更新”打开 GitHub Releases 页面；没装 tauri updater（v1.0） |
| 崩溃上报 | ❌ | 无（隐私上是优点；但出问题时用户只能手动描述） |
| 遥测 | ✅（不收集） | 代码里没有任何上报；README 和已知限制写明“不收集遥测” |
| 本地诊断导出（日志打包） | ✅ | 0.3.2：`tw diag export`（脱敏 zip，只存本机）；关于页 / 结论卡入口；真实 e2e |
| 开源许可（Apache-2.0 + 第三方许可对话框） | ✅ | 关于 → 开源许可 |
| README / 用户文档 | ✅ | v0.3：README 重写（安装 / SmartScreen / 快速开始 / 权限 / 成本 / 路线图）+ `docs/release/known-limitations.md`；FAQ 未做 |
| CHANGELOG / tag / GitHub Release | 🟡 | v0.3：CHANGELOG.md + `release.yml`（v* 标签 → 草稿 Release 附安装包 + sha256）就绪；**尚未打标签** |
| 撞名检查（W1-02） | ❌ | 延后 |
| CI | ✅ | python / desktop / windows-latest pytest |
| 开发盒子环境 | 🟡 | 2026-10-11 重置后 Docker 没了（集成测试只在 CI 跑） |

## 8. 发布阻塞项（必须先解决或明确写进“已知限制”）

| # | 阻塞项 | 为什么阻塞 | 工作量 | 需要 Eva |
|---|---|---|---|---|
| B1 | **安装包不带 Python 核心** | 普通用户装完点“发送”就是“找不到核心命令”，演示模式也要核心，只剩内置的 3 条回放能看 | 2–4 天：把 python-build-standalone + 核心 wheel 作为 Tauri resources 打进安装包（或首次启动用 uv 自动装），核心路径自动发现 | 决定方案（体积 +30–50 MB）｜**✅ v0.3 已完成（PyInstaller onedir，CI 构建 + 冒烟）** |
| B2 | **App 里从没真跑过一次 DeepSeek 端到端**（真实 key、真实仓库、流式、审核模型） | 核心卖点在真实模式下未验证；流式和审核模型只有夹具 | 0.5 天 + 修 bug | **要**：真实 key、约 ¥1–3、空闲时段 |
| B3 | **Windows 真机验证**：凭据管理器、原生文件夹对话框、Git Bash / PowerShell 执行、worktree、权限 / 完全访问、`tw doctor`、一键安装 Docker | 这些只在 CI 或 Linux 上跑过 | 1 天（按 UI-08 清单）+ 修 bug | **要**：真机 |
| B4 | **“开 PR”并不存在** | README / 产品叙事是 Issue → PR，实际只产出本地分支 + pr.md | 两种选法：①发布说明里改口为“生成可审阅分支 + PR 正文”（0.5 天）；②用 `gh pr create`，在审批后推送（1–2 天，需 GitHub 令牌） | 选方案｜**✅ v0.3 选方案①，已改口；0.3.2 做了方案②（审批 + 最小权限令牌）** |
| B5 | **预算页账本是假数据** | 给用户看伪造的花费，必须修 | 0.5–1 天：`tw budget --json` 接桌面 | 否｜**✅ v0.3 已完成** |
| B6 | **README / 文档过时**，没有安装指南和已知限制 | 公开发布第一印象 | 1 天 | 审阅｜**✅ v0.3 已完成** |
| B7 | **未签名** → SmartScreen 警告 | 预览版可接受（写清楚）；正式 v1.0 必须签名 | 证书 ¥1–3k/年，或 Azure Trusted Signing 约 $10/月；接入 0.5 天 | **要**：花钱、身份认证 |
| B8 | **没有自动更新**，“检查更新”是假按钮 | 预览版可以改成“打开 GitHub Releases”；v1.0 需要 tauri updater（要签名密钥 + 托管 latest.json） | 0.5 天（链接）/ 1–2 天（updater） | v1.0 需要｜**✅ v0.3 预览版改为链接；updater 留给 v1.0** |
| B9 | **ADR-0006 待采纳** | 决定默认路由和 harness，发布前要冻结 | 15 分钟 | **要**：拍板｜**✅ 已采纳（922b6cd）** |
| B10 | 没有 CHANGELOG / tag / Release 流程 | | 0.5 天 | 审阅｜**✅ v0.3 流程就绪，未打标签** |
| B11 | 开发盒子没有 Docker | 本地跑不了集成测试和评测（CI 仍有）；不影响用户 | 0.5 小时重装 | 同意重装即可 |

## 9. 建议的发布切分

### v0.3「公开预览」（目标：别人能装、能真跑、不骗人）

必须做：B1 核心打包、B2 真实端到端、B3 真机验证、B4 选方案①（如实改口）、B5 真实账本、B6 README + 安装指南 + 已知限制、B8 改成“打开 Releases”链接、B9 ADR-0006、B10 CHANGELOG + tag + GitHub Release（附 sha256）。
另外：把 ⚪ 入口保留（与 Claude 对齐的原则），但在已知限制里列清楚。

- AI 工作量约 **5–7 天**；Eva 约 **1 天**（真机 + 拍板 + 审阅）；花费约 **¥1–3**。
- 明确不做：签名（发布说明写清 SmartScreen 怎么过）、自动更新、Planner / Reviewer、开 PR、wsl2、Qwen / GLM。

### v1.0「正式版」（在 v0.3 之上）

必须做：代码签名（B7）、tauri 自动更新（B8）、~~开 PR（B4 方案②，带审批和最小权限令牌）、断点续跑、本地诊断导出~~（0.3.2 已做）、Windows 真机全清单（UI-08）+ 至少一次一键安装 Docker 走通、真实模式下的审核模型成本 / 质量抽检。

- AI 约 **2–3 周**；Eva：签名证书（花钱 + 身份认证）、GitHub App / 令牌授权、真机。

### 可以往后放（nice-to-have）

Planner / Reviewer 角色与编排（W4）、消融与博客数据（W5）、记忆 / Skills（W6）、安全网关 + 红队（W7）、Leaderboard / 数据集（W8）、Qwen / GLM（等资金）、wsl2 后端、lsp 工具、Snap Layouts、语音 / 连接器等 ⚪ 入口。

## 10. 状态计数（按上面各表逐行统计）

| 分组 | ✅ | 🟡 | ⚪ | ❌ |
|---|---|---|---|---|
| Agent 核心 | 10 | 4 | 0 | 7 |
| 验证与证据 | 9 | 2 | 0 | 2 |
| 沙箱与权限 | 8 | 3 | 0 | 2 |
| 模型 | 5 | 3 | 1 | 1 |
| 桌面端交互（Tauri 2 + React 19） | 20 | 4 | 1 | 3 |
| 评测 | 5 | 0 | 0 | 2 |
| 发布工程 | 5 | 2 | 1 | 4 |
| **合计** | **62** | **18** | **3** | **21** |

v0.3 前：55 / 21 / 3 / 22；v0.3.0：60 / 17 / 3 / 21。

（统计方式：§1–§7 每个表格行取状态列的第一个符号；一行里有两种状态的按第一个计。）
