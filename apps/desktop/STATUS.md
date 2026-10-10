# 桌面 UI 进度

> 不按日历排期，做完一项记一项。

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
