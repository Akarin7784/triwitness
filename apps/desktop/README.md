# TriWitness Desktop · 三证

验证优先的编程 Agent 桌面壳。布局参考 Claude Desktop（左侧会话 / 中间对话 / 右侧活动流），视觉走**暖色文字文学风**：羊皮纸底、espresso 墨色、琥珀点缀；动画克制温柔。

## 技术选型

| 层 | 选择 | 理由 |
|---|---|---|
| 壳 | **Tauri 2** | 体积小、内存省、原生 Windows 窗口；前端仍是 Web 技术，易做精致排版 |
| UI | **React 19 + TypeScript + Vite 8** | 组件化、热更新快，适合打磨交互 |
| 样式 | **Tailwind CSS 4** | 设计 token 集中（羊皮纸 / 琥珀 / 墨色），改气质成本低 |
| 动效 | **CSS + framer-motion** | 书写感主要靠自研时序；motion 只做进度条等轻量过渡 |
| 字体（本地打包，离线可用） | **Noto Serif SC**（标题）+ **Noto Sans SC**（界面）+ **JetBrains Mono**（SSH 流）；Windows 回退 Segoe UI / 微软雅黑 / Cascadia | 衬线标题撑起「文学感」，无衬线保证可读，等宽留给终端字迹 |

> 事件来源统一走 **tw-events/1**（`schemas/tw-events-1.schema.json`，规格见 `docs/design/event-protocol.md`）。后端接线前，默认回放仓库里的 golden fixture（`evals/fixtures/events/*.jsonl`）。

## 快速运行（推荐先看 Web 预览）

```bash
cd apps/desktop
npm install
npm run dev
```

浏览器打开终端提示的地址（默认 **http://localhost:1420**）。右侧 **SSH · 书写推流** 会自动落笔；可暂停 / 重播。左侧「近期」里三条 #87 就是三份 fixture（✓ 成功 / × 失败 / 钱币 触及安全上限），点击即可切换。

| URL 参数 | 作用 |
|---|---|
| `?source=fixture:success` · `fixture:failure` · `fixture:budget_exceeded` | 选择回放哪份 fixture（默认 success） |
| `?source=mock` | 旧的演示日志（已包装成 tw-events/1 事件） |
| `?speed=4` | 回放倍速（默认 1.5；单个空档最长约 3.2 秒） |

```bash
npm test               # vitest：解析 / 映射 / 回放源 / URL 参数 / 生成类型是否过期
npm run gen:events     # schema 改了之后重新生成 src/data/tw-events.gen.ts
npm run check:events   # 只检查生成文件是否过期（CI 在跑）
```

## Windows 安装包

已从 Linux 交叉编译出 `release/TriWitness_0.1.0_x64-setup.exe`。完整构建步骤见 [docs/WINDOWS_BUILD.md](docs/WINDOWS_BUILD.md)。

## Windows 原生窗口（Tauri）

在 **Windows** 上安装 [Rust](https://rustup.rs/) 与 WebView2 后：

```bash
cd apps/desktop
npm install
npm run tauri:dev      # 开发
npm run tauri:build    # 产出安装包（msi / nsis）
```

Linux / CI 盒子上若缺 WebKitGTK，请先用 `npm run dev` 预览 UI；原生打包在 Windows 开发机完成即可。

## 目录

```
apps/desktop/
  src/
    components/     # Sidebar · Chat · Activity · WritingStream（核心）
    hooks/          # useWritingStream（落笔） · useEventFeed（订阅事件源） · useFixtureCatalog
    data/
      tw-events.gen.ts  # 由 schema 生成的类型（勿手改）
      events.ts         # 解析 / 校验 JSONL，未知 kind 保留但不渲染
      mapEvent.ts       # 事件 → 推流行 / 角色点 / 状态 chip / 费用 chip（event-protocol §3）
      sources/          # EventSource 接口 · FixtureSource · MockSource
      mock.ts           # 旧演示日志（mock 源用）
  scripts/gen-event-types.mjs
  tools/            # shoot.mjs · shoot-replay.mjs · test-guards.mjs（puppeteer 截图与回归）
  src-tauri/        # Tauri 2 原生壳
```

## 先给 Eva 看什么

1. 打开应用，感受整体暖色与字体。
2. 盯右侧 **SSH · 书写推流**：字不是匀速蹦出，而是带停顿、淡入、行首墨晕与呼吸光标。
3. 点暂停 / 重播，体验温柔节奏。
4. 左侧切换三条 #87：状态 chip、费用 chip、对话都跟着笔尖一起推进。
5. 悬停费用 chip 看缓存命中率和高峰价调用数。

下一步是把 FixtureSource 换成连编排器的 SSE 源（同一个 EventSource 接口）。
