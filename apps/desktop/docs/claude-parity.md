# Claude Desktop 交互对齐清单

原则：操作方式与 Claude Desktop 一一对应，不缺也不多。差异只放在审美和复验功能上。
没做好的功能也放真入口，点了提示“即将推出”，之后逐步补齐。

状态：**done** 已可用 · **stub** 入口在，点了提示即将推出 · **todo** 还没有入口

## 输入框（Composer）

| Claude 控件 | 状态 | 说明 |
|---|---|---|
| 自动增高输入框，Enter 发送 / Shift+Enter 换行，输入法安全 | done | 最高 240px |
| 每个会话单独保存草稿 | done | localStorage `tw.drafts` |
| 发送 / 停止切换（Esc 停止） | done | 用弹簧动画切换 |
| 语音听写按钮（输入框为空时） | stub | |
| “+” 菜单：添加文件或图片（Ctrl+U） | stub | |
| “+” 菜单：截图 / 网页搜索 / 深度研究 / 技能 / 连接器 / 插件 | stub | |
| 模型选择器（在输入框底部） | done | 只有 deepseek-flash；通义千问 / 智谱 GLM 灰显“稍后”；不出现 v4-pro |
| 思考强度子菜单（Effort） | done | 关/低/中/高 → thinking + reasoning_effort；经 tw-bridge 传到 core，选择会保存 |
| “更多模型” | stub | |
| 仓库签（对应 Claude 的项目 / 附件签） | done | 三证自有 |
| Chat / Cowork 切换 | todo | |

## 消息流

| Claude 控件 | 状态 | 说明 |
|---|---|---|
| 逐字流式输出，柔和淡入，带光标 | done | rAF 平滑显示，每段 6 字淡入；尊重“减少动态效果” |
| Markdown 渲染（列表、表格、代码块） | done | react-markdown + GFM |
| 代码块复制 | done | |
| 思考块：边想边流，结束后折叠为“思考了 N 秒” | done | |
| 工具调用：紧凑可展开行，与正文交错 | done | 展开看参数、输出、审批 |
| 自动滚到底；向上滚时暂停，并出现“回到底部” | done | |
| 复制回复 | done | |
| 重试 / 重新生成 | stub | 第二轮做 |
| 赞 / 踩反馈 | stub | |
| 编辑用户消息后重发（分叉 + 版本切换） | stub | 第二轮做 |
| 复制用户消息 | done | |
| Artifacts 面板 | todo | |

## 侧栏

| Claude 控件 | 状态 | 说明 |
|---|---|---|
| 新会话 | done | |
| 最近会话列表 | done | |
| 搜索会话（Ctrl+K） | todo | 第二轮做 |
| 收起侧栏（Ctrl+Shift+S） | todo | 第二轮做 |
| 会话菜单：星标 / 重命名 / 加入项目 / 删除 | todo | 第二轮做 |
| 项目 / Artifacts / 星标分组 | todo | 第二轮做入口 |
| 底部用户菜单 | todo | |

## 顶部栏

| Claude 控件 | 状态 | 说明 |
|---|---|---|
| 自定义标题栏 | done | |
| 会话标题下拉（重命名 / 星标 / 删除） | todo | |
| 分享 / 导出 | todo | |

## 设置（Ctrl+,）

| Claude 分区 | 三证对应 | 状态 |
|---|---|---|
| 外观（浅色/自动/深色，字体） | 常规：主题 / 字号 / 语言 | todo |
| 功能（Capabilities） | 模型：默认模型 / 思考强度 / API Key（系统钥匙串）/ 运行模式 | todo（运行模式已在 UI-10 做好） |
| — | 预算：上限 + 错峰闸门 | todo |
| — | 权限：模式（含红色“无限制”）+ 规则 | todo |
| 开发者 | 沙箱：后端，Docker / WSL2 一键入口 | todo |
| 连接器 / 扩展 | | todo（入口做 stub） |
| 账户 / 隐私 / 账单 | 关于 | todo |

## 快捷键

| 快捷键 | 动作 | 状态 |
|---|---|---|
| Enter / Shift+Enter | 发送 / 换行 | done |
| Esc | 停止生成 | done |
| Ctrl+Shift+O | 新会话 | todo |
| Ctrl+K | 搜索 | todo |
| Ctrl+Shift+S | 收起侧栏 | todo |
| Ctrl+Shift+C | 复制最后一条回复 | todo |
| Shift+Esc | 聚焦输入框 | todo |
| Ctrl+U | 上传文件 | todo（stub） |
| Ctrl+, | 设置 | todo |
| Ctrl+/ | 快捷键列表 | todo |
| Ctrl+Shift+] / [ | 下一个 / 上一个会话 | todo |
