# 桌面 UI 进度

> 不按日历排期，做完一项记一项。

## 0.3.2-preview · 去掉预算控制 + 断点续跑 + 开 PR + 诊断包（2993407 … ，未发布、未打包）

- **金额一致**（2993407 / 18aaf7e）：结论卡显示实付（缓存命中 ¥0），名义价在悬停提示；审核模型花费记 `reviewer` 类别。
- **去掉预算控制**（Eva 19:14；d4377ac / 5b9faf4 / 30b784c）：只保留用量记录、金额 / 缓存显示、非金钱安全上限和模型白名单；设置“预算”→ 只读“用量”页，状态栏显示累计已花；旧偏好 `maxCost` / `allowPeak` 读取时丢弃并回写。截图 `usage-hello.jpg`、`usage-settings.jpg`。
- **断点续跑**（a03bb7c）：停止 / 失败 / 中断的任务轮显示「继续」。截图 `resume-stopped.jpg`、`resume-done.jpg`。
- **开 PR**（9976327 / 338edfe / 4a729fc）：结论卡「开 PR」→ 审批卡（仓库 / 分支→目标 / 标题 / 改动 / 授权方式）→ 确认才推送并开 PR；令牌存凭据库 `github-token`，只注入 `tw pr`；连接器页有令牌行 + 最小权限指引。真实验收：临时私有仓库 `Akarin7784/tw-pr-e2e-20261011`，本机已登录 gh 授权，开出 PR #1，重复调用返回同一个 PR（`created=false`）；之后关闭 PR、删远端分支。**仓库没能删除**：gh 登录没有 `delete_repo` 权限（需 Eva 运行 `gh auth refresh -h github.com -s delete_repo` 后 `gh repo delete Akarin7784/tw-pr-e2e-20261011 --yes`，或网页上删）。令牌（REST）路径只有模拟测试（不从 gh 提取令牌）。截图 `pr-card.jpg`、`pr-opened.jpg`。
- **诊断包**（2364489 / 424d2af）：关于页「导出诊断包」、结论卡「诊断包」；`tw diag export`。真实验收：95 个文件、116 KB，zip 里查不到本机的 DeepSeek 密钥。截图 `diag-export.jpg`。
- **Docker**：box 上用 fuse-overlayfs 重装，`pytest -m integration tests/integration` 两次全过（含 `tw eval` 流水线用例），之后 `docker system prune -af`（回收 4.46 GB，磁盘 12%）。
- **真实 key 花费（2026-10-11，deepseek-flash，高峰调用 0）**：金额一致 ¥0.0146；断点续跑 ¥0.0507；去掉预算控制 ¥0.0008；开 PR ¥0.0210；诊断包 ¥0.0007；合计 ¥0.0878（本机账本累计 ¥0.1640）。
- **W4 多角色编排（核心，00a1a22；spec 010 初稿待 Eva 审）**：`tw run --harness orchestrated-1m` = Planner → 计划确认 → 复现 → Executor → 验证 → Reviewer（同厂商异构变体，可选共识）→ 整理结果；评审 blocker 有上限地返工；任务与事件写 `tw.db`（`tw tasks`）。桌面端不用改：计划确认复用审批卡（tool = Plan），评审走已有的 review 事件。默认 harness 仍是 long-context-1m（是否切换见 spec 010 §11 Q4）。
- **W4 真实 key 实测（2026-10-11 21:09–21:16 UTC+8，周日空闲价，deepseek-flash，高峰调用 0）**：5 次运行合计 ¥0.4001；local 规则放行 python 后 add 修复 done（复现 + Verifier pass + 评审通过，¥0.0598）；`--jsonl` 计划审批 → 双评审共识 done（¥0.0997）。暴露终端 `tw run` 无审批通道时测试命令全被拒（spec 010 §11 Q5）。
- **W4 第二批（Eva 21:35 / 21:36 决定落地）**：终端 `tw run` TTY 下 y/N 审批（Q5）；计划确认停住时保存续跑点、`--resume` 沿用原计划（Q6）；评测权限完全放开（计划含 L3 自动批准、命令不审批，只限评测）；依赖 / CI 配置改动必须人工确认（W4-10，默认开，待审）；`ask_human` 工具；跨厂商评审假模型 e2e（W4-08）。桌面端：依赖 / CI 确认与 ask_human 复用现有审批卡（tool = 原工具 / AskHuman），能批准 / 拒绝；**还不能输入文字回答**（审批卡没有附言框，ask_human 只能得到“是 / 否”），留给 UI-13。
- **第二批真实 key 实测（2026-10-11 21:41–21:46 UTC+8，周日空闲价，deepseek-flash，高峰调用 0）**：4 次运行合计 ¥0.1013——计划确认 needs_human → `--resume` 沿用原计划 → done（¥0.0065 + ¥0.053）；伪终端里计划 y/N → done（¥0.0303）；一次测试驱动问题作废（约 ¥0.01）。
- **W4 第三批（核心，桌面端不用改）**：W4-09 事件日志重放续跑 + 工具预写日志 + 对外副作用幂等键（b482cdd，`tw pr open` 重复执行复用同一个 PR）；spec 011 初稿（W4-02，待 Eva 审）；W4-13 评审者注入缺陷集 40 题；W4-14 消融脚本 + Windows 一键脚本（全量 160 次评审交给 Eva 本机跑，box 只做了冒烟）。默认权限模式仍是 auto_review（等 Eva 决定）。
- **第三批真实 key 花费（2026-10-11 21:5x–22:25 UTC+8，周日空闲价，deepseek-flash，高峰调用 0）**：W4-09 崩溃续跑 ¥0.0178；消融冒烟 4 题 × 4 臂 ¥0.7671（box 账本）+ 容器端到端 1 次 ¥0.0060（容器账本）；合计 ¥0.7909。
- **W5 第一批（核心，桌面端暂不改；GitHub App 暂缓）**：`tw run --open-pr` 接上 PR_OPENED / CI_WATCH（按风险：L0 / L1 确认、L2 Draft、L3 不开；CI 失败把精简日志交给 Executor 返工，最多 2 轮；推送与开 PR 带幂等键）；spec 012 草稿（待 Eva 审）。桌面端仍走 0.3.2 的“审批后开 PR”，确认卡复用审批卡（tool = OpenPR），接入编排器发布流程放到 W6。另有 `eval/ablation.py`、OFAT 消融脚本 + Windows 一键脚本（`scripts/windows/run-ofat-ablation.ps1`）、评测防作弊加固与 `task_factory.py audit`。
- **W5 第二批（桌面端不改）**：CI 修复返工后先重跑验证器再推送（验证不过不推送）；L0 仍确认；不建新仓库。扩充任务集 ext（加固构建，冻结套件 `ext.yaml`，dev / test 不动）。Harbor 集成：`TriWitnessAgent` + `HarborSandbox`，TB2 10 题子集脚本 `scripts/windows/run-harbor-tb2.ps1`（WSL2，待 Eva 本机跑）。
- **W5 第二批真实 key 花费（2026-10-11 23:3x UTC+8，周日空闲价，deepseek-flash，高峰调用 0）**：Harbor 实测 1 题 ¥0.0126（box 账本，类别 harbor-external）；其余离线。
- **W5 第一批真实 key 花费（2026-10-11 23:0x UTC+8，周日空闲价，deepseek-flash，高峰调用 0）**：OFAT 容器冒烟 1 题 ¥0.0083（容器账本）；其余全部离线测试。清掉 1.4 GB 的 `tw-reviewer-ablation` 镜像等（磁盘 12%）。
- **延后（Eva 21:36）**：“模型自动审批”（auto_review）权限模式的专门实测，本轮不做。
- 按 Eva 19:39：**本版先不打包**，不取 CI 安装包。

## 0.3.1-preview · 对话轮 + 正式版移除演示模式（7482a05 / 07e3c68 / …）

- 起因：Eva 在 v0.3 里发“你好”，得到的是演示脚本修 verses.py 的全过程——每条消息都被当成编码任务，演示模式又无视输入。
- **对话轮**（核心 `harness/chat.py`、`prompts/chat.md` v1）：每条消息先一次对话调用（带 `start_repo_work{goal}` 工具）。不调工具 → 直接回复，`turn_finished.kind=chat`，没有 finish / 验证 / 证据 / 补丁；调工具且已选仓库 → 同一个 run、同一个 recorder 接着跑 `run_local`；没选仓库 → 不再调模型，直接请用户选仓库。没有额外的分类调用。
- **多轮**：`tw run --jsonl --parent-run <run_id>`；每个 run 目录写 `turn.json`（parent / user / assistant / kind），沿链取最近 20 轮。前端 `chats.threads[根]` 记各轮，之前各轮只读显示在上面（读盘回放折叠），重试 / 编辑只作用于最后一轮（同一个 parent 分叉）。
- **界面**：直接回复是一条普通助手消息（无结果卡 / 作品卡），状态签“已回复”；输入框跟进时提示“回复…”；仓库选择在会话里一直可用、可空。
- **正式版移除演示模式**：PyInstaller 排除 `bridge.demo` / `harness.testing` / `verify.testing` / `llm.fake` 并在构建时用 `pyi-archive_viewer` 校验；`tw.exe run --demo` → “正式版不含演示模式”。Rust 发行构建只有 live（调试构建才放行 demo / replay）、仓库可空、`--parent-run` 只放行合法 run_id、没密钥返回 `missing_api_key`。前端 fixture / mock / 压测来源只在 `import.meta.env.DEV`，正式版默认打开新会话；去掉“运行方式”设置和全部「演示」文案；`npm run check:bundle` 扫正式版前端包（CI desktop job + package-windows）。
- **密钥引导**：凭据库没有密钥时首次打开弹“连接 DeepSeek”（链接 platform.deepseek.com/api_keys），没密钥就发送也弹，保存后自动把那条消息发出去。
- **测试**：本机 OpenAI 兼容模拟服务 `packaging/mock_llm.py` + `TW_LLM_BASE_URL_OVERRIDE`（只允许 127.0.0.1 / localhost，用到时 stderr 告警）。`smoke_core.py` 改为：拒绝 `--demo`、「你好」直接回复（无 task_started / tool_call / patch）、「我刚才说了什么」复述、未选仓库请选、verses 小任务（询问模式 + 自动批准）done / pass、所有请求带鉴权且是 SSE、账本有记录——Linux 打包核心本机全过。Python 单测 +15（`tests/unit/harness/test_chat.py`），vitest +6（`chatTurn.test.ts`），e2e `tools/shoot-v031.mjs`（正式版前端包 + `vite preview` 开发桥 + 打包核心 + 模拟服务，13 项全过）。截图 `docs/images/v0.3.1/`。
- **真实 key 验收（2026-10-11 18:33–18:40 UTC+8，deepseek-flash，全部经账本，高峰调用 0 次）**：正式版前端包（`vite preview` + 开发桥）+ Linux 打包核心 + 真实适配器。
  - 「你好」+ 多轮跟进：¥0.0010（重拍时命中本地 llm-cache，¥0）。
  - verses 询问模式首跑：¥0.0212，结论“复验未过”——暴露 `submit_repro` 把 `python: command not found` 当成复现（已修，见 CHANGELOG）。
  - 修复后询问模式：¥0.0129 / ¥0.0161（两次），复验通过、风险 L2（无沙箱，干净环境未验证）。
  - 自动审核模式：¥0.0145 / ¥0.0105（两次），复验通过；审核模型自动批准 5 次，工作区外路径 1 次升级给人。
  - 合计 ¥0.0762。结论卡上的金额（¥0.017–0.023）含命中本地缓存的调用的名义价，高于账本实付。
  - 截图（真实输出）：`hello.jpg`、`followup.jpg`、`task-ask.jpg`、`task-ask-approval.jpg`、`task-auto_review.jpg`、`task-auto_review-approval.jpg`。
- **还没做**：用真实 DeepSeek 密钥从 App 发起的运行（box 上没有项目密钥）。

## 0.3.0-preview · 公开预览（84244a0 … d8f800e）

- **安装包自带核心**：PyInstaller onedir（`tw.exe` + `_internal/`）作为 Tauri 资源装到 `<安装目录>\core\`；Rust `bundled_core()` 优先用它，再退回 TW_CORE / PATH / `python -m`。选 onedir 不选 onefile：onefile 每次启动都要把 ~40 MB 解压到临时目录（桌面端每个任务、每次查规则 / 账本都会起一次核心，冷启动多 1–3 秒，杀毒软件还会反复扫），onedir 启动约 0.1 s（Linux 实测），以后也便于逐个文件签名。
- 构建：`.github/workflows/package-windows.yml`（windows-latest；PyInstaller 不能交叉编译）。冒烟：打包后的 `tw.exe` 跑 `--version`、`budget --json`、两次 `run --demo --jsonl`（模型自动审批 / 询问 + 批准），再静默安装、对安装目录里的核心再跑一遍。`tauri.core.conf.json` 只在这个 job 里叠加资源，Linux 上 cargo-xwin 的无核心构建不受影响。
- 预算页 / 状态栏余额读真实账本（`tw budget --json`，白名单在 Rust / TS / 开发桥三处一致）；没连上核心显示“—”。删掉 `src/data/budget.ts` 里的假账本。
- 如实表述交付：结论卡写明“已生成本地分支和 PR 说明；没有推送，也没有在 GitHub 上创建 PR”，按钮是“复制 PR 说明 / 打开运行目录”（tauri-plugin-opener `revealItemInDir`）；状态名改为“待确认交付 / 分支已就绪”。
- 关于 → 检查更新：打开 https://github.com/Akarin7784/triwitness/releases 。
- 版本号集中在 `src/lib/version.ts`；README 截图 `docs/images/v0.3/`（`tools/shoot-v03.mjs`，9 项检查全过，¥0）。
- **安装包（CI 构建，5ec99cd）**：`TriWitness_0.3.0-preview_x64-setup.exe`，27,583,653 字节 ≈ 26.3 MiB（内置核心 onedir 37.1 MiB 未压缩、762 个文件；0.2.1 无核心版 9.96 MiB），sha256 `feb134e48351775f3032e295c8a9446410327a1205944ddfb5541f6c80ab2de1`。artifact：https://github.com/Akarin7784/triwitness/actions/runs/38128418471/artifacts/11698880903 （保留到 2026-10-25）。CI 上静默安装后，安装目录里的核心在 Git Bash 和 PowerShell 两种环境下都跑通了演示往返。
- 修复（5ec99cd）：打包核心在 PowerShell / 桌面端环境下卡在“找 Git Bash”——`git --exec-path` 经 `Git\cmd\git.exe` 启动器超时后，孙进程握着 stdout 管道，`subprocess.run` 在 Windows 上等读线程永远不返回。改为先从 PATH 上的 git 路径 / Program Files 推出 bash.exe，最后才起 git，且用文件输出 + stdin 为空 + 杀进程树（`run_quiet`）。
- 发布：`release.yml`（推 `v*` 标签 → 构建 → CHANGELOG 取说明 → 草稿 Release 附安装包和 sha256，不自动发布）。**尚未打标签。**

## 0.2.1 · 性能 + Eva 0.2.0 真机反馈（a2de105 / 5ad5617 / 9638d53）

- 性能（a2de105）：事件按帧批量提交 + 增量折叠、长回合虚拟化、content-visibility、增量 Markdown、懒加载分包、字体子集。500 轮推流 16.2 → 59.5 fps，long task 26.4 s → 0.16 s，主 JS 971 → 177 KB。详见 `docs/research/native-vs-web-ui.md` §6
- 真机反馈（5ad5617）：
  - BUG1 提示框不再盖住已打开的菜单
  - BUG2 仓库选择器：原生文件夹对话框 + 最近仓库 + 手动输入；仓库签不换行
  - BUG3 已有空会话时“新会话”直接聚焦它
  - BUG4 “搜索”打开 Ctrl+K 面板，“会话”打开会话页（排序 / 搜索 / 批量删除）
  - BUG5 全局不换行规则；shoot-review 增加 100/125/150% × 中英文换行检查
  - SUGG1 权限四种模式（只读 / 询问 / 模型自动审批 / 完全访问），沙箱独立；旧值自动迁移
  - SUGG2 侧栏行高固定
  - SUGG3 纸书配色（浅色 + 夜读深色，对比度全部 ≥ AA）
  - before / after 截图：`docs/feedback-2026-10-11/`

**安装包 0.2.1**：`release/TriWitness_0.2.1_x64-setup.exe`（10,440,991 字节 ≈ 9.96 MiB，NSIS，未签名；0.2.0 是 12.74 MiB，变小主要因为字体子集）
- sha256 `94f13100a012a52c28cd66dc485e40fd4daa1737bc69c3b0c3b3ad5809964cd3`
- 构建方式同 `docs/WINDOWS_BUILD.md` 方式 B（cargo-xwin，`--bundles nsis`）

## UI-21 · Claude 交互对齐（已完成：三轮 + 界面审查）

原则（Eva）：操作方式与 Claude Desktop 一一对应，不缺也不多；差异只放在审美和复验功能上。没做的功能也放真入口，点了提示“即将推出”。逐项状态见 `docs/claude-parity.md`。

> 提交名更正：核心流式提交 a3f9c7b 和桌面端第 1 轮 710dbf5 的提交说明误写成 “UI-20”，它们属于 **UI-21**；UI-20 是勇士模式 UI。历史不改写，只在这里和任务表里更正。

### 第 1 轮：输入框、模型选择、流式消息（a3f9c7b / 710dbf5）

**核心**
- tw-events/1 新增 `model_delta` / `reasoning_delta`（call_id、index、text），属于增量字段，v 仍为 1
- `model_call` / `tool_call` 带 call_id；`tool_call` 带参数和输出预览（已脱敏）
- DeepSeek 流式：`stream=true` 解析 SSE，再拼回非流式形状，所以回放缓存的 key 不变；已经输出一部分后不重试。只用合成 SSE 夹具测试，没有真实调用
- 回放命中时，把缓存回复切成 delta 输出；DeltaWriter 按 50ms / 48 字合并
- 只在 `tw run --jsonl`（桌面端）时写 delta，eval 不写
- `--model` / `--thinking`：关 / 低 / 中 / 高 → thinking + reasoning_effort（low / high / max），只接受 deepseek-flash

**桌面端**
- 输入框：自动增高，Enter 发送，Shift+Enter 换行，输入法安全，每个会话单独保存草稿；+ 菜单（各项为占位）、仓库签、模型选择、发送 / 停止 / 语音
- 模型选择：只有 DeepSeek Flash 可选；通义千问、智谱 GLM 灰显“稍后”；不出现 v4-pro。思考强度是子菜单（照 Claude 的 Effort）
- 流式消息：新字淡入，柔和光标；Markdown（代码块带复制）；思考块折叠为“思考了 N 秒”；工具调用是可展开的紧凑行
- 滚动贴底；向上滚时暂停，并出现“回到底部”

### 第 3 轮：剩余对齐功能 + 中英文 + 界面审查（bfaa2a6 / 0ed5355 / f150ea2 / c514a28 / 6f0c226 / 7ee763e / ae187f3）

**核心**
- `tw run --attach PATH`（可重复，最多 20 个）：文本内联进任务（单个 2 万字、总共 6 万字封顶），图片和二进制只列文件名，原件存进 run_dir/attachments
- `tw run --guidance-file`：个人资料、风格、项目说明（8K 封顶）
- `mode_changed` 事件：会话模式不同于基础模式时发出，任务结束发 auto_revert；CI 环境拒绝 unrestricted
- `tw doctor --json`：docker / wsl / winget 状态；Docker 必须真有版本号才算 ok，权限不足时报“没有权限”
- `tw sandbox install docker|wsl --plan|--yes`：UAC 提权，不带 --yes 就拒绝执行
- `tw permissions list / validate / add [--replace] / remove`：用户层或本仓库层，写入前用 parse_rule 校验

**桌面端**
- 附件：+ 菜单、拖放（放置层）、粘贴、Ctrl+U；附件签可预览、移除；图片提示“当前模型只读文字”
- 项目：新建、重命名、删除；项目说明；知识文件；侧栏按项目分组；会话 … 菜单和标题下拉里可“加入项目”
- 作品栏：代码 / Markdown / diff / pr.md；版本切换、复制、下载；可拖动调宽，宽度会记住；另有作品页
- 分享：复制为 Markdown、导出 .md、导出 PDF（系统打印）。只在本机，菜单里写明
- 风格：标准 / 简洁 / 详细 / 正式 + 自定义；个人资料和风格都交给模型
- 规则编辑器（核心实时校验）；审批卡“总是”会提示已写入规则，并能在设置里看到
- UI-19 沙箱：检测卡片 + 一键安装（先确认，经 UAC 提权，有进度显示）
- 勇士横幅：由核心 mode_changed 驱动
- 隐私：导出本机数据、清除会话记录；关于：开源许可
- 中英文：`t('中文')` 查英文表，共 432 条；`tools/i18n-wrap.mjs --check` 防止漏包
- Rust：files.rs，含 attach_save、save_download、core_read_artifact、core_tool 白名单

**验证**
- vitest 90 项
- shoot-ui21c 46 项全过；shoot-ui21、test-guards 全过（右键空白点改为动态寻找）
- 界面审查：浅色 / 深色 / 英文 / 减少动态效果，139 张截图，报告见 `docs/ui-review-2026-10-11.md`

**安装包 0.2.0**：`release/TriWitness_0.2.0_x64-setup.exe`（13,360,733 字节 ≈ 12.74 MiB，NSIS，未签名）
- sha256 `857a0a8659d4ae9d50793990ae5c3efd8cc2b982603d91a9ddbf55d1805a7266`
- 构建方式同 `docs/WINDOWS_BUILD.md` 方式 B：cargo-xwin 交叉编译，`--bundles nsis`

### 第 2 轮：设置、侧栏、消息操作、快捷键（b3d20d0 / f35b741）

**设置**（Ctrl+,，左侧分区导航，改动即时保存）
- 常规：主题浅色 / 跟随系统 / 深色（深色是“灯下读书”配色，只覆盖 CSS 变量）；对话字体宋体 / 黑体 / 系统；字号四档，只作用于对话区；语言只有简体中文，English 灰显
- 个人资料：称呼、偏好，只存在本机（还没注入提示词）
- 模型：默认模型、思考强度、运行方式；**API 密钥**存系统凭据库（Rust `keyring`：Windows 凭据管理器 / macOS 钥匙串 / Linux 密钥环）。前端只能写入、清除、查询是否已设置，拿不到明文；真实模式启动核心时把密钥注入子进程的 `DEEPSEEK_API_KEY`。浏览器预览里显示“仅桌面应用”
- 预算：单任务上限 ¥0.10–1.00，只能调低；“高峰也允许真实调用”开关只影响真实模式；高峰闸门图；账本仍是 mock
- 权限：plan / ask / auto_edit / auto / full_access（无沙箱时禁选）；红色的“无限制（勇士模式）”需要两步确认（勾选 + 输入“我了解风险”），只对下一个任务生效，从不落盘，任务运行时对话区顶部有常驻红色横幅；内置规则只读列表（拒绝 54 / 询问 38），“添加规则”为占位
- 沙箱：后端 自动 / Docker / 本机；一键安装 Docker、启用 WSL2 为占位（UI-19）
- 连接器、隐私为占位；关于：版本、快捷键入口

**设置接到核心**：每次起任务，把设置作为本次任务的选择传给 `tw run`
- 参数：`--backend`、`--max-cost`、`--permission-mode`、`--confirm-unrestricted`、`--allow-peak`
- 白名单三处一致：Rust `choice_args`、`src/bridge/choices.ts`（开发桥和前端共用）、核心 CLI 再校验一次
- 核心侧的约束：`--max-cost` 只能调低，不超过 `Budget.for_run()`；权限模式走 session 层；勇士模式只在交互运行（`--jsonl`）中、带确认短语时才开启，scope=task；`load_policy` 仍然做最终检查

**侧栏**
- 新会话、搜索（Ctrl+K 面板：方向键、回车）、会话、项目（占位）、作品（占位）
- 星标分组和近期分组
- 每个会话的 … 菜单：星标、重命名、加入项目（占位）、删除。重命名和删除都有对话框；删除时会停掉仍在运行的任务
- 收起侧栏（Ctrl+Shift+S）：变成图标窄栏，宽度用弹簧过渡
- 底部用户菜单：设置、快捷键、帮助（占位）、关于

**消息操作**
- 重试、编辑后重发是真功能：在同一会话里起一个新任务，作为新版本，用 ‹ n / m › 切换
  - 编辑产生的版本显示在用户消息下，重试产生的显示在回复操作条上，与 Claude 一致
  - 版本不会单独出现在侧栏
- 赞 / 踩可以附一段文字，只存在本机；再点一次取消

**快捷键**：照 Claude 的整套做，Ctrl+/ 打开快捷键列表
- 会话：新会话 Ctrl+Shift+O、搜索 Ctrl+K、收起侧栏 Ctrl+Shift+S、下 / 上一个会话 Ctrl+Shift+] / [
- 对话：停止 Esc、聚焦输入框 Shift+Esc、复制最后一条回复 Ctrl+Shift+C、添加文件 Ctrl+U（占位）
- 菜单：设置 Ctrl+,、模型菜单 Ctrl+Shift+I、思考强度 Ctrl+Shift+E
- macOS 上显示 ⌘ ⇧
- 防护层改成只取消浏览器默认动作、不拦截冒泡，所以 Ctrl+U、Ctrl+Shift+C/I 能用作应用快捷键（release 版里 WebView2 的浏览器快捷键在原生层已关）

**顶部**：会话标题下拉（星标 / 重命名 / 加入项目（占位）/ 删除）；分享按钮下的复制链接、导出 Markdown、导出 PDF 都是占位。+ 菜单新增“风格”（占位）

**动画**：对话框、菜单、侧栏宽度、分区切换、选中滑块、开关、单选点都用弹簧；整体包在 `MotionConfig reducedMotion="user"` 里

**和 UI-09 的偏差**（第 1 轮起）
- 对话区实时显示，不跟笔；右侧书写推流和角色点仍跟笔
- 切换版本后，右侧推流从头写

**验证**
- vitest 68 项通过。新增 choices（白名单）、chats（重命名 / 星标 / 版本 / 反馈）、shortcuts（全表）、rules（解析真实规则文件）测试，prefs 测试补了坏值回退和勇士模式不落盘
- lint / check:events / build 通过
- `cargo xwin check --tests` 通过（新增 `secrets.rs` 和 Choices 白名单测试；本机缺 webkit，Rust 单测只做了编译检查）
- Python 侧：`tests/unit/cli/test_run_overrides.py`；bridge 子进程测试加了一组带覆盖参数的运行；ruff / format / pyright / pytest 全部通过
- e2e 全部通过：
  - `tools/shoot-ui21.mjs`：设置九个分区、勇士模式两步确认、深色主题、Ctrl+/ 和 Ctrl+K、侧栏星标 / 重命名 / 删除 / 收起、标题下拉、分享占位、踩、复制最后一条、重试 2/2、单任务上限 ¥0.50 传到核心、编辑后重发 3/3、切回 2/3、其余快捷键；页面没有报错
  - `shoot-chat.mjs` 19/19，`shoot-live.mjs` 18/18
- `tools/test-guards.mjs`：第 1 轮之前就有一项失败（“右键 UI 空白处无菜单”，点击坐标落在了输入框上），其余通过；侧栏选择器已更新
- 截图（docs/）
  - 第 1 轮：`composer-model-picker.png`、`composer-plus-menu.png`、`thinking-streaming.png`、`streaming-mid-message.png`、`chat-tool-rows.png`、`chat-result.png`
  - 第 2 轮：`settings-general.png`、`settings-general-dark.png`、`settings-model.png`、`settings-budget.png`、`settings-permissions.png`、`settings-unrestricted-dialog.png`、`settings-sandbox.png`、`settings-about.png`、`sidebar-chat-menu.png`、`sidebar-collapsed.png`、`search-palette.png`、`shortcuts.png`、`title-menu.png`、`edit-message.png`、`version-nav.png`
- 全程 ¥0，没有重建安装包

**还没做**（占位或 todo，见对齐清单）
- 文件 / 图片附件、截图、网页搜索、深度研究、技能、连接器、插件、风格、语音
- 项目、作品（Artifacts）面板、分享 / 导出、Chat / Cowork
- 英文界面
- 用户自定义规则编辑
- Docker / WSL2 一键安装（UI-19）
- 个人资料注入提示词
- 勇士模式横幅改为由 `mode_changed` 事件驱动（UI-20 剩余部分）

## UI-10 · 桌面端驱动真实核心（已完成）

**通路**：新会话 → 输入框上方的仓库签（点开填路径；演示模式可留空，核心自动建示例仓库）→ 发送 → 后端拉起 `tw run --jsonl` → 实时 tw-events/1 进入原有推流、状态 / 费用 chip 和角色点 → 审批卡 → 结论卡。

**协议 tw-bridge/1**（`src/triwitness/bridge/stdio.py`，核心侧在 b49daa2）
- stdout 每行一个 JSON：tw-events/1 事件原样输出；带 `bridge` 键的是控制行，包括 `hello`（协议 / 模式）、`run`（run_id / run_dir）、`result`（终态 / 裁决 / 风险 / 费用 / 步数 / pr.md）、`error`、`ack`。stderr 只放人读日志
- stdin 收两种命令：`{"cmd":"approve","request_id","decision":"allow|deny","scope":"once|session|always"}` 和 `{"cmd":"cancel"}`
- 审批走权限系统原有的 ApprovalBroker，所以有界面审批时 `tw run` 不再一律拒绝复现命令
- 取消：核心收尾后发 `cancelled` 状态和 `task_finished(status=cancelled)`。Rust 侧 10 秒后仍未退出就强制结束进程

**桌面端**
- `src-tauri/src/core.rs` 提供五个命令：`core_start / core_send / core_cancel / core_read_run / core_alive`，输出通过事件 `tw://line`、`tw://exit` 推给前端
  - 核心命令按顺序找：`TW_CORE`（JSON 数组）→ `tw` → Windows 上 `py -3 -m triwitness` → `python -m triwitness` → `python3 -m triwitness`
  - 子进程设置 `PYTHONUTF8=1`；Windows 上不弹控制台窗口
- `src/bridge/`
  - `protocol.ts`：行解析和命令构造
  - `transport.ts`：Tauri 实现和开发桥实现
  - `liveTask.ts`：任务本身，实现 EventSource，同时维护审批 / 结果 / 退出快照
  - `liveStore.ts`：注册表；任务清单存在 localStorage，侧栏据此显示
- `vite.coreBridge.ts`：开发桥。只在 `npm run dev` 且 `TW_DEV_BRIDGE=1` 时启用，提供同一套 HTTP + SSE 接口，供浏览器预览、截图和 e2e 使用；正式构建不包含
- **审批卡**：四个选择，允许一次 / 本次任务 / 总是 / 拒绝。笔写到审批那一行时出现，此时状态签显示「待批」；结案后收起
- **结论卡**：裁决（复验通过 / 未过 / 证据不足）、风险等级、费用 / 步数、摘要、pr.md 前几行（可展开全文）。笔写完最后一行时出现
- **停止**：任务进行中，发送键变成停止键
- **续上**：刷新或重开界面后，若进程还在，读 `run_dir/trajectory.jsonl` 补齐，再接上实时流；若已结束，从记录回放全程，并用保存下来的结论重现结论卡
- **设置 · 运行方式**：演示 / 回放 / 真实，默认演示。真实模式走 `--live`（deepseek-flash），已接通，本轮未运行

**顺带修的三处（27b6cee）**
- 补丁侧回归超时：判为证据不足，不再判失败
- 薄证据：只有「自报风险」这一条时，不算证据
- 跑测试时设置 `PYTHONDONTWRITEBYTECODE=1`

**和任务卡的偏差**
- 「续上」只做到重新接上 / 回放，不支持从 checkpoint 继续已停止的任务
- 演示适配器是脚本化模型：费用 ¥0，不写账本；回放模式需要录好的模型回复

**验证**
- `npm test`：46 项通过。新增 protocol 和 liveTask 测试，其中 liveTask 用真实核心录下的 `__fixtures__/demo-run.jsonl` 做 e2e 回放：审批、结案、结论、跟笔折叠、幂等、续传
- `npm run lint` / `check:events` / `build` 通过
- `cargo xwin check --target x86_64-pc-windows-msvc`（含 `--tests`）通过
- Python 侧：`tests/unit/bridge/`，包括真实子进程 `python -m triwitness run --demo --jsonl`；ruff / pyright / pytest 全部通过
- `tools/shoot-live.mjs`：18/18 通过。流程为：起任务 → 推流 → 审批卡 → 允许 → 结论卡（复验通过 · 风险 L2 · ¥0.000）→ 再起一个并停止 → 刷新续上；页面没有报错
- 本轮没有重建 Windows 安装包

## UI-09 · 回放 tw-events/1 fixture（已完成）

**事件模型**
- `scripts/gen-event-types.mjs` 用 json-schema-to-typescript 把 `schemas/tw-events-1.schema.json` 编译成 `src/data/tw-events.gen.ts`；`npm run check:events` 检查生成文件是否过期（已接入 CI）
- `events.ts`：逐行解析，并校验 v=1、seq、ts、id 和 payload；坏行跳过，按 seq 去重排序；未知 kind 保留为 UnknownEvent，不渲染、不崩
- `sources/`：`EventSource` 接口（subscribe / afterSeq / close）。`FixtureSource` 按 ts 间隔回放，支持倍速、空档上限和 afterSeq 续传；`MockSource` 把旧演示日志包装成事件，复用同一条路径
- `useEventFeed` 取代 `useMockFeed`（已删）

**映射（event-protocol §3）**
- 推流：优先显示 `payload.display`，没有时按 kind 拼出一行；角色取 `role_hint`，其次 `role`，都没有时归为系统
- 推流行的样式：状态切换显示为居中的章节标题；checkpoint 显示为琥珀色细分隔；失败的工具调用和复验失败用赭红；高峰时段调用和循环警告用琥珀；收尾行用衬线字
- 角色点：亮起当前状态对应的角色（规划 / 执行 / 验证 / 评审）
- 状态 chip：显示中文状态，配色点按阶段区分（进行 / 等待 / 完成 / 失败 / 预算耗尽 / 取消）
- 费用 chip：显示 `¥x.xxx` 和一条迷你预算条；悬停显示命中率、上限和高峰调用次数。超过 80% 变琥珀，超出预算或预算耗尽变赭红
- **跟笔同步**：状态、费用和对话只推进到笔尖已经写到的那一行；暂停时一起冻结
- 对话：task_started 显示为用户消息（Issue 标题）；task_finished 显示为助手消息（finish_report 摘要，附带置信度）

**选择 fixture**：没有新增任何说明文字。左侧「近期」直接列出三条 #87，用状态图标（✓ / × / 钱币）加北京时间区分，标签放在悬停提示里；也支持 `?source=fixture:<name>|mock` 和 `?speed=`。

**和任务卡的偏差**
- fixture 用 Vite 的 `?raw` 直接从仓库根导入，没有复制到 `public/`。这样只有一份数据源，构建时会打成独立的 chunk，Tauri 离线也能用。为此 `vite.config.ts` 的 `server.fs.allow` 加上了仓库根
- 新增两个开发依赖：`json-schema-to-typescript`（生成类型）和 `vitest`（单元测试），都不进产物

**验证**
- `npm test`：29 项通过（覆盖解析、映射、三份 fixture 的终态、幂等、部分折叠、回放计时 / 续传 / 退订、URL 参数、生成类型是否过期）
- `npm run lint`：通过，只剩 useWritingStream 里原有的警告；`npm run build`：通过；`uv run pytest -q`：35 项通过
- `tools/shoot-replay.mjs`：三份 fixture 都走到终态，chip 显示正确；暂停冻结，继续后不跳字；mock 源可用；页面没有报错
- `tools/test-guards.mjs`：21/21 通过
- 本轮没有重建 Windows 安装包

## 第 4 轮（已完成）

**屏蔽浏览器默认行为**
- 右键：全局屏蔽 WebView2 默认菜单。只有在输入框里，或在消息、推流、账本中选中了文字时，才弹出自绘菜单（剪切 / 复制 / 粘贴 / 全选）。可用 Esc 或 ↑↓ Enter 操作；点击外部、滚动、窗口失焦或改变大小时自动关闭；靠近窗口边缘时会翻转或贴边，不会超出窗口
- 开发调试：只在开发模式（`import.meta.env.DEV`）下，按住 Shift 再右键可以调出原生菜单来检查元素；正式版没有这个入口
- 快捷键拦截（前端 `src/lib/desktopGuards.ts`）：F5、Ctrl+R、Ctrl+P、Ctrl+F/G、F3、Ctrl+U、F7、Ctrl+S/H/J/N/T、Alt+←/→、浏览器专用的前进/后退/刷新键；Ctrl+Shift+I/J/C 和 F12 只在正式版拦截；不在输入框里时 Ctrl+A 也拦截
- 缩放：拦截 Ctrl+滚轮、Ctrl+加减号/0 和双指捏合（Tauri 默认也已关闭缩放快捷键）。辅助功能方面，WebView2 会跟随 Windows 的“缩放与布局 / 使文本更大”设置，以后可以在设置页加一个字号选项
- 拖放：拖入文件或链接不会在 WebView 里打开（以后标了 `data-dropzone` 的区域除外）；图片、链接、图标不能被拖出；鼠标中键的自动滚动和打开链接也禁止了
- 文字选择：界面外框（侧栏、标题栏、按钮、标签）不能选中；消息、推流内容、账本和输入框可以选中
- 原生层（`src-tauri/src/lib.rs`，只对 Windows 生效）：通过 `with_webview` 直接改 WebView2 的设置。正式版关闭 `AreBrowserAcceleratorKeysEnabled`；所有版本关闭默认右键菜单、左下角链接状态栏、表单自动填充和密码保存，以及触摸板左右滑动前进后退。Tauri v2 的配置文件没有提供这些开关；`additionalBrowserArgs` 保持默认没改（改了会覆盖 wry 默认关掉的 msWebOOUI 等功能）。用 cargo xwin 检查过，开发版和正式版都能编译通过
- 剪贴板：读剪贴板的权限由 wry 在 Windows 上自动允许，粘贴走 `navigator.clipboard`，再用 `execCommand('insertText')` 写入，这样 React 的输入状态和撤销栈都正常

**验证**：`tools/test-guards.mjs` 共 21 项全部通过（右键、快捷键、缩放、刷新、选择规则、复制粘贴、Esc 关闭、菜单不越界）

**截图**：`docs/composer-context-menu.png`（输入框里的右键菜单），`docs/context-menu-full.png`（整窗）

**安装包**：这一轮没有重新构建。以后只在你提出时才打包；现在的 `release/` 里是第 3 轮的安装包，不包含这一轮的改动

## 第 3 轮（已完成）

**去掉说明文字**：界面只留必要的标签，信息改用布局、图标、状态小标签和悬停提示（暖色深墨底，悬停约 0.4 秒后淡入）来表达
- 删除：侧栏的英文副标、会话预览行和仓库行；对话页的“会话”小标题和“验证优先的编程代理”副标；输入框下的提示行（占位文字缩短为“写下任务…”）；消息下方的署名和模型说明（改为悬停才显示时间，模型说明放进提示）；推流面板的“AGENT 活动”小标题、“落笔中 · 规划”这类状态句、页脚“逐字落墨 · 随写随干”和计数、空白时的“纸页微暖…”
- 设置页删除：开头介绍、各节标题旁的注释、模型卡片的说明行、API 密钥的说明（改为“已托管”标签）、高峰闸门右侧说明和底部段落、预算卡片的提示行、账本的价格说明（改为 ⓘ 悬停）和底注
- 状态栏从整句文字改为图标标签：Flash · 空闲/高峰 · 余额 · 版本号，详情在悬停提示里
- 推流状态改为一个小圆点：落笔时用当前角色的颜色并呼吸，暂停变灰，写完变绿；正在工作的角色点亮，其余变淡

**自绘标题栏**（`src/components/TitleBar.tsx`）
- `decorations: false` 加 `shadow: true`：去掉系统边框，保留系统阴影。Win11 由系统（DWM）自动画圆角和细边框，Win10 是直角加阴影
- 40px 高的暖色标题条：左边是侧栏开关和“三证”字标，中间是当前会话标题，右边是自绘的最小化、最大化/还原、关闭三个按钮（46px 宽，图标是细线 SVG）；关闭按钮悬停时是柔和的赭红 #b9695a
- 整条可拖动（`data-tauri-drag-region`），双击最大化/还原（Tauri 自带）；文字和图标也带拖动属性，点在字上同样能拖
- 最大化按钮的图标随窗口状态切换（监听窗口大小变化）
- 浏览器预览里不会调用 Tauri，三个按钮照常显示，点击什么也不做（`src/lib/appWindow.ts`）
- 窗口权限：minimize、maximize/unmaximize、toggle-maximize、internal-toggle-maximize、is-maximized、close、start-dragging、start-resize-dragging；Tauri 编译时已校验通过
- 侧栏可以收起和展开

**Windows 安装包已重新构建**：`release/TriWitness_0.1.0_x64-setup.exe`（12.6 MiB）

### 需要在 Windows 真机上测
- 贴靠布局（Snap Layouts）：自绘的最大化按钮悬停时**不会**弹出 Win11 的贴靠布局面板（要改就得在 Rust 里处理窗口命中测试）；Win+方向键和拖到屏幕边缘贴靠应该仍然可用
- 圆角：Win11 应该由系统自动画圆角；Win10 没有圆角。最大化后圆角和阴影是否正确消失
- 边缘拉伸：没有系统边框时靠阴影区域拉伸，要确认四条边和四个角都能拉
- 标题栏里双击最大化、拖动，以及最大化状态下往下拖能否还原
- 多显示器、不同缩放比例下按钮位置和窗口位置是否正确
- 关闭按钮现在直接退出，没有最小化到托盘

## 第 2 轮（已完成）

**书写感动画重写**
- 改用虚拟时钟加 requestAnimationFrame 驱动：暂停时时钟停住，继续后从原处接着写，不会跳字；切到后台再回来，也不会一下涌出一大片
- 节奏是固定算好的（正弦呼吸加字符哈希），不用随机数，所以不会抖：句号、问号后停约 260ms，逗号、顿号后约 150ms，行末停约 380ms 换气，词与词之间稍顿，长行中途偶尔停一下
- 墨色变化：字刚落下时是湿润的浅琥珀色，约 0.9 秒内沉成深墨，即“随写随干”
- 每写新的一行，整行轻轻淡入，行首的角色点上散开一圈墨晕；光标跟着笔尖走，暂停时变淡、静止
- 支持流式追加：数据源按块推送（mock 每 1.6 秒来一行），引擎接在队尾继续写；如果用户往上翻看历史，就不自动滚到底
- 遵循系统的“减少动态效果”设置：整行直接出现，不做位移、模糊和墨晕
- 去掉了和行距对不齐的信笺横线，换成纸页顶部的柔光

**字体本地化**
- 用 @fontsource 把 Noto Serif SC 500/600、Noto Sans SC 400/500、JetBrains Mono 400/500 打包进应用，已删掉 CDN
- 构建时去掉 woff 回退，只保留 woff2，并按 unicode-range 分片按需加载；dist 从 27MB 降到 13MB
- 用 puppeteer 实测：外部请求数为 0，5 个字重全部加载成功

**设置与预算页**（左下角“设置与预算”，或访问 `?view=settings`）
- 模型白名单：只启用 deepseek-flash；deepseek-v4-pro 显示为删除线加“禁用”；qwen / glm 标为“以后”
- API 密钥：只说明由系统凭据库保管，界面不读、不显示
- 高峰闸门：按北京时间（UTC+8）计算，与本机时区无关。显示当前状态、下次切换时间、24 小时时间轴（工作日 9–12、14–18 两段高峰，周末用虚线标出作参考）和一周视图
- 预算：单任务上限 ¥0.80、总预算 ¥100、已花费加进度条；账本是 mock 数据，花费按官方空闲价计算，超过上限的行标红

**Windows 安装包（从 Linux 交叉编译成功）**
- `release/TriWitness_0.1.0_x64-setup.exe`（12.6 MiB，NSIS，未签名）
- 用的是 cargo-xwin 加 clang/lld 加 makensis；这次为了省内存用了 thin LTO
- 详细步骤见 `docs/WINDOWS_BUILD.md`

## 截图（docs/）
- `live-stream.png`：真实核心（演示适配器）实时推流
- `approval-card.png`：审批卡，状态签为「待批」
- `result.png`：结论卡（复验通过 · 风险 L2 · pr.md 摘要）
- `stopped.png`：中途停止
- `replay-success.png` / `replay-failure.png` / `replay-budget_exceeded.png`：三份 fixture 回放到终态
- `replay-success-mid.png`：success 回放到规划阶段（状态、费用跟笔）
- `replay-budget-tooltip.png`：费用 chip 的悬停提示
- `main-midstream.png`：主界面，推流写到一半
- `titlebar.png`：标题栏，关闭按钮处于悬停状态
- `tooltip.png`：悬停提示示例
- `stream-closeup.png`：推流特写，能看到墨色由浅变深
- `main-stream-late.png`：推流后段
- `main-reduced-motion.png`：开启减少动态效果时
- `settings.png` / `settings-full.png`：设置与预算页

重新截图：先运行 `npm run dev`，再运行 `cd tools && node shoot.mjs`；回放截图运行 `node tools/shoot-replay.mjs`（可用 `SPEED=` 调速）；真实核心截图先运行 `TW_DEV_BRIDGE=1 TW_DEMO_DELAY_S=1.2 npm run dev`，再运行 `cd tools && node shoot-live.mjs`

## 下一步
- [ ] 在 Windows 真机上装一次安装包，看字体渲染（ClearType）和窗口的 DPI 缩放
- [ ] Win11 贴靠布局：自绘最大化按钮在 Rust 里处理窗口命中测试
- [x] 用 tw-events/1 事件模型替换 mock（UI-09）
- [ ] 实现 SSE 版 EventSource，接 `/v1/runs/{id}/events`（断线后按 afterSeq 续传）
- [x] 桌面端驱动真实核心：起任务 / 推流 / 审批卡 / 停止 / 续上 / 结论卡（UI-10）
- [ ] Windows 真机跑一次真实核心（Git Bash / `py -3`），并重建安装包
- [ ] 从 checkpoint 继续已停止的任务
- [ ] 完整证据页（复现 / 回归 / 评审 / diff）
- [ ] 实现 hitl_request 卡片（问答型）
- [ ] 推流面板：可折叠、可停靠到底部，书写速度和字号可调
- [ ] 证据包卡片，L0–L3 风险徽章
- [ ] 接入法定节假日日历；账本改由 `tw budget` 驱动
- [ ] 安装包代码签名
