# 原生 GUI vs Web UI：性能差异与 TriWitness 的取舍

> 2026-10-11 · 研究备忘（开发暂停期间，¥0 API）。外部数字全部附来源；**本机实测**数字来自 Linux headless Chrome（软件渲染，非 WebView2），只作相对参考；**估计**会明确标注。
> 原始数据：`perf-trace-initial.json`、`perf-longchat-clone.json`（§3 初测），`perf-*-before/after.json`（§6 优化前后）；脚本：`apps/desktop/tools/perf-trace.mjs`、`perf-longchat.mjs`。

## 0. 一句话结论

对 TriWitness 这种「对话 + 流式文字 + 动画」的产品，**Web UI 不是瓶颈，写法才是**。WebView2 的代价主要是**常驻内存**（多进程，约几百 MB 量级）和**无上限增长的 DOM**；帧率、输入延迟、中文 IME、字体排版反而是 Web 的强项。真正会咬人的是**很长的对话、很大的 diff、多路并发流式**——在 Tauri 内就能解决（虚拟化 / `content-visibility` / 节流提交 / 只动 transform+opacity / 重活放 Rust）。只有当目标变成「编辑器级 120fps + 低内存常驻 + 海量文本」（Zed、Warp 那一档）才值得换原生。

## 1. 各维度对比

| 维度 | 原生 Windows（WinUI 3 / WPF） | 跨平台原生（Qt/QML、Flutter、Slint、egui/GPUI） | Electron | Tauri / WebView2（我们） |
|---|---|---|---|---|
| 安装包 | 小（几 MB 起；WinUI 3 自包含会大些） | 小～中 | 大：自带 Chromium+Node，示例 **244 MiB**（[Hopp](https://www.gethopp.app/blog/tauri-vs-electron)） | 小：用系统 WebView2，示例 **8.6 MiB**（同上）；**我们 0.2.0 = 12.7 MiB**，其中字体占大头 |
| 冷启动 | 快 | 快 | 对简单应用与 Tauri 差别可忽略（Hopp 实测 "negligible"） | 同左；WebView2 运行时 Win11 自带（[Electron 博客](https://electronjs.org/blog/webview2)） |
| 内存 | 最低 | 低：macOS 同功能应用峰值 Slint 106–133MB、Qt 139–174MB、Flutter 166–216MB（[15 框架基准](https://zenn.dev/mizugeeks/articles/1019cf2353d343?locale=en)） | 高：同基准 444–644MB；Hopp 6 窗口 409MB | 高：同基准 308–739MB（macOS WKWebView，非 WebView2）；Hopp 6 窗口 172MB。WebView2 一组进程 = browser + renderer + GPU + 工具进程（[MS 进程模型](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-model)），每个实例都有自己的一套（[MS 性能指南](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/performance)） |
| 动画 CPU/GPU | 合成器动画（WinUI Composition）很省 | GPU 直绘；GPUI 目标帧时 <3ms（[Zed](https://zed.dev/blog/we-have-to-start-over)） | Chromium 合成器：transform/opacity 走 GPU，便宜；动 layout 属性就贵 | 同 Electron（同为 Chromium 内核，微软自己说渲染性能"差别很小"——[Electron 博客](https://electronjs.org/blog/webview2)） |
| 帧节奏 / 输入延迟 | 稳 | 最稳（无 GC、无 DOM 重排）；Zed 正是因 Atom 的重排/GC 停顿做不到 8.33ms 预算而自建 GPUI（[Zed](http://zed.dev/blog/videogame)） | 60fps 容易，120fps 稳定难；GC、重排是长尾来源 | 同左 |
| 文字排版 & 中文 IME | 系统级，最好 | **参差**：Flutter Windows 中文输入法候选框错位/闪烁是长期 issue（[#128323](https://github.com/flutter/flutter/issues/128323)、[#173526](https://github.com/flutter/flutter/issues/173526)）；egui/iced 要自带 CJK 字体（+~25MB，见 15 框架基准） | 浏览器级 TSF/IME，成熟；字体回退、`unicode-range` 子集、连字、换行规则都现成 | 同左（WebView2 = Edge 内核） |
| 长列表 / 流式渲染 | 有虚拟化控件（ItemsRepeater 等） | 自己管理（GPUI/Warp 只画可见部分） | **DOM 不会自己回收**，必须自己做虚拟化 / `content-visibility` | 同左 → 本项目的主要风险点（见 §3） |
| Markdown / 富文本 | 弱：要自造或嵌 WebView（有 macOS 开发者在 [HN](https://brianlovin.com/hn/47104973) 说 Swift Markdown 库慢、缺 Mermaid，最后自写 Rust+TextKit 渲染器） | 弱～中 | 最强（react-markdown、shiki、KaTeX、Mermaid…） | 同左 |
| 电池 | 最好 | 好（但 GPU 常驻绘制要注意降频，Zed 只在输入后 1s 保持满帧——[Zed 120fps](https://zed.dev/blog/120fps)） | 较差（多进程 + 常驻 Chromium） | 比 Electron 少一个 Node 主进程；渲染侧同 Chromium。闲置时**不能留无限循环动画** |
| 无障碍 | UIA 原生 | Qt/Flutter 有桥接，egui/GPUI 较弱 | Chromium 无障碍树完整 | 同左 |
| DPI / 多显示器 | 原生，好 | 一般好 | 好 | 好（WebView2 跟随 DPI；我们的自绘标题栏需自测缩放 125/150%） |
| 开发速度 / 生态 | 仅 Windows；C#/XAML | Qt 许可、Flutter Dart、Rust UI 生态年轻（[Warp：Rust UI 为什么难](https://www.warp.dev/blog/why-is-building-a-ui-in-rust-so-hard)） | 最快，AI 写得最好 | 快；前端生态 + Rust 后端；AI 写得好 |

**注意**：上面内存数字来自不同平台、不同应用，只能看趋势（原生 ≈ 100–200MB，WebView 系 ≈ 300–700MB，Electron 最高），不能直接套到我们的 app。我们在 Windows 真机上的数字**还没测**（见 §5 待办）。

## 2. 真实产品怎么选

| 产品 | 技术 | 理由（有来源的） |
|---|---|---|
| Claude Desktop（含 Claude Code Desktop / Cowork） | Electron（内含部分 Rust/Swift/Go） | 负责人 Felix Rieseberg：一切是取舍，Electron 只是工具；Boris：团队熟悉 Electron、和 Web 共享代码保证一致观感、"Claude is great at it"（[HN 讨论](https://brianlovin.com/hn/47104973)） |
| ChatGPT macOS | 原生 SwiftUI | [Windows Central](https://www.windowscentral.com/software-apps/windows-11/after-microsoft-invested-dollar10-billion-openai-snubs-windows-11-as-it-releases-chatgpt-app-first-on-mac-were-just-prioritizing-where-our-users-are)："uses SwiftUI" |
| ChatGPT Windows | Electron（不是 WebView2，也不是 WinUI） | [Windows Latest 拆包](https://www.windowslatest.com/2024/10/18/i-tried-the-official-chatgpt-app-for-windows-11-its-just-an-electron-based-chrome-wrapper/)；2026 版静态分析显示 Electron 39 + Vite + React，MSIX 分发（[腾讯云文章](https://cloud.tencent.com/developer/article/2690047)，第三方分析） |
| Codex app | Electron（agent 运行时是 Rust CLI） | OpenAI 的 Romain Huet：「specifically so we can support Windows and Linux」（[HN](https://news.ycombinator.com/item?id=46859673)） |
| VS Code / Cursor | Electron；Cursor 是 VS Code 分支 | VS Code 是 Electron 的标志性应用；Cursor 分支说明见 [Cursor 论坛](https://forum.cursor.com/t/vs-fork-question/5105) |
| Zed | 自研 GPUI（Rust，GPU 直绘） | Electron/Atom 的重排与 GC 停顿撑不住 120fps；目标帧 <3ms（[Zed 博客](http://zed.dev/blog/videogame)、[访谈](https://zed.dev/blog/we-have-to-start-over)） |
| Warp | 自研 Rust UI，Metal/wgpu 直绘，字形图集 | 终端是海量文本 + 高频刷新（[How Warp Works](https://www.warp.dev/blog/how-warp-works)） |

**规律**：做「聊天 / agent 前台」的头部公司（Anthropic、OpenAI 的 Codex 与 ChatGPT Windows）几乎都选 Web 技术，理由是跨平台、与 Web 版共享代码、迭代快；只有「编辑器 / 终端」这类**文本即产品、要 120fps** 的才自建原生渲染。ChatGPT macOS 是反例：资源充足时为平台质感做了原生。

## 3. 本机实测（我们自己的 app）

环境：box 上 Linux headless Chrome（无 GPU，软件光栅化），1440×900，DPR 1。**不是 WebView2、不是 Windows**，绝对值偏悲观，只看相对关系。

### 3.1 生产构建体积（`npm run build`）

| 资源 | 原始 | gzip |
|---|---|---|
| 主 JS `index-*.js`（React 19 + framer-motion + react-markdown…，单 chunk） | 971 KB | 306 KB |
| 其他 JS（5 个 fixture/窗口 chunk） | 50 KB | ~10 KB |
| CSS（Tailwind + 400 个字体子集的 `@font-face`） | 483 KB | 185 KB |
| 字体 woff2（Noto Serif/Sans SC + JetBrains Mono，**400 个 unicode-range 子集**，按需加载） | 11.3 MB | — |
| `dist/` 合计 | 12.8 MB | — |
| Windows 安装包 0.2.0 | 13.36 MB（12.7 MiB） | — |

→ 安装包几乎全是**字体**，不是 Web 框架；Electron 的同类包会再多出 ~100–200MB Chromium。首屏实际只下 ~480KB（JS+CSS），字体子集遇到字才加载。

### 3.2 书写推流回放（生产构建，`fixture:success`，30 秒）

| 指标 | 数值 |
|---|---|
| DOMContentLoaded（本地 preview） | 140 ms |
| 帧率 / 帧时 p50 / p95 / p99 / 最差 | 59.8 fps / 16.7 / 16.7 / 16.8 / 50 ms |
| >33ms 的掉帧 | 2 帧（/1796） |
| Long task（>50ms） | 1 次，61 ms（启动期） |
| JS 堆 | 3.7 MB → 8.4 MB |
| DOM 节点 | 291 → 1342（30s 推流后）；元素 831 |
| 30s 内 layout / style recalc 次数 | 580 / 2199（≈每帧一次 style，约每 3 帧一次 layout） |
| 空闲 10s | 59.6 fps，0 long task |

### 3.3 Claude 式对话一轮（dev 构建 + 开发桥演示适配器）

一轮完整回合（思考块 + 工具行 + 流式正文 + 结论卡）：58 fps，2 次 long task（最长 145ms，dev 构建含 React 开发模式开销），JS 堆 ~36MB（dev）。**一轮回合约 270 个 DOM 元素、却只有 ~1300 字**——工具行、图标、按钮是 DOM 大户。

### 3.4 长对话压测（代理实验）

把一轮真实渲染好的回合 DOM 克隆 K 份放进对话滚动区（不经 React，所以**不含** React 重渲染成本，是下限），测强制重排（模拟拉窗口）、追加一段流式文字后的同步重排、以及每帧滚 40px 的帧时：

| 回合数 | DOM 元素 | 整页重排 | 流式追加重排 | 滚动帧时 p50 / p95 / 最差 |
|---|---|---|---|---|
| 1 | 842 | 1.2 ms | 0.5 ms | 16.7 / 16.8 / 50 ms |
| 50 | 14,058 | 24 ms | 0.6 ms | 16.7 / 33 / 133 ms |
| 200 | 54,454 | 137 ms | 7.6 ms | 83 / 133 / 600 ms |
| 500 | 135,170 | 340 ms | 11.2 ms | 233 / 1450 / 1450 ms |
| **500 + `content-visibility:auto`** | 135,214 | **6.8 ms** | **3.9 ms** | **16.7 / 50 / 50 ms** |

→ 50 轮以内基本无感；**200 轮以上开始明显卡**（软件渲染下）。只加一行 CSS `content-visibility:auto` 就把 500 轮的重排从 340ms 压到 7ms、滚动回到 60fps——这和 web.dev 报告的「初次渲染 232ms→30ms，约 7×」同一量级（[web.dev](https://web.dev/articles/content-visibility)）。

### 3.5 代码层面发现的热点（只读，未改）

1. **对话列表无虚拟化**，全仓无 `content-visibility` / 虚拟列表；长对话 DOM 线性增长（§3.4）。
2. `StreamingText`：每个段落定稿时把**整段已定稿的 head 重新交给 react-markdown 解析**（`memo` 只挡住同一字符串），超长回答是 O(n²) 解析；且每帧 `setShown` 触发重渲染。
3. 用户消息用了 framer-motion `layout="position"`：每次重渲染都要测量所有 layout 节点，长对话里会放大成本。
4. 主 JS 是 971KB 单 chunk（构建已告警）；设置页、导出、项目页等可懒加载。
5. CSS 483KB 主要是 400 个 `@font-face`；可只保留常用字重或改为本地系统字体回退 + 子集。

### 3.6 局限

Linux 软件渲染 ≠ Windows WebView2 + GPU；没测 Windows 进程组内存、电池、真实 IME、125/150% DPI；§3.4 绕过了 React，真实情况会更差一些；dev 构建数字偏高。

## 4. 对 TriWitness 的判断

**Web UI 是不是瓶颈？** 现阶段不是。60fps 稳定、空闲无 long task、首屏 ~480KB。真正的代价是：

- **常驻内存**：WebView2 一套进程，外部测量通常是几百 MB 级（估计，Windows 真机待测）。对开发者桌面工具可以接受，Claude/ChatGPT/Codex 都是同一类（甚至更重的 Electron）。
- **会咬人的场景**（按概率排序）：
  1. **很长的对话 / 长时间后台任务的推流**（DOM 无限增长）→ 200+ 回合可感知卡顿；
  2. **大 diff / 大日志**（几千行 patch 直接进 DOM、语法高亮在主线程）；
  3. **多路并发流式**（多个任务同时每帧 setState）；
  4. 超长单条回答的 Markdown 反复全量解析。

**Tauri 内的对策**（成本低、收益大，建议排进下一轮）：

| 对策 | 解决什么 | 成本 |
|---|---|---|
| 对话回合加 `content-visibility:auto; contain-intrinsic-size:auto 400px` | 长对话重排/滚动（实测 340ms→7ms） | 一行 CSS |
| 超过 ~100 回合再上真虚拟列表（如 TanStack Virtual），并保证"跟随到底"逻辑 | 长对话 DOM/内存 | 中 |
| 流式提交节流：网络 token 进缓冲，**每帧最多一次** commit；后台/不可见会话暂停动画（`document.hidden`、IntersectionObserver） | 多路并发、电池 | 低 |
| Markdown 增量：只解析"最后一个未定稿段落"，已定稿段落按块 memo 缓存 | 超长回答 O(n²) | 低～中 |
| 动画只用 `transform` / `opacity`（走合成器），避免动 `height/width/top`；慎用 framer `layout`，长列表关掉 | 帧节奏 | 低 |
| 大 diff：Rust 侧先切块/算 hunk、高亮放 Web Worker，前端虚拟化行 | 大 diff | 中 |
| 代码分割：设置/项目/导出懒加载；字体只留常用字重 | 启动、包体 | 低 |
| WebView2：只用一个 WebView 实例；最小化/后台时 `MemoryUsageTargetLevel=Low`（[MS 指南](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/performance)）；不要禁 GPU | 常驻内存 | 低（需 Rust 侧调用，Tauri/wry 是否暴露需确认） |

**什么时候才值得换原生？** 同时满足以下几条时：
- 产品变成**编辑器/终端级**（海量文本、120fps 滚动、输入延迟要 <10ms）；
- **常驻内存**成为卖点或硬约束（例如要常驻托盘、低配机器、企业瘦客户端）；
- 有余力维护多端原生或自研渲染（Zed/Warp 都花了数年）。
即便如此，更现实的路线是**局部原生**：例如把超大 diff/日志视图做成 Rust 渲染的独立面板，而不是整体重写。

## 5. 面试话术（可直接用）

> 「我们选 Tauri 而不是原生，是因为这类 agent 前台的瓶颈不在渲染器，而在**状态与 DOM 规模管理**。Anthropic、OpenAI 的桌面端都是 Web 技术，Zed、Warp 这类编辑器/终端才自建 GPU 渲染——因为它们的产品就是海量文本和 120fps。我在自己的 app 上实测：流式推流 60fps、p99 帧时 16.8ms；但长对话到 500 轮时整页重排 340ms、滚动掉到个位数 fps。加一行 `content-visibility:auto` 后重排降到 7ms、滚动回到 60fps。所以我的结论是：Web UI 的上限够用，关键是知道它在哪里会坏，以及怎么在不换栈的情况下修好。」

### 待办（不花钱）
0. ~~落地 §4 低成本对策~~ —— 已完成，见 §6。
1. Windows 真机测量：冷启动到首帧、空闲/工作时整个进程树（TriWitness.exe + msedgewebview2.exe 子进程）的 Private Bytes / Working Set、动画时 CPU/GPU，100/125/150% DPI，微软拼音/搜狗输入。
2. 落地 §4 前三项低成本对策，再用 `tools/perf-longchat.mjs` 回归。

## 6. 优化落地与前后对比（2026-10-11 下午）

Eva 批准后在 `apps/desktop` 落地了 §4 的对策。测量方法同 §3（box 上 Linux headless Chrome、软件渲染、生产构建 `vite preview`），**前后同一台机器、同一脚本**。
§3.4 的「克隆 DOM」代理实验绕过了 React，这里换成更真实的压测源：`?source=stress&rounds=N`（合成一个超长 agent 回合，每轮 = 思考增量 → 正文增量（段落 / 列表 / 代码块）→ 工具调用，事件流经真实的 订阅 → 折叠 → React 渲染 路径，¥0）；`repeat=K` 把一条正文重复 K 段，用来压超长单条回答。

### 6.1 改了什么

| # | 对策 | 实现 |
|---|---|---|
| 1 | `content-visibility:auto` | 对话块（思考 / 工具行 / 正文 / 气泡）和推流行的**根元素**加 `.cv-auto` / `.cv-line` + `contain-intrinsic-size: auto …`；放在根元素上，兄弟间 margin 折叠不变 |
| 2 | 虚拟列表 | `VirtualList`：块数 ≤150 全量渲染（靠 1 兜底）；>150 只挂视口 ±1200px，上下占位（量过用真高，没量过按类型估计）。贴底跟随 / 回到底部仍由 `useStickToBottom` 负责；往上翻的高度差由浏览器滚动锚定吸收。浏览器 Ctrl+F 本就被禁用（查找走 Ctrl+K），整条复制读数据不读 DOM |
| 3 | 流式节流 | `useEventFeed` 事件先进缓冲，**每帧最多一次 setState**（隐藏窗口改 250ms 定时器）；`mergeEvents` 有序追加 O(批)；`IncrementalFold` 让 `foldRun/foldTurn`、推流行映射只处理新增事件（原来每个事件都从头折叠，O(n²)）；块组件 memo；窗口隐藏时 `html[data-hidden]` 暂停全部 CSS 动画 |
| 4 | 增量 Markdown | `splitMdBlocks` 按顶层块切（不切代码围栏、缩进续行、引用式定义），每块独立 memo 解析；流式收尾不再整篇重解析、整块换 DOM。`StreamingText` 的 rAF 不再在 setState updater 里排帧 |
| 5 | 拆包 + 字体 | 设置 / 项目 / 作品页、Markdown 渲染器（react-markdown + remark-gfm）、PDF 导出（react-dom/server）懒加载并空闲预取；React、framer-motion 独立 vendor chunk。字体：去掉未使用的 JetBrains Mono 500 和西里尔 / 希腊 / 越南文切片；标题衬线体 Noto Serif SC 裁到 GB2312 + 常用标点（`scripts/subset-serif.py`，集外字回退到全覆盖的 Noto Sans SC），正文无衬线体不裁 |
| 6 | 动画 | 长回合（>40 块）关掉用户气泡的 framer `layout`；书写墨迹动画去掉 `filter: blur`（每字一层滤镜、逐帧重绘），保留 opacity/transform；琥珀→墨色的颜色过渡只作用于正在沉淀的最后两行（≤ 约 20 个字），是有意保留的品牌效果 |

### 6.2 前后对比

| 场景 / 指标 | 优化前 | 优化后 |
|---|---|---|
| **主 JS**（首屏应用代码） | 971 KB（gzip 306） | 177 KB（gzip 59）+ react 220 KB + motion 130 KB 独立 chunk |
| 首屏 JS 合计 | 971 KB（gzip 306） | 548 KB（gzip ≈182） |
| CSS | 483 KB | 446 KB |
| 字体（dist） | 400 个 / 11.33 MB | 366 个 / 8.34 MB（-26%） |
| `dist/` 合计 | 12.84 MB | 9.81 MB |
| 冷加载 DOMContentLoaded（本地 preview） | 134 ms | 66 ms |
| 首屏传输 | 481 KB | 355 KB |
| 书写推流回放 30s：fps / p99 | 59.9 / 16.8 ms | 59.9 / 16.8 ms（不变，本来就不卡） |
| 同上：DOM 节点 / 脚本耗时 | 1316 / 0.51 s | 738 / 0.33 s |
| **200 轮长回合**推流：fps / p95 / 掉帧 | 37.1 / 50 ms / 80 帧 | 59.3 / 16.7 ms / 2 帧 |
| 200 轮完成后：DOM 元素 / JS 堆 | 9,323 / 15.8 MB | 881 / 10.2 MB |
| 200 轮：整页重排 / 流式追加重排 | 22.9 / 5.7 ms | 1.0 / 0.7 ms |
| **500 轮长回合**推流：fps / p99 | 16.2 / 166.6 ms | 59.5 / 16.8 ms |
| 500 轮：long task 次数 / 总时长 | 314 次 / 26.4 s | 2 次 / 0.16 s |
| 500 轮：推完用时（受事件节奏限制，越接近 15.6s 越好） | 52.9 s | 15.7 s |
| 500 轮完成后：DOM 元素 / JS 堆 | 22,811 / 30.4 MB | 940 / 15.9 MB |
| 500 轮：整页重排 / 滚动 fps / 滚动 p95 | 68.4 ms / 51.3 / 33.4 ms | 0.7 ms / 60.5 / 16.8 ms |
| **超长单条回答**（150 段）推流：fps / 掉帧 | 38.4 / 53 帧 | 59.3 / 1 帧 |

解读：
- 真正的瓶颈不是渲染器，而是**每个事件都触发一次全量折叠 + 全量渲染**（O(n²)）。批量提交 + 增量折叠之后，500 轮时 long task 从 26 秒降到 0.16 秒。
- DOM 从「随回合线性增长」变成「只随视口大小」：500 轮完成后 940 个元素，与 200 轮几乎一样。
- 首屏代码量减半，冷加载 DCL 减半；字体少 3 MB，安装包预计相应变小（本轮按要求没重打安装包）。

### 6.3 验证
- vitest 全绿（新增 `incrementalFold`、`mdBlocks` 单测）；oxlint / tsc / vite build / i18n 检查 / `check:events` 通过；`cargo xwin check --tests` 通过（Rust 侧无改动）。
- e2e：`shoot-replay`、`test-guards`、`shoot-ui21`（36 项）、`shoot-ui21c`（46 项）全过；`shoot-live` / `shoot-chat` 里「审批卡出现」3 项失败，**在未改动的 HEAD 上同样复现**，与本次改动无关，已单列待查。
- 虚拟列表手动核对：300 轮回合流式中贴底、完成后停在底部；滚到中部 / 顶部每屏都有内容无空白；「回到底部」后间距 0、按钮消失。

### 6.4 已知边界
- 虚拟化模式（>150 块）下，条目改用 `flow-root` 包裹以便量高，思考块与正文之间的间距比全量模式多约 6px。
- 跨越很远（已卸载）条目的手动框选复制不可用；整条复制按钮不受影响。Claude 本身也只建议用复制按钮。
- 一条正在流式写出的超长代码块仍是每帧整段重解析（只在尾块里），之后可以对围栏内做行级增量。
