# 三证桌面端 UI 全面改造计划：电子书 / Typora 阅读风格（v1 定稿）

> 状态：**已拍板**（2026-10-13）。范围：`apps/desktop`（Tauri + React）与 `site/`。
> 原则：交互与控件 **1:1 对齐 Claude Desktop**（不增不减），差异只在美学与验证功能（结论卡、证据、diff）。**浅色简约为默认主主题**（参考 Typora / Markdown 编辑器），夜间为次要主题。动画高质量但克制。

## 0. 已锁定决策（2026-10-13）

| # | 决策 | 来源 |
|---|---|---|
| 1 | **纸纹彻底删除，不留开关。** 护眼与简约优先；纸感只靠底色与字体。 | 蓝色大肥鱼 |
| 2 | **默认正文 16px。** 第 2 批「长时间阅读」再提供 17/18px。 | 蓝色大肥鱼 |
| 3 | **夜间卡片正文对比度 ≥ 7:1**：只提亮卡片上的文字色，**不压暗卡片底色**。 | 蓝色大肥鱼 |
| 4 | **分开发布**：git 自动初始化修复（已在 main `59fc73b`）单独合入；UI 批次 1 等 @真用户阿验 30 分钟走查通过后再单独发版。 | 蓝色大肥鱼 |
| 5 | **浅色简约为主**：参考 Typora 等 Markdown 编辑器；日间默认、少羊皮纸/旧书戏剧感；Markdown（标题/代码/引用/表格/分隔线）贴近 Typora 干净阅读 chrome（细边框、柔和代码底、标题字重克制）。夜间保留为次要主题。 | Eva |

## 1. 硬指标

| 项 | 目标 |
|---|---|
| 正文字号 | 默认 **16px**；长读模式（批 2）17 / 18px |
| 正文行高 | 1.7 |
| 行宽 | 对话列约 68 字/行（`max-width: min(68em, 100% - 2*--sp-6)`） |
| 日间（主） | 干净米白 / 冷灰白底 + 深灰棕字；禁用纯白 `#fff` / 纯黑 `#000`；少羊皮纸 sepia |
| 夜间（次） | 深胡桃底；**含卡片底上的正文** ≥ 7:1 |
| 对比度底线 | 正文 ≥ 7:1，次要文字 ≥ 4.5:1（日夜、所有可能底色） |
| Token 化 | 组件内禁止硬编码颜色，一律 CSS 变量（批 1 清对话路径；设置预览色块批 2） |
| 代码 | 等宽 JetBrains Mono；语法高亮降饱和；代码块柔和底、细边框（Typora 风） |
| 动效 | 默认「减少动效」，并始终尊重 `prefers-reduced-motion` |
| 纸纹 | **已删除**，无开关、无 SVG grain |

## 2. 现状审计（来源：`src/index.css`、`src/components/*`，改造前）

1. 日间对比过高（14:1），夜间卡片上正文约 6.9:1（不达标）。
2. 正文字号 14.5px；大量 `text-[10–12.5px]`。
3. `.app-grain` 纸纹 + 多道渐变 → **删除**。
4. 动效偏多偏长；默认应 reduced。
5. 消息列 `max-w-[720px]` 偏窄。
6. `--color-amber*` 实为蓝 → 增加 `--accent*` 别名，旧名保留一版。
7. Markdown：章首朱砂短线、偏重标题 → 改为 Typora 式克制标题（无装饰线、字重 600、细底边或无）。

## 3. 新设计 Token（已按 WCAG 重算）

### 3.1 日间「Typora 浅色」（默认主主题）

干净冷米白，少旧书黄；对标 Typora 默认阅读底。

| Token（逻辑名） | CSS 变量 | 值 | 对 bg 对比度 | 用途 |
|---|---|---|---|---|
| bg | `--color-parchment` | `#f7f5f2` | — | 主阅读底 |
| bg-deep | `--color-parchment-deep` | `#efeee9` | — | 略深底（侧栏过渡，纯色） |
| raised / cream | `--color-cream` / `--color-panel-raised` | `#fbfaf8` | — | 输入框、卡片、弹层 |
| panel | `--color-panel` | `#efeee9` | — | 侧栏、柔和代码底 |
| border | `--color-border` | `#d9d5cd` | — | 1px 分隔 |
| border-soft | `--color-border-soft` | `#e3e0d8` | — | 更淡边框 |
| text | `--color-ink` | `#3a3632` | **11.00**（panel 10.31 / raised 11.48） | 正文、标题 |
| text-soft | `--color-ink-soft` | `#4a4540` | **8.71**（panel 8.16） | 次要正文 |
| text-muted | `--color-sepia-muted` | `#6b6560` | **5.28**（panel 4.94） | 时间戳 ≥4.5 |
| sepia | `--color-sepia` | `#5c564f` | **6.55** | UI 次要标签 |
| accent | `--color-amber` / `--accent` | `#2f4a72` | **8.24** | 链接、主按钮、焦点 |
| ok / err / warn | sage / rose-ink / ochre | `#3a6341` / `#9a2a22` / `#7d5212` | 6.35 / 7.07 / 6.25 | 状态色 |

说明：正文约 11:1，比旧 14:1 柔和，仍明显高于 7:1，白天强光下不发灰。

### 3.2 夜间「深胡桃」（次要主题）

卡片底 **保持** `#2d261e`；**提亮**正文到 `#c4b59c`，使 raised 上 ≥ 7:1。

| Token | CSS 变量 | 值 | 对 bg / raised | 用途 |
|---|---|---|---|---|
| bg | `--color-parchment` | `#1f1a15` | — | 主阅读底 |
| panel | `--color-panel` | `#262019` | — | 侧栏、代码块 |
| raised | `--color-panel-raised` / cream | `#2d261e` | — | 卡片（**不压暗**） |
| border | `--color-border` | `#4a3e32` | — | 分隔线 |
| text | `--color-ink` | `#c4b59c` | **8.58 / 7.41** | 正文（卡片 ≥7.1） |
| text-strong | （标题可用 ink） | — | — | 标题可同 ink 或略亮 |
| text-soft | `--color-ink-soft` | `#cebfa8` | **9.57 / 8.27** | 次要正文 |
| text-muted | `--color-sepia-muted` | `#a3937d` | **5.77 / 4.99** | 次要 ≥4.5 |
| accent | `--color-amber` | `#9fb4d8` | **8.21** | 链接/焦点 |
| ok / err / warn | | `#97b99c` / `#e0907f` / `#d4a660` | ≥6.9 | 状态 |

> 计算：WCAG 2.x `(L1+0.05)/(L2+0.05)`。批 1 合入时加 vitest 断言表中关键对。

### 3.3 字号阶梯

| Token | px | 行高 | 用途 |
|---|---|---|---|
| `--fs-body` | **16**（批 2：17/18） | 1.7 | 消息正文、输入框 |
| `--fs-ui` | 14 | 1.5 | 按钮、侧栏、工具行 |
| `--fs-meta` | **13**（最小） | 1.45 | 时间戳、徽标、Tip、kbd |
| `--fs-code` | 14 | 1.6 | 代码块 / diff |
| `--fs-h3/h2/h1` | 17 / 19 / 22 | 1.4 | Markdown 标题（克制） |
| `--fs-display` | 26 | 1.3 | 空状态欢迎语 |

### 3.4 Markdown（Typora 风）

- 标题：无朱砂装饰线；`font-weight: 600`；h1/h2 仅极淡底边或无边；字号见上表。
- 代码块：`background: var(--color-panel)`，`border: 1px solid var(--color-border-soft)`，圆角 8px，内边距宽松；行内 code 同柔和底。
- 引用：左边 3px `--border`，文字 `--sepia`，无重阴影。
- 表格：细边框 `--border-soft`，表头略用 panel 底。
- `hr`：单线 `--border-soft`，上下留白。
- 正文 serif 可保留；UI sans。段距 `0.8em`，列表项 `0.35em`。

### 3.5 纹理 / 渐变

- **删除** `--paper-grain`、`.app-grain` 多层背景、`.stream-paper` / `.titlebar` 渐变 → 纯色 `--color-parchment` / `--color-panel`。
- **无开关、无回退**。

### 3.6 动效

- 默认 `--motion: reduced`（或 `data-motion="reduced"`）。
- reduced：≤160ms 透明度；流式直接出字；静态光标；无 shimmer 无限循环。
- `prefers-reduced-motion: reduce` 强制 none。

### 3.7 焦点

- 全局 `:focus-visible { outline: 2px solid var(--color-amber); outline-offset: 2px }`。

## 4. 分批范围

### 批次 1：对话主界面（本分支 `ui/ebook-batch1`）

色板 + Typora Markdown + 消息列 + 流式降动效 + 结论/审批卡 + 侧栏/标题/状态栏 + 输入区；删纸纹；16px/1.7；夜间卡片字提亮。

### 批次 2：设置与主题

设置 9 分区；主题预览；**长时间阅读**（17/18px、行高 1.8、动效 reduced）；设置页预览色块改 token。

### 批次 3：其他页面

项目 / 作品 / 会话管理 / 对话框 / 菜单。

### 批次 4：`site/` 视觉对齐。

## 5. 验收标准（批次 1 优先项标 ★）

1. ★ 对话路径组件无 `text-[10–12.5px]`；CSS Tip/chip/kbd/ctx ≥13px。
2. ★ 正文 16px / line-height 1.7；列宽约 68em。
3. ★ 无阅读区纹理/渐变；无 `#fff`/`#000` 作文字或大面积底。
4. ★ 夜间 ink 在 panel-raised 上 ≥ 7:1（表值 −0.05）。
5. ★ 默认 motion=reduced；系统减少动画时无装饰动画。
6. ★ Typora 风 Markdown：无标题朱砂线；柔和代码底。
7. ★ Tab 焦点环可见（Composer → 发送 → 侧栏）。
8. ★ vitest + `tsc -b` 全绿。
9. 全仓最小字号 / 硬编码 hex 清零：批 2–3 收尾。
10. 长读开关：批 2。
11. site token 一致：批 4。
12. 长对话滚动：阿验走查 + Performance 抽查。

## 6. 真用户 30 分钟走查（@真用户阿验）

前提：批次 1 分支或安装包；日/夜各 15 分钟；100%/125% 缩放。清单同前版（首印象、长对话、任务与验证、错误空态、夜间、减少动画、键盘焦点）。另加：

- [ ] 日间是否像 Typora：干净、少「旧书黄」、代码块柔和不抢戏
- [ ] 夜间卡片正文是否清晰（不发灰、不刺眼）

输出：通过 / 问题（严重度）/ 建议；疲劳感 1–5（日、夜）。

## 7. 节奏与发布

1. **git 自动初始化**：已单独在 main（`59fc73b`），先发。
2. **批次 1**：本分支开发 → 测试 → 交阿验走查 → 修问题 → **单独发版**。
3. 批次 2 → 3 → 4，每批走查后再进下一批。

## 8. 开放项（已关闭）

原 §6 四问均已拍板，见 §0。无新的阻塞拍板项。

## 代码高亮色板（批次 1 合并前补，2026-10-13）

highlight.js core（本地打包，随 Markdown 懒加载 chunk；python/ts/js/bash/json/diff/yaml/ini(toml)/rust/xml/css），未知语言不猜、按纯文本。代码底 = `--color-panel`（日 `#efeee9` / 夜 `#262019`），对比度按 WCAG 相对亮度计算：

| token | 日间 | 对比 | 夜间 | 对比 |
|---|---|---|---|---|
| 正文 | `#3a3632` | 10.31 | `#c4b59c` | 8.01 |
| keyword | `#7a4a6e` | 5.96 | `#c9a3bc` | 7.25 |
| string / addition | `#4f6b3a` | 5.17 | `#a9c18f` | 8.22 |
| number / attr | `#8a5a2b` | 5.05 | `#d9ae7e` | 7.91 |
| comment（斜体） | `#6b645e` | 5.01 | `#a39682` | 5.56 |
| title / function | `#3d5a80` | 6.08 | `#9db5d6` | 7.69 |
| built_in / type | `#2f6a68` | 5.34 | `#8fbcb8` | 7.72 |
| meta / tag | `#7a6648` | 4.73 | `#c2ad8c` | 7.41 |
| deletion | `#9a3f36` | 5.76 | `#d99a8c` | 6.87 |
