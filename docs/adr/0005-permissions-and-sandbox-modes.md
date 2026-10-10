# ADR-0005：权限管理与沙箱模式（无沙箱默认 + 一键启用沙箱）

- 状态：方向已由 Eva 拍板（2026-10-10）；细节（默认规则、模式名）待 Eva 审阅｜关联：spec 002（沙箱运行时，已重写）、spec 006（权限，新增）、ADR-0001 #2（工具名）、#7（`.tw/`）
- 编号说明：0004 预留给命名检索（W1-02），原先预留给路由复核的 0005 顺延为 **ADR-0006（docs/adr/0006-routing.md，W2-26）**。

## 1. 背景

规划默认“终端用户也用 Docker 沙箱”（spec 002 旧版、04 §2.4：DockerSandbox 默认，E2B 可选，不支持 Windows 容器）。Windows 终端用户要装 Docker Desktop（WSL2、约 1GB、管理员、重启、商用授权限制），门槛太高。

Eva 的决定：
1. 终端用户**默认无沙箱**运行；
2. 设置页提供**一键安装 WSL2 + Docker Desktop**（`wsl --install`、winget；管理员与重启由带进度的 UI 处理），装好后**自动启用沙箱模式**；
3. 开发 / CI / 评测**继续用 Docker**；
4. 无沙箱模式的权限管理**照抄成熟 coding agent 的做法**。

## 2. 我们参考了谁（只借鉴设计，不复制代码）

| 来源 | 借鉴点 | 许可证 / 能否复制代码 |
|---|---|---|
| Claude Code 权限（<https://code.claude.com/docs/en/permissions>）、设置层级（<https://code.claude.com/docs/en/settings>） | `Tool(specifier)` 规则语法；allow / ask / deny 三类，**deny → ask → allow** 求值，跨层级 deny 不可被 allow 覆盖；Bash 复合命令按 `&& \|\| ; \| &` 拆分、逐段匹配；剥离 `timeout`/`nice` 等包装；`*` 通配与“`*` 放在子命令之后”；Read/Edit 用 gitignore 风格路径（`//` 绝对、`~/` 家目录、`/` 相对配置源）；Windows 路径先规范成 `/c/Users/...`；符号链接：allow 要求请求路径与真实路径都匹配，deny 任一匹配即拒；权限模式 default / acceptEdits / plan / dontAsk / bypassPermissions；user / project / local / managed 四层，列表合并；项目 allow 规则需“信任工作区”后才生效；“总是允许”写入 `settings.local`；PreToolUse hook 不能绕过 deny；additionalDirectories | 专有（`© Anthropic PBC. All rights reserved`，仓库 anthropics/claude-code 无开源许可证）→ **只借鉴概念，不得复制任何代码或文案** |
| OpenAI Codex CLI（<https://developers.openai.com/codex/agent-approvals-security>、<https://developers.openai.com/codex/windows>） | **审批策略 × 沙箱模式两维矩阵**（read-only / workspace-write / danger-full-access × on-request / never 等）；工作区内 `.git`、`.codex`、`.agents` 即使可写也强制只读（受保护路径）；默认断网；非版本控制目录默认只读；`never` 用于 CI；Windows 原生沙箱（MXC / elevated / unelevated）与 WSL2 的取舍；“容器本身就是边界时内部用 full-access”。注意：官方文档已说明 `untrusted` 审批策略**已退役**，改用项目 `trust_level = "untrusted"` | Apache-2.0（openai/codex）→ 允许复制代码，须保留版权与 NOTICE；本 ADR 仍只借鉴设计 |
| Gemini CLI（<https://geminicli.com/docs/cli/trusted-folders/>、<https://geminicli.com/docs/reference/policy-engine/>） | **受信任目录**：不信任时忽略项目配置、`.env`、MCP、自动批准；**非交互（headless）模式下 ask 视为 deny**；规则带 `modes` / `interactive` 条件；“总是允许”只向更宽松的模式传播；deny 的工具直接从模型工具列表中移除 | Apache-2.0 |
| Cline（<https://docs.cline.bot/features/auto-approve>） | 自动批准按**类别**勾选（读项目 / 读全部 / 改项目 / 改全部 / 安全命令 / 全部命令 / 浏览器 / MCP），“全部”只是“项目”的扩展 → 设置页的类别开关 | Apache-2.0 |
| Roo Code（<https://docs.roocode.com/features/auto-approving-actions>） | 命令前缀 allow + deny 双表、**最长前缀胜出、同等具体时 deny 胜**；默认拒绝清单（`rm`、`sudo`、`git push`、`npm publish`、`Remove-Item`、`Set-ExecutionPolicy`、`curl \| sh`…）；危险替换（`$(...)` 等）即使前缀允许也不自动批准；受保护文件 | Apache-2.0 |
| Cursor（<https://cursor.com/docs/agent/run-modes>） | Run Mode：Allowlist / Auto-review / Run Everything；**删除保护、工作区外文件保护**在任何模式下都要求确认；受保护路径 `.git/config`、`.git/hooks`、`.vscode`；读取边界 System / Workspace + Read Allowlist | 专有 → 只借鉴概念 |

原则：**规则语法主要抄 Claude Code，模式设计主要抄 Codex 的“审批 × 沙箱”矩阵**，其余补丁式借鉴。所有实现自行编写；若将来复制 Apache-2.0 代码片段，在文件头标注来源并在 `NOTICE` 中列出。

## 3. 决定

### 3.1 两个维度：沙箱后端 × 审批模式

沙箱后端（spec 002）：`none`（本机 + git worktree + 权限）、`docker`、`wsl2`、`remote`（只留接口）。
审批模式（spec 006）：

| 模式 | 含义 | 来源 |
|---|---|---|
| `plan` | 只读：读文件、只读命令；不改文件 | Claude `plan` / Codex read-only |
| `ask` | 改文件、非只读命令都要确认 | Claude `default` |
| `auto_edit` | worktree 内改文件自动；允许清单内命令自动；其余 ask | Claude `acceptEdits` + Codex Auto |
| `auto` | 沙箱内一切自动，只有越界（出网、`git push`、发布）才 ask | Codex workspace-write + on-request |
| `full_access` | 不问（deny 规则仍生效）；**仅限 docker / wsl2 / remote**，`none` 后端下禁止 | Claude bypassPermissions / Codex danger-full-access |
| `unrestricted`（无限制 / 勇士模式） | 不问，**内置默认 deny / ask 规则与受保护路径全部解除**；无沙箱也可用；只剩用户 / 管理员自己写的 deny 规则。只能在本次会话 / 任务中经两步确认开启，见 §3.6 | Eva 2026-10-10 新增 |

另有正交开关 `interactive`：`false`（eval、CI、`tw run --non-interactive`）时 **ask 一律按 deny 处理**（Gemini headless、Claude dontAsk、Codex never）。

默认组合：

| 场景 | 后端 | 模式 | interactive |
|---|---|---|---|
| 终端用户（未装沙箱） | `none` | `auto_edit` | 是 |
| 终端用户（一键安装后） | `docker` | `auto` | 是 |
| 开发 / CI | `docker` | `auto` | 否 |
| 评测 `tw eval` | `docker`（强制） | `auto` | 否（ask→deny） |

### 3.2 无沙箱模式的安全边界（诚实说明）

`none` 后端下，权限规则是**护栏，不是安全边界**（Claude Code 文档原话：Bash 规则“isn't a security boundary”）。`/bin/rm`、`sh -c '…'`、脚本里自己开文件都绕得过。因此另加四层兜底：

1. **git worktree 隔离**：任务在 `~/.triwitness/worktrees/<run_id>/`（分支 `tw/<run_id>`）里做，用户的工作目录和当前分支不被修改；结果以 diff / 分支交给用户合并。非 git 目录：拒绝 `none` 模式运行，提示先 `git init` 或启用沙箱。
2. **受保护路径**：`.git/`、`.triwitness/`、`.tw/` 对 Edit 只读（抄 Codex / Cursor）。
3. **环境变量最小化**：子进程只继承白名单变量（PATH、HOME、LANG、TEMP 等）；`DEEPSEEK_API_KEY` 等密钥**永不**进入子进程。
4. **进程树管控**：Windows 用 Job Object（超时杀整棵树、内存上限），POSIX 用进程组 + rlimit。

### 3.3 干净环境复跑证人（三证之一）

`none` 后端没有干净环境：Verifier 改为在**第二个全新 worktree**（从基线提交检出 + 应用 diff）复跑测试，记为“本机复跑”，`verification.clean_env = "unverified"`、`unverified_reason = "no_sandbox"`。规则：
- 证据包与 UI 显示“未在干净环境验证”；
- 风险等级至少 L2（需要人工审查），**不得自动合并**；
- 启用沙箱后自动恢复“干净沙箱复跑”。

### 3.4 Windows：shell 选择

无沙箱模式下的 `bash` 工具在 Windows 上用 **Git Bash**（Git for Windows 自带的 `bash.exe`）：
- worktree 本来就要求装 Git for Windows，Git Bash 几乎一定存在；
- 工具名与工具说明在各平台逐字节一致（ADR-0001 #2，稳定前缀 / 缓存命中）；
- 模型最熟悉 bash 语法，权限解析器只需一套 bash 解析。

找不到 Git Bash 时才退到 PowerShell 7（`pwsh`），作为**另一个工具** `powershell` 暴露，规则写成 `PowerShell(...)`，匹配前把常见别名规范成 cmdlet 名、大小写不敏感（抄 Claude Code 的 PowerShell 规则形态）。不支持 cmd.exe。

### 3.5 一键安装

设置页“沙箱”一节：检测 → 说明与同意（列出要装什么、需要管理员、需要重启、Docker Desktop 授权条款）→ `wsl --install --no-distribution` → `winget install -e --id Docker.DockerDesktop` → 重启后自动续装 → 等 Docker 引擎就绪 → 拉基础镜像 → 冒烟测试 → 切到 `docker` 后端 + `auto` 模式。任何一步失败都可重试，且**不影响继续用无沙箱模式**。细节见 spec 002 §7。

### 3.6 unrestricted（勇士模式）

给明确愿意承担风险的用户。和 `full_access` 的区别：`full_access` 只在沙箱里用、内置 deny 仍生效；`unrestricted` 在宿主机上也能用、连内置 deny 都解除。

- **行为**：永远不弹确认（用户层 ask 规则也不再问）；`configs/permissions.default.yaml` 整层不生效、`.git/` 等受保护路径可写；用户 / 管理员层的 deny 规则仍生效（自己写的底线自己保留）。
- **硬底线（不可关闭）**：① API 密钥 / 令牌类环境变量永远不传给子进程（`scrub_host_env`、沙箱 env 占位符校验）；② eval、CI（`CI` 环境变量）、非交互运行一律拒绝开启；③ 审计日志照常逐条记录；④ 超时杀整棵进程树。
- **开启**：只能交互式两步确认——第一步勾选“我知道没有任何确认和默认拒绝”，第二步输入“我了解风险”。
- **范围**：只在内存里，`scope=task`（任务结束自动回退）或 `scope=session`（应用重启即回退）。**从不写入任何配置文件**；user / project / local / managed 里写 `mode: unrestricted` 一律忽略并告警；管理员可用 `disable_modes` 禁用。
- **可见性**：切换时发 `mode_changed` 事件（`risk=high`），UI 显示红色模式徽标和常驻红色顶部横幅，直到回退（UI-20）。

## 4. 备选与不选的理由

- **强制装 Docker**：门槛高，劝退大部分 Windows 用户。不选。
- **只做 Windows 原生沙箱（AppContainer / Job Object / 受限令牌，类似 Codex elevated/unelevated、MXC）**：工作量大、需要管理员配置、任务环境是 Linux 跑不了。推迟到资金和人手允许时再评估（DF）。
- **云沙箱（E2B 等）做默认**：按量计费、代码出境、国内网络不稳。保留 `remote` 接口，不做默认。
- **Cline 式“由模型自己标记是否安全”**：不可审计、易被提示注入操纵。不选；分类器式自动审查（Codex Auto-review、Cursor Auto-review）也推迟——它要额外模型调用，与 ¥100 预算冲突。

## 5. 后果

- 新增 spec 006 与任务：规则解析器、权限引擎、审批事件、本机后端、UI 审批卡片、设置权限页、一键安装（前端 + 后端）、Docker 后端改按 SandboxBackend 协议实现。
- `tw-events/1` 只增不改：新增 `approval_requested`、`approval_resolved`；`tool_call` 增加可选 `permission`、`permission_rule`；`verification` 增加可选 `clean_env`、`unverified_reason`。
- 评测结果只承认 docker 后端；`none` 后端的运行在报告中标为“未沙箱”，不进入 Leaderboard。

## 6. 已采纳的默认值（Eva 可随时推翻，2026-10-10）

| # | 问题 | 默认 |
|---|---|---|
| 1 | `auto_edit` 下 `npm install` / `pip install` 等装依赖 | **ask**（供应链风险优先于便利） |
| 2 | 模式命名 | 配置与代码里的模式 ID 保持英文（`plan` / `ask` / `auto_edit` / `auto` / `full_access`），UI 显示中文标签（只读规划 / 逐项确认 / 自动改文件 / 沙箱自动 / 完全放行 / 无限制（勇士模式）） |
| 3 | 后台任务审批超时 | **不超时**：任务停在 `needs_human`，直到用户处理或取消 |
| 4 | 一键安装的容器运行时 | 目前**只提供 Docker Desktop**；Rancher Desktop / Podman 分支推迟（probe 仍接受兼容 Docker API 的运行时） |
| 5 | 国内 winget 慢 | 内置下载地址作为 winget 失败 / 超时后的后备（`configs/sandbox_install.yaml`，带检查日期；校验签名发布者，拒绝过期镜像）。2026-10-10 检查：阿里云镜像停更于 2021 年，默认禁用；目前只有官方 CDN 可用 |
| 6 | 本 ADR 状态 | 保持“方向已定”，Eva 审阅（W1-43）后再改为“已采纳” |
