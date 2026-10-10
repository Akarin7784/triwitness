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

> 架构文档（`02` / `04`）当前以 CLI 为主，未规定桌面栈。本应用是产品排面层，后端接线前全部用 mock 流。

## 快速运行（推荐先看 Web 预览）

```bash
cd apps/desktop
npm install
npm run dev
```

浏览器打开终端提示的地址（默认 **http://localhost:1420**）。右侧 **SSH · 书写推流** 会自动落笔；可暂停 / 重播。

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
    hooks/          # useWritingStream — 变时序落笔、暂停续写
    data/mock.ts    # 演示会话与 plan→execute→verify→review 日志
  src-tauri/        # Tauri 2 原生壳
```

## 先给 Eva 看什么

1. 打开应用，感受整体暖色与字体。
2. 盯右侧 **SSH · 书写推流**：字不是匀速蹦出，而是带停顿、淡入、行首墨晕与呼吸光标。
3. 点暂停 / 重播，体验温柔节奏。
4. 左侧切会话、中间发一条消息（仍为 mock 回复）。

后端 / 真实 SSH 接线是下一步，不阻塞排面打磨。
