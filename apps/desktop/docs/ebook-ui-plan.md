# 三证桌面端 UI 全面改造计划：电子书阅读风格（v1 草案）

> 状态：计划稿，未改代码。日期 2026-10-13。范围：`apps/desktop`（Tauri + React）与 `site/`。
> 原则：交互与控件 **1:1 对齐 Claude Desktop**（不增不减），差异只在美学与验证功能（结论卡、证据、diff）。动画高质量但克制。

## 0. 硬指标（团队已商定）
| 项 | 目标 |
|---|---|
| 正文字号 | 16–17px（默认 16px，设置可切 17px） |
| 正文行高 | 1.7 |
| 行宽 | ≤ ~70 个汉字（`max-width: 70em` 不对；用 `max-width: calc(70 * 1em)` 以正文字号计 ≈ 1120px 上限，实际取 `min(70em, 100%)`，16px 时 1120px；建议对话列 `68em`） |
| 日间 | 米白底 + 深棕灰字，禁用纯白 `#fff` / 纯黑 `#000` |
| 夜间 | 深胡桃底，正文对比度 ≈ 7:1（取 7.5–8） |
| 对比度底线 | 正文 ≥ 7:1，次要文字 ≥ 4.5:1（日夜两套，所有可能底色） |
| Token 化 | 组件内禁止硬编码颜色，一律走 CSS 变量（现 `src/components` 内有 8 处 6 位 hex 需清理） |
| 代码 | 等宽 JetBrains Mono，语法高亮降饱和 |
| 动效 | 默认"减少动效"，并始终尊重 `prefers-reduced-motion` |

## 1. 现状审计（来源：`src/index.css` 682 行、`src/components/*`）
1. **对比度过高**：日间 `--color-ink #221812` 对 `--color-parchment #f1e6d0` = **14.05:1**；夜间 `#ecdfca` 对 `#211913` = **13.17:1**。长时间阅读偏刺眼，夜间尤甚（目标 7:1）。
2. **正文字号偏小**：`.md, .md-tail { font-size: 14.5px; line-height: 1.85 }`；组件里大量写死小字号：`text-[12px]`×40、`text-[12.5px]`×40、`text-[11.5px]`×31、`text-[13px]`×29、`text-[10.5px]`×26、`text-[11px]`×17、`text-[10px]`×6。没有统一字号阶梯。
3. **纹理与渐变噪声**：`.app-grain` 叠了 SVG fractalNoise 纸纹（`--paper-grain`，日 0.075 / 夜 0.035 alpha）+ 2 个彩色 radial-gradient + 线性渐变；`.stream-paper`、`.titlebar` 也各有渐变。阅读区底色不均匀，文字边缘有"脏感"，也增加重绘成本。
4. **动效偏多、偏长**：`lineEnter 520ms`、`inkSettle 900ms`、`bloomFade 1400ms`、`inkIn 620ms`、`caretBreath 1.8s/2.4s` 无限循环、`shimmer 2.2s` 无限循环、`indeterminate 1.4s` 无限循环。已有 `prefers-reduced-motion` 覆盖（L185、L652），但默认态仍是"全动效"。
5. **行宽**：消息列 `max-w-[720px]`（×4），16px 时仅 45 字/行，偏窄；用户气泡 `max-width: 75%`。
6. **语义色名不符**：`--color-amber*` 实际是蓝（#2f4a72），后续维护易误用 → 改名为 `--accent*`。
7. **焦点态**：仅 Tip 用了 `:focus-visible`，按钮/输入/侧栏项无统一焦点环。
8. 字体：Noto Serif SC / Noto Sans SC / JetBrains Mono 已本地打包（`src/assets/fonts`），保留。

## 2. 新设计 Token

### 2.1 日间「米白书页」
| Token | 值 | 对 bg 对比度 | 用途 |
|---|---|---|---|
| `--bg` | `#f4ede0` | — | 主阅读底（米白，非纯白） |
| `--panel` | `#ece3d2` | — | 侧栏、代码块底 |
| `--raised` | `#faf6ee` | — | 输入框、卡片、弹层 |
| `--border` | `#d6cbb6` | — | 1px 分隔线（装饰性，不要求 3:1） |
| `--text` | `#3b342c` | **10.53**（panel 9.62 / raised 11.37） | 正文、标题 |
| `--text-soft` | `#544a3f` | **7.43**（panel 6.79） | 次要正文、工具行 |
| `--text-muted` | `#6b6052` | **5.27**（panel 4.82） | 时间戳、提示（≥4.5 AA） |
| `--accent` | `#2f4a72` | **7.70** | 链接、主按钮、焦点环 |
| `--ok` | `#3a6341` | **5.93** | 验证通过 |
| `--err` | `#9a2a22` | **6.61** | 失败/错误 |
| `--warn` | `#7d5212` | **5.84** | 不确定/警告 |

说明：日间正文 10.5:1 已比现状 14:1 柔和；不降到 7:1 是因为浅底上过低对比在白天强环境光下发灰。

### 2.2 夜间「深胡桃」
| Token | 值 | 对 bg 对比度 | 用途 |
|---|---|---|---|
| `--bg` | `#1f1a15` | — | 主阅读底 |
| `--panel` | `#262019` | — | 侧栏、代码块 |
| `--raised` | `#2d261e` | — | 输入框、卡片 |
| `--border` | `#4a3e32` | — | 分隔线 |
| `--text` | `#bdae97` | **7.94**（raised 6.87） | 正文（≈7:1 目标） |
| `--text-strong` | `#d2c4ae` | **10.06** | 标题、强调、代码块内正文可选 |
| `--text-muted` | `#a3937d` | **5.77**（raised 4.99） | 次要信息 |
| `--accent` | `#9fb4d8` | **8.21** | 链接/主按钮/焦点 |
| `--ok` | `#97b99c` | **8.00** | 通过 |
| `--err` | `#e0907f` | **6.96** | 失败 |
| `--warn` | `#d4a660` | **7.74** | 不确定 |

> 计算方法：WCAG 2.x 相对亮度公式，(L1+0.05)/(L2+0.05)，脚本复算即可。所有文字色在其可能出现的底色上 ≥ 4.5:1。

### 2.3 字号阶梯（替换所有 `text-[Npx]` 写死值）
| Token | px | 行高 | 用途 |
|---|---|---|---|
| `--fs-body` | 16（可切 17） | 1.7 | 消息正文、输入框 |
| `--fs-ui` | 14 | 1.5 | 按钮、侧栏条目、工具行标题 |
| `--fs-meta` | 13 | 1.45 | 时间戳、徽标、状态栏（最小字号，取代 10–12.5px） |
| `--fs-code` | 14 | 1.6 | 代码块/diff |
| `--fs-h3/h2/h1` | 17 / 19 / 22 | 1.4 | Markdown 标题 |
| `--fs-display` | 26 | 1.3 | 空状态欢迎语（保留现 26px） |

- 正文 serif（Noto Serif SC），UI 控件 sans（Noto Sans SC），保持现分工。
- 段间距 `0.8em`，列表项 `0.35em`；中文 `text-align: start`，不两端对齐；开启 `font-feature-settings: "palt" 0`、`hanging-punctuation` 不用（Chromium 不支持）。

### 2.4 间距与版式
- 4px 基准：`--sp-1..8 = 4,8,12,16,24,32,48,64`。
- 消息列：`max-width: min(68em, 100% - 2*--sp-6)`（16px 时 ≈ 68 字/行），居中。
- 用户消息：取消气泡化重底色，改为 `--raised` 浅底 + 圆角 12px（Claude Desktop 同构），最大宽 85%。
- 卡片圆角统一 10px；阴影只保留弹层一级 `0 4px 16px rgb(0 0 0 / .08)`（夜间 .3）。

### 2.5 纹理 / 渐变
- **默认移除** `--paper-grain` 与 `.app-grain` 的彩色 radial-gradient、`.stream-paper`/`.titlebar` 渐变，改纯色 `--bg`。
- 设置 → 外观里保留开关「纸张纹理」（默认关，alpha 上限 0.03，仅铺在侧栏，不铺阅读区）。若 Eva 认为这是 Claude Desktop 没有的控件，则直接删除，不加开关（**待拍板**）。

### 2.6 代码与 diff
- 高亮主题自定义：日间基色 `--text`，关键字 `#5a4a7a`、字符串 `#4f6b45`、注释 `--text-muted` 斜体、数字 `#7d5212`；夜间对应 `#b7a3c9 / #a9c19a / #a3937d / #d4a660`。饱和度均控制在 HSL S ≤ 35%。
- diff 增/删行底色：日 `#e4ead8` / `#f0dcd5`，夜 `#26301f` / `#3a2420`；行内仍用 `+/-` 字符，不只靠颜色区分（色弱友好）。

### 2.7 动效（克制）
- 新增 `--motion` 档：`reduced`（默认）/`standard`。`prefers-reduced-motion: reduce` 时强制 `none`。
- reduced 档：只保留 ≤160ms 的透明度过渡（弹层、菜单 `ctxIn`）；流式输出不做逐行 `lineEnter`/`inkSettle`/`bloomFade`，直接出字；光标 `caretBreath` 改为静态竖线；`shimmer` 改为静态"思考中…"文字 + 单点 1s 低频脉冲（可关）。
- standard 档：时长上限 240ms，缓动 `--ease-tender`；仍禁止无限循环装饰动画（进度条 indeterminate 除外）。

### 2.8 焦点与可达性
- 全局 `:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: inherit }`，鼠标点击不显示（沿用 Tip 的做法）。
- 焦点环对相邻底色 ≥ 3:1（日 accent 7.7、夜 8.2，满足）。
- 所有图标按钮有 `aria-label` + Tip；状态不只用颜色（StatusGlyph 保留形状差异）。

## 3. 分批范围
### 批次 1：对话主界面
| 区域 | 组件 | 改动 |
|---|---|---|
| 色板微调 | `index.css` | 新 token（§2）、字号阶梯、移除阅读区纹理/渐变、动效档、焦点环；`amber*` → `accent*`（旧名保留别名一版）；清理组件内硬编码 hex |
| 排版 | `Markdown` `MarkdownRenderer` | 正文 16px/1.7、列宽 68em、段距、标题阶梯 |
| 消息气泡 | `MessageBubble` `AssistantTurn` | 用户消息 raised 浅底圆角 12px，最大宽 85%；助手无气泡 |
| Markdown/代码 | `MarkdownRenderer` `CopyButton` | 降饱和高亮、diff +/- 双编码 |
| 流式区 | `StreamingText` `WritingStream` `ThinkingBlock` `ToolRow` `VirtualList` | 流式动画降级为直接出字、静态光标；VirtualList 行高估算随字号更新 |
| 结论卡 | `ResultCard` `StatusGlyph` `MemoryChip` | 通过/不确定/失败 = ok/warn/err + 图形；"不确定"不得用绿色 |
| 审批卡 | `ApprovalCard` | 主次按钮层级、焦点环 |
| 侧栏会话列表 | `Sidebar` `TitleBar` `StatusBar` | 纯色 panel，条目 14px、meta 13px，选中态用 accent 左边线 + 背景 |
| 输入区 | `Composer` `PlusMenu` `ModelPicker` `Attachments` | 16px 输入、raised 底、焦点环；控件集合不变 |
| 错误/空态 | `Toaster` 空状态 | err 色 + 可读文案 |

### 批次 2：设置与主题
- `SettingsPage` 9 个分区 + `settings/*`（`DataDialogs` `RulesEditor` `SandboxInstall`）、`StyleDialog` `ApiKeyDialog`：全部套 token 与字号阶梯。
- **主题预览**：外观分区内日/夜/跟随系统的小样预览（同一段正文 + 代码 + 结论卡缩略）。
- **长时间阅读开关**：开启后正文 17px、行高 1.8、纸张纹理强制关、动效强制 reduced；关闭恢复默认 16px/1.7。
- 动效档、字号档作为外观项；与 Claude Desktop 外观设置逐项对照，不多出控件（纹理开关是否保留见 §6）。

### 批次 3：其他页面
`ProjectsPage`（项目）、`ArtifactsPage`/`ArtifactsPanel`（作品）、`ChatsPage`（会话管理）、`Dialog` `ChatDialogs` `PrDialog` `ProjectPicker` `RepoPicker`（对话框）、`ContextMenu` `Popover` `PlusMenu` `Tip`（菜单/浮层）：统一 token、圆角、阴影、焦点环、13px 最小字号。

### 批次 4：公开站点 `site/` 对齐
`site/index.html`：同一色板与字号阶梯（可抽 `tokens.css` 共享或复制并在 CI 比对一致），截图换成新界面，日夜跟随 `prefers-color-scheme`。

## 4. 验收标准
1. 全仓 `rg "text-\[(10|10\.5|11|11\.5|12|12\.5)px\]" src` 为 0；最小可读字号 13px。
2. 消息正文计算样式：font-size 16px（17 档 17px）、line-height 27.2px（1.7）；1920 宽窗口下每行 ≤ 70 汉字（实测截图数字数）。
3. 无 `#ffffff` / `#000000` 文字或背景（`rg -i "#fff\b|#ffffff|#000\b|#000000"`，阴影 rgba 除外）。
4. 对比度：自动化测试（vitest 读 token 计算）断言 §2.1/2.2 表中每对 ≥ 表值 − 0.05，夜间正文 7.0–8.5。
5. 默认首启 motion=reduced；系统开启"减少动画"时无任何 animation（DevTools Animations 面板为空）；无无限循环装饰动画。
6. 阅读区无纹理/渐变背景（computed `background-image: none`）。
7. 键盘 Tab 走完 Composer → 发送 → 侧栏 → 设置，每个可交互元素都有可见焦点环。
8. 控件清单与 Claude Desktop 逐项对照表无"多"或"缺"（附截图对照）。
9. 现有 vitest 与 `tsc` 全绿；Windows 安装包构建通过。
10. `rg -n "#[0-9a-fA-F]{3,8}\b|rgb\(" src/components` 为 0（颜色只在 `index.css` token 定义处出现）。
11. 长时间阅读开关开启后：正文 17px / 行高 1.8 / 无纹理 / 无动画；关闭后恢复。
12. 批次 4：site 与桌面端 token 值一致（脚本比对）。
13. 长对话（≥200 条、含 20 个代码块）滚动不掉帧（Performance 面板无 >50ms 长任务成串）。

## 5. 真用户 30 分钟走查清单（@真用户阿验）
前提：拿到批次 1 的安装包或分支；日间、夜间各 15 分钟；Windows 100% 与 125% 缩放各看一次。每项记 通过 / 问题（严重度）/ 截图。

**0–3 分钟 首印象**
- [ ] 打开后底色是否均匀、无脏点纹理；日间是否感觉"纸"而非"白屏"
- [ ] 侧栏、标题栏、输入框层级是否一眼可分

**3–12 分钟 长对话阅读（日间）**
- [ ] 让三证解释一段较长代码（≥15 段输出），连续读完：字号是否无需凑近、行宽是否不用左右甩头
- [ ] 段落、列表、标题间距是否清楚；中文标点不挤
- [ ] 流式输出时有无闪烁、跳动、文字位移
- [ ] 代码块：高亮是否温和、能否区分关键字/字符串/注释；复制按钮可找到
- [ ] 上下滚动 200 条历史：是否卡顿、位置是否跳

**12–18 分钟 任务与验证**
- [ ] 选仓库 → 修一个小问题：工具行、思考块折叠/展开是否清楚不吵
- [ ] diff：增删行不看颜色也能分（看 +/-）
- [ ] 结论卡：通过/不确定/失败 三态一眼区分；"不确定"不像成功
- [ ] 开 PR 审批卡按钮层级清楚

**18–21 分钟 错误与空态**
- [ ] 断网或填错 Key：错误提示是否可读、有下一步
- [ ] 新建对话空状态：欢迎语与输入框位置舒适

**21–30 分钟 夜间（关灯或低亮度）**
- [ ] 切夜间：正文不刺眼也不发灰；标题与正文可分
- [ ] 重复长对话阅读 5 分钟，记录眼睛干涩/想眯眼的时刻
- [ ] 代码块、diff、结论卡夜间三态色是否仍可分
- [ ] 系统开启"减少动画"后重开：确认没有任何动画
- [ ] 全程用 Tab 键走一遍主要控件，焦点是否始终可见

**收尾**：输出 通过项 / 问题项（阻断/严重/一般/建议）/ 建议项；主观疲劳感 1–5 分（日、夜各一）。

## 6. 待拍板
1. 纸张纹理：彻底删除，还是保留默认关闭的开关（是否违反"控件 1:1"）。
2. 默认字号 16 还是 17。
3. 日间正文 10.5:1、夜间 7.9:1 均满足 ≥7:1，是否接受。
4. 批次 1 是否需与 git 自动初始化修复同一版本发布。

## 7. 节奏
1. 批次 1：token + index.css（0.5 天）→ 组件替换字号/色（1–1.5 天）→ 测试与对照截图（0.5 天）→ 打包给阿验走查。
2. 根据走查修正 → 批次 2（设置与主题）→ 批次 3（其他页面）→ 批次 4（site）。每批交阿验走查后再进下一批。
