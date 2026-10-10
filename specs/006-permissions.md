# Spec 006：权限与审批

- 状态：草稿｜负责人：Eva｜目标：地基块（W1 尾 / W2）｜依赖：spec 002、spec 003（工具）、spec 005（事件）
- 决策依据：ADR-0005（参考 Claude Code、Codex、Gemini CLI、Cline/Roo、Cursor 的设计；只借鉴概念）

## 1. 背景

终端用户默认无沙箱（`none` 后端），Agent 直接在本机执行命令。需要一套确定性的、可审计的权限系统：哪些操作自动放行、哪些要用户确认、哪些一律拒绝。沙箱后端下同一套规则继续生效（deny 永远生效）。

## 2. 目标

1. 规则语法 `Tool` / `Tool(specifier)`，三类 allow / ask / deny。
2. 五种审批模式 + `interactive` 开关（ADR-0005 §3.1）。
3. 配置分层与合并；项目规则需工作区信任。
4. 默认规则集（破坏性命令、网络、工作区外路径、密钥文件、`git push`）。
5. 审批事件 `approval_requested` / `approval_resolved` 与 UI 审批卡片。
6. 审计日志。

## 3. 非目标

- 不做 OS 级强制（那是沙箱后端的职责，spec 002）。
- 不做模型分类器式“自动审查”（预算原因，推迟）。
- 不做企业托管策略下发（只预留 `managed` 层的文件位置）。

## 4. 规则语法

### 4.1 工具类别

规则中的工具名是**类别**，映射到 ADR-0001 #2 的具体工具：

| 类别 | 覆盖的工具 | specifier |
|---|---|---|
| `Read` | `read_file`、`list_files`、`grep`（及 Bash 中识别出的 `cat`/`head`/`<` 重定向等） | gitignore 风格路径 |
| `Edit` | `write_file`、`edit_file`（及 Bash 的 `>`/`>>`/`tee` 目标） | gitignore 风格路径 |
| `Bash` | `bash`、`run_tests` 实际执行的命令 | 命令模式 |
| `PowerShell` | `powershell`（仅 Windows 无 Git Bash 时） | 命令模式（别名规范化、大小写不敏感） |
| `Fetch` | 将来的联网工具；沙箱 allowlist 网络策略 | `domain:<host>` |
| `Mcp` | 将来的 MCP 工具 | `server__tool`，支持 `*` |

`Read` 的 deny 同时阻止 `Edit`（不能写一个不能读的文件）。

### 4.2 命令模式（Bash / PowerShell）

- `Bash` 或 `Bash(*)`：所有命令。
- `Bash(npm run test)`：精确匹配。
- `Bash(npm run test *)`：`*` 匹配任意文本（含空格）；**末尾 ` *` 也匹配不带参数的形式**；`Bash(ls *)` 不匹配 `lsof`，`Bash(ls*)` 匹配。
- `Bash(npm run test:*)` 等价于 `Bash(npm run test *)`（只在末尾识别 `:*`）。
- 允许规则中 `*` 出现在子命令之前（如 `Bash(git * main)`）时启动告警。

匹配前处理：
1. **拆分复合命令**：`&&`、`||`、`;`、`|`、`|&`、`&`、换行；子 shell、`$(...)`、反引号、`for/while` 体内的命令也提取出来。
2. **allow**：每个子命令都必须被某条 allow 规则（或内置只读集）覆盖。**deny / ask**：任一子命令匹配即生效。
3. **剥离包装**：`timeout`、`time`、`nice`、`nohup`、`stdbuf`、`command`、`builtin`、无参 `xargs`；allow 只剥离已知安全的前置变量赋值（如 `NODE_ENV=test`），deny/ask 剥离任意前置赋值。
4. **无法解析**（引号不闭合、超过 10,000 字符、`&&` 后为空、危险替换如 `${var@P}`）→ 视为 ask。
5. `sh -c`、`bash -c`、`pwsh -Command`、`python -c`、`node -e`、`eval`、`iex`/`Invoke-Expression` 等“执行字符串”的形式：内部字符串**不**展开匹配，整体按 ask 处理（除非显式 allow 了完整命令）。
6. 重定向目标按 `Edit` / `Read` 规则检查；`/dev/null`、`2>&1`、heredoc 不检查。

### 4.3 路径模式（Read / Edit）

gitignore 语义：`*` 不跨目录，`**` 跨目录；裸文件名任意深度匹配（`Read(.env)` ≡ `Read(**/.env)`）。

| 前缀 | 含义 |
|---|---|
| `//path` | 文件系统绝对路径（Windows：`//c/Users/...`；`//**/.env` 跨所有盘符） |
| `~/path` | 家目录 |
| `/path` | 相对**规则所在配置源**的根（项目配置 = 仓库根；用户配置 = `~/.triwitness/`） |
| `path` 或 `./path` | 相对当前工作区根（none 后端 = worktree 根） |

同一配置源内 `!pattern` 为排除（如 `Read(!.env.example)`），只作用于同源、在它之前的相对规则。

**路径规范化**（所有平台都做，Windows 尤其重要）：
1. 转绝对路径并 `resolve`（展开 `..`、符号链接、Windows junction）；allow 要求**请求路径与真实路径都**匹配，deny/ask **任一**匹配即生效。
2. Windows：`C:\Users\A` → `/c/Users/A`；比较时大小写不敏感；8.3 短名展开为长名（`GetLongPathNameW`）；去掉末尾的 `.` 与空格；`\\?\` 前缀去掉。
3. 拒绝/询问：UNC 路径 `\\server\share`（访问会发送 Windows 凭证）→ ask；NTFS 备用数据流 `file:stream` → deny；保留设备名 `CON`、`NUL`、`COM1`… → deny（`NUL` 作为重定向目标除外）。
4. Git Bash 下的 `/c/...`、`/tmp`（映射到 `%TEMP%`）先经 `cygpath -w` 等价逻辑转换再比较。

### 4.4 Fetch / Mcp

`Fetch(domain:example.com)`、`Fetch(domain:*.example.com)`（子域，不含顶级）；`Mcp(github__get_*)`。

## 5. 求值

```
deny 规则（任一层）命中 → deny
ask  规则（任一层）命中 → ask
受保护路径（.git/ .triwitness/ .tw/ 的 Edit）→ deny（full_access 也不放行 .git/hooks）
allow 规则命中 或 模式默认放行 → allow
否则 → 模式默认（见 §6 表）
```

规则具体程度不改变顺序：宽的 deny 不能被窄的 allow 打洞（抄 Claude Code；与 Roo 的“最长前缀”不同，更易推理）。
随后：`interactive = false` 时 ask → deny（`approval_resolved.by = "policy"`）。

## 6. 模式默认行为

| 操作 | plan | ask | auto_edit（none 默认） | auto（docker 默认） | full_access |
|---|---|---|---|---|---|
| 工作区内读 | allow | allow | allow | allow | allow |
| 工作区外读 | ask | ask | ask | 沙箱内无宿主文件 | allow |
| worktree 内改 / 建文件 | deny | ask | allow | allow | allow |
| 工作区外改 | deny | ask | ask | 不可达 | allow |
| 内置只读命令（`ls`、`cat`、`git status/log/diff/show`、`rg`…） | allow | allow | allow | allow | allow |
| `run_tests`（任务配置的测试命令） | deny | ask | allow | allow | allow |
| 其他命令 | deny | ask | ask | allow | allow |
| 出网（`curl`、`pip install`、`npm install`、`Fetch`） | deny | ask | ask | ask（沙箱默认断网） | allow |
| deny 规则 | deny | deny | deny | deny | deny |

`full_access` 在 `none` 后端下不可选（配置加载时报错）；只能在用户层或 CLI 设置，项目 / local 配置里写了无效（抄 Claude Code）。

## 7. 审批流程与事件

1. 引擎判为 ask → 写 `approval_requested`（tw-events/1，见 `core/events.py`），任务状态 → `needs_human`（后台任务）或在交互会话中等待。
2. UI 审批卡片显示：工具类别、规范化后的命令/路径（已脱敏）、原因、命中规则与来源、风险等级；按钮：**允许一次 / 本次任务内允许 / 总是允许（写入 local 规则，可编辑 `suggested_rule`）/ 拒绝（可附理由）**。
   - “总是允许”只对能完整展示其含义的规则提供（例如复合命令拆成多条，最多 5 条；带 `*` 的建议规则需用户确认文本）。
   - 拒绝附言作为工具结果回传模型，模型可换路子；无附言的拒绝结束本轮并等待用户。
3. 写 `approval_resolved`（`by = user / policy / timeout / cancelled`）。
4. 超时：交互会话默认不超时；后台任务可配置 `approval_timeout_s`，超时按 deny。
5. 同一请求重复出现（同类别 + 同规范化动作）时复用“本次任务内允许”的决定。

## 8. 配置文件与优先级

YAML（与 `configs/` 一致）：

| 层 | 路径 | 说明 |
|---|---|---|
| managed | Windows `%ProgramData%\TriWitness\permissions.yaml`；POSIX `/etc/triwitness/permissions.yaml` | 最高；预留，v0.1 只读取 |
| session | CLI `--permission-mode`、`--allow`、`--deny`；UI 本次任务设置 | 只对本次运行 |
| local | `<repo>/.triwitness/permissions.local.yaml` | 个人、不进 git（首次写入时加入 `.git/info/exclude`）；“总是允许”写这里 |
| project | `<repo>/.triwitness/permissions.yaml` | 团队共享、可提交 |
| user | `~/.triwitness/permissions.yaml`（`TW_HOME`） | 个人全局；设置页写这里 |
| default | 随包发布 `configs/permissions.default.yaml` | 内置默认规则（§9） |

- 标量（`mode`）：managed > session > local > project > user > default。
- 列表（allow / ask / deny、`additional_directories`）：**各层合并**；deny/ask 来自任何层都生效。
- **工作区信任**：project 层（以及被 git 跟踪的 local 文件）中的 `allow` 与 `additional_directories` 只有在用户信任该仓库后才生效；deny / ask 立即生效。信任记录在 `~/.triwitness/trusted.yaml`（按仓库根，worktree 归到主仓库）。非交互运行不弹信任框：未信任时忽略项目 allow 并告警（抄 Claude Code / Gemini）。
- `additional_directories`：额外可读写目录，只扩展文件访问，不加载其中的配置。

示例：

```yaml
mode: auto_edit
allow:
  - Bash(npm run test *)
  - Bash(uv run pytest *)
ask:
  - Bash(docker *)
deny:
  - Read(./secrets/**)
additional_directories:
  - ~/shared/fixtures
```

## 9. 默认规则（configs/permissions.default.yaml）

**deny**（任何模式）：
- 密钥文件：`Read(**/.env)`、`Read(**/.env.*)`（`!.env.example`、`!.env.sample` 排除）、`Read(~/.ssh/**)`、`Read(~/.aws/**)`、`Read(~/.config/gcloud/**)`、`Read(~/.docker/config.json)`、`Read(~/.git-credentials)`、`Read(~/.npmrc)`、`Read(~/.pypirc)`、`Read(**/*.pem)`、`Read(**/*.key)`、`Read(**/id_rsa*)`、`Read(**/id_ed25519*)`、`Read(~/.triwitness/**)`（账本、令牌；`/runs/` 由 harness 自己写，不经工具）。
- 提权与系统：`Bash(sudo *)`、`Bash(su *)`、`Bash(doas *)`、`Bash(runas *)`、`Bash(mkfs*)`、`Bash(dd *)`、`Bash(shutdown *)`、`Bash(reboot*)`、`Bash(format *)`、`Bash(diskpart*)`、`Bash(reg *)`、`Bash(bcdedit*)`、`PowerShell(Set-ExecutionPolicy *)`、`PowerShell(Format-Volume *)`。
- 管道执行远程脚本：`Bash(* | sh)`、`Bash(* | bash)`、`Bash(* | sh *)`、`Bash(* | bash *)`、`PowerShell(* | Invoke-Expression*)`、`PowerShell(iex *)`。
- 破坏性删除：`Bash(rm -rf /*)`、`Bash(rm -rf ~*)`、`Bash(rm -rf /)`、`Bash(rm -rf $HOME*)`（工作区外的 `rm` 走 Edit 外部路径 → ask）。
- 发布与强推：`Bash(git push --force*)`、`Bash(git push * --force*)`、`Bash(git push -f*)`、`Bash(git push * -f*)`、`Bash(npm publish*)`、`Bash(pnpm publish*)`、`Bash(yarn publish*)`、`Bash(twine upload*)`、`Bash(uv publish*)`、`Bash(cargo publish*)`。
- 改全局配置：`Bash(git config --global *)`、`Bash(git config --system *)`。

**ask**：
- `Bash(git push *)`、`Bash(git reset --hard*)`、`Bash(git clean *)`、`Bash(git checkout -- *)`、`Bash(git rebase *)`、`Bash(git branch -D *)`。
- 网络：`Bash(curl *)`、`Bash(wget *)`、`Bash(pip install *)`、`Bash(uv add *)`、`Bash(uv pip install *)`、`Bash(npm install *)`、`Bash(npm i *)`、`Bash(pnpm add *)`、`Bash(yarn add *)`、`Bash(git clone *)`、`Bash(git fetch *)`、`Bash(git pull *)`、`PowerShell(Invoke-WebRequest *)`、`PowerShell(Invoke-RestMethod *)`、`Fetch`。
- 删除：`Bash(rm *)`、`Bash(rmdir *)`、`PowerShell(Remove-Item *)`（`none` 后端；docker 后端默认 allow，因为在容器里）。
- `Bash(docker *)`、`Bash(kill *)`、`Bash(pkill *)`、`PowerShell(Stop-Process *)`、`Bash(chmod -R *)`、`Bash(chown *)`。
- 执行字符串：`Bash(sh -c *)`、`Bash(bash -c *)`、`Bash(eval *)`、`Bash(python -c *)`、`Bash(node -e *)`。

**allow**（内置只读集，不可配置，但可被 ask/deny 收紧）：`ls`、`cat`、`head`、`tail`、`wc`、`pwd`、`echo`、`which`、`diff`、`stat`、`du`、`file`（不带 `-m`/`-f`）、`rg`、`grep`、`find`（不带 `-exec`/`-delete`）、`tree`、`git status|log|diff|show|branch --list|rev-parse|ls-files|blame`、`cd`（目标在工作区内）。

## 10. 审计日志

- 每次判定（allow / ask / deny）追加一行到 `~/.triwitness/audit/permissions-<YYYYMM>.jsonl`：`ts`（带时区）、`run_id`、`task_id`、`backend`、`mode`、`interactive`、`category`、`action`（脱敏、≤2000 字）、`decision`、`rule`、`rule_source`、`by`、`request_id`。
- 同时：`tool_call.permission` / `permission_rule` 写入轨迹；ask 另有 `approval_*` 事件。
- 脱敏复用 spec 005 §5.5 的规则（`sk-`、`ghp_`、`Bearer` 等）。
- 设置页“审计”标签按任务过滤显示；`tw audit --since 7d` 导出。

## 11. eval 模式差异

- 后端强制 `docker`；`none` 后端拒绝运行 eval（开发者可用 `--allow-unsandboxed-eval`，结果标记 `unsandboxed=true`，不计入报告和 Leaderboard）。
- `interactive = false`：ask → deny，写 `approval_resolved(by="policy")`，模型收到“该操作在评测中被禁止”的工具结果。
- 只读取 default 层 + 评测配置（`configs/runs/*.yaml` 中的 `permissions:`）；**忽略** user / project / local 层，保证可复现；有效规则集的哈希写入 `config_hash`。

## 12. 接口

```python
Decision = Literal["allow", "ask", "deny"]


class Rule(BaseModel):
    raw: str  # "Bash(git push *)"
    category: Literal["Read", "Edit", "Bash", "PowerShell", "Fetch", "Mcp"]
    pattern: str | None
    kind: Decision
    source: Literal["default", "user", "project", "local", "session", "managed"]


class Action(BaseModel):
    category: ...  # 同上
    raw: str  # 原始命令 / 路径
    cwd: Path
    tool: str  # 具体工具名


class Verdict(BaseModel):
    decision: Decision
    rule: Rule | None
    reason: str
    sub_actions: list[Action] = []  # 复合命令拆分结果


class PermissionEngine:
    def __init__(self, policy: EffectivePolicy, workspace: Workspace, backend: SandboxBackendName): ...
    def check(self, action: Action) -> Verdict: ...  # 纯函数，无 I/O（除路径 resolve）
    def remember(self, action: Action, scope: Literal["session", "always"]) -> Rule | None: ...


def load_policy(repo: Path, *, interactive: bool, eval_mode: bool, cli: SessionOverrides) -> EffectivePolicy: ...
def parse_rule(raw: str, kind: Decision, source: str) -> Rule: ...  # 语法错误 → ConfigError，带位置
```

## 13. 验收标准

- [ ] AC1：`Bash(npm run *)` allow + `Bash(git push *)` deny：`npm run build` allow；`npm run build && git push origin x` deny；`timeout 30 npm run build` allow；`FOO=1 git push` deny。
- [ ] AC2：`Bash(ls *)` 不匹配 `lsof`；`Bash(ls *)` 匹配 `ls`；`Bash(git:*)` ≡ `Bash(git *)`。
- [ ] AC3：`Read(.env)` deny 阻止 `read_file("sub/.env")`、`cat sub/.env`、`grep x < .env`、经符号链接 / junction 指向 `.env` 的读取；`Read(!.env.example)` 放行 `.env.example`。
- [ ] AC4：Windows 路径：`C:\Repo\.ENV`、`c:/repo/.env`、`\\?\C:\Repo\.env`、8.3 短名都被 AC3 的规则拒绝（Windows CI 或纯函数模拟）；`\\server\share\x` → ask；`a.txt:secret` → deny。
- [ ] AC5：user 层 allow + project 层 deny → deny；project allow 在未信任仓库时不生效、信任后生效；local 被 git 跟踪时也需信任。
- [ ] AC6：`interactive=false` 时 ask → deny，且轨迹中有 `approval_resolved(by="policy")`。
- [ ] AC7：`none` 后端配置 `full_access` → ConfigError；项目文件中的 `mode: full_access` 被忽略并告警。
- [ ] AC8：`auto_edit` + none 后端：worktree 内 `edit_file` allow；对 `.git/config` 的 Edit deny；对工作区外文件的 Edit ask。
- [ ] AC9：“总是允许”写入 `permissions.local.yaml`，复合命令最多拆 5 条；重新加载后同命令 allow。
- [ ] AC10：审计日志每次判定一行，注入假 `sk-` 密钥后日志中查不到。
- [ ] AC11：`sh -c 'rm -rf /'`、`bash -c ...` → ask（不被前缀 allow 放行）；引号不闭合 → ask。

## 14. 测试计划

- 纯函数单测（不需要 Docker / Windows）：规则解析、命令拆分、包装剥离、路径规范化（Windows 路径用 `PureWindowsPath` 模拟）、层级合并、模式表（参数化，覆盖 §6 每一格）。
- 属性测试（hypothesis，可选）：任意 allow 规则都不能放行命中 deny 的命令。
- 集成：本机后端 + 引擎 + 事件（FakeRouter 驱动），断言事件序列。

## 15. 开放问题

- `auto_edit` 下是否默认允许 `npm install` 等装依赖（便利 vs 供应链风险）？当前：ask。
- 是否提供 Cursor 式“删除保护 / 工作区外保护”的独立开关？当前：用规则表达，设置页做成类别开关（Cline 风格）映射到规则。
- 后台任务审批超时默认值（当前：不超时，任务停在 needs_human）。

## 16. 变更记录

- 2026-10-10：初稿（ADR-0005）。`tw-events/1` 已加入 `approval_requested` / `approval_resolved` 与可选字段（schema 桩，引擎未实现）。
