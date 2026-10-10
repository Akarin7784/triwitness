# Claude Desktop 交互对齐清单

原则：操作方式与 Claude Desktop 一一对应，不缺也不多。差异只放在审美和复验功能上。
没做好的功能也放真入口，点了提示“即将推出”，之后逐步补齐。

状态：**done** 已可用 · **stub** 入口在，点了提示即将推出 · **todo** 还没有入口

最后更新：2026-10-11（UI-21 第 2 轮）

## 输入框（Composer）

| Claude 控件 | 状态 | 说明 |
|---|---|---|
| 自动增高输入框，Enter 发送 / Shift+Enter 换行，输入法安全 | done | 最高 240px |
| 每个会话单独保存草稿 | done | localStorage `tw.drafts` |
| 发送 / 停止切换（Esc 停止） | done | 弹簧切换 |
| 语音听写按钮（输入框为空时） | stub | |
| “+” 菜单：添加文件或图片（Ctrl+U） | stub | 菜单和快捷键都在 |
| “+” 菜单：截图 / 网页搜索 / 深度研究 / 技能 / 连接器 / 插件 | stub | |
| 模型选择器（在输入框底部，Ctrl+Shift+I） | done | 只有 deepseek-flash；通义千问 / 智谱 GLM 灰显“稍后”；不出现 v4-pro |
| 思考强度子菜单（Effort，Ctrl+Shift+E） | done | 关/低/中/高 → thinking + reasoning_effort；经 tw-bridge 传给核心，选择会保存 |
| “更多模型” | stub | |
| 仓库签（对应 Claude 的项目 / 附件签） | done | 三证自有 |
| 风格（Styles） | stub | 在 + 菜单里 |
| Chat / Cowork 切换 | todo | 需要先确定三证里对应什么 |

## 消息流

| Claude 控件 | 状态 | 说明 |
|---|---|---|
| 逐字流式输出，柔和淡入，带光标 | done | 尊重“减少动态效果” |
| Markdown 渲染（列表、表格、代码块） | done | |
| 代码块复制 | done | |
| 思考块：边想边流，结束后折叠为“思考了 N 秒” | done | |
| 工具调用：紧凑可展开行，与正文交错 | done | |
| 自动滚到底；向上滚时暂停，并出现“回到底部” | done | |
| 复制回复 / 复制用户消息 | done | Ctrl+Shift+C 复制最后一条回复 |
| 重试 | done | 同一会话起新任务，作为新版本 |
| 编辑用户消息后重发 | done | 就地编辑，Enter 发送，Esc 取消；作为新版本 |
| 版本切换 ‹ 2 / 3 › | done | 编辑产生的版本显示在用户消息下，重试产生的显示在回复操作条上；侧栏不单列 |
| 赞 / 踩反馈（附文字） | done | 只存在本机（`tw.chats`），再点一次取消 |
| Artifacts 面板 | todo | 侧栏“作品”入口为 stub |

## 侧栏

| Claude 控件 | 状态 | 说明 |
|---|---|---|
| 新会话（Ctrl+Shift+O） | done | |
| 搜索会话（Ctrl+K） | done | 面板支持方向键和回车；第一项是新会话 |
| 会话（全部会话） | done | 打开搜索面板 |
| 项目 | stub | |
| 作品（Artifacts） | stub | |
| 星标分组 / 近期分组 | done | |
| 会话 … 菜单：星标 / 重命名 / 删除 | done | 重命名和删除各有对话框；删除时停掉仍在运行的任务 |
| 会话 … 菜单：加入项目 | stub | |
| 收起侧栏（Ctrl+Shift+S） | done | 收成图标窄栏，宽度用弹簧过渡 |
| 底部用户菜单：设置 / 快捷键 / 帮助 / 关于 | done | 帮助为 stub |
| 上一个 / 下一个会话（Ctrl+Shift+[ / ]） | done | |

## 顶部

| Claude 控件 | 状态 | 说明 |
|---|---|---|
| 自定义标题栏 | done | |
| 会话标题下拉：星标 / 重命名 / 删除 | done | |
| 会话标题下拉：加入项目 | stub | |
| 分享：复制链接 / 导出 Markdown / 导出 PDF | stub | 菜单在 |

## 设置（Ctrl+,）

| Claude 分区 | 三证对应 | 状态 | 说明 |
|---|---|---|---|
| 外观 | 常规 | done | 主题浅色 / 跟随系统 / 深色；对话字体宋体 / 黑体 / 系统；字号四档 |
| 外观：语言 | 常规 | done | 只有简体中文；English 灰显“即将推出” |
| 个人资料 | 个人资料 | done | 称呼、偏好，只存本机；还没注入提示词 |
| 功能 / 模型 | 模型 | done | 默认模型、思考强度、运行方式 |
| — | 模型：API 密钥 | done | 存系统凭据库（Windows 凭据管理器 / macOS 钥匙串）；前端只能写入、清除、查询状态，拿不到明文；真实模式启动核心时注入子进程环境变量。浏览器预览里显示“仅桌面应用” |
| 账单 | 预算 | done | 单任务上限 ¥0.10–1.00，只能调低，传给核心 `--max-cost`；高峰闸门图；允许高峰（只影响真实模式，`--allow-peak`）；账本仍是 mock |
| — | 权限：模式 | done | plan / ask / auto_edit / auto / full_access（无沙箱时禁选）→ `--permission-mode`（session 层） |
| — | 权限：无限制（勇士模式） | done | 红色选项；两步确认（勾选 + 输入“我了解风险”）；只对下一个任务生效，从不落盘；任务运行时显示常驻红色横幅 |
| — | 权限：规则列表 | done | 内置规则只读（拒绝 / 询问 / 允许）；“添加规则”为 stub |
| 开发者 | 沙箱 | done | 后端 自动 / Docker / 本机 → `--backend` |
| — | 沙箱：一键安装 Docker / 启用 WSL2 | stub | UI-19 |
| 连接器 | 连接器 | stub | GitHub / GitLab / Gitee |
| 隐私 | 隐私 | stub | 数据位置说明；导出、清除为 stub |
| 账户 | 关于 | done | 版本、快捷键入口；检查更新、开源许可为 stub |
| 扩展 | — | todo | |

## 快捷键（Ctrl+/ 列表）

| 快捷键 | 动作 | 状态 |
|---|---|---|
| Enter / Shift+Enter | 发送 / 换行 | done |
| Esc | 停止生成 | done |
| Shift+Esc | 聚焦输入框 | done |
| Ctrl+Shift+O | 新会话 | done |
| Ctrl+K | 搜索 | done |
| Ctrl+Shift+S | 收起侧栏 | done |
| Ctrl+Shift+C | 复制最后一条回复 | done |
| Ctrl+U | 添加文件或图片 | stub |
| Ctrl+, | 设置 | done |
| Ctrl+/ | 快捷键列表 | done |
| Ctrl+Shift+] / [ | 下一个 / 上一个会话 | done |
| Ctrl+Shift+I | 模型菜单 | done |
| Ctrl+Shift+E | 思考强度 | done |

macOS 上 Ctrl 对应 ⌘，列表里按 ⌘ ⇧ 显示。
