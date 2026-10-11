# 更新记录

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。桌面端版本号用 SemVer（`0.3.1-preview`），核心 Python 包用 PEP 440（`0.3.1a1`）。
发布流程（`.github/workflows/release.yml`）会把下面对应版本的整节内容作为 GitHub Release 说明。

## [0.3.1-preview] - 2026-10-11

### 变更（不兼容）
- **正式版移除演示模式**：安装包（前端 + 内置 `tw.exe`）不再包含演示适配器、演示运行方式、侧栏里的录制回放和任何「演示」选项 / 签；设置里的“运行方式”去掉，应用始终用真实模型（deepseek-flash）。脚本化模型 / 回放只留在源码里给测试和开发构建用（PyInstaller 排除并在构建时校验，前端只在 `import.meta.env.DEV` 下，CI 扫描正式版前端包）。打包后的 `tw.exe run --demo` 直接报“正式版不含演示模式”。
- **需要 DeepSeek API 密钥**：首次打开（凭据库里没有密钥）会弹出引导，粘贴密钥存进系统凭据库，附“去 DeepSeek 开放平台创建密钥”链接；没填密钥就发送也会弹它，而不是让任务失败。

### 新增
- **对话轮（像 Claude 一样）**：每条消息先由模型决定直接回答还是开始干活。问候 / 感谢 / 问题直接回复（没有工具、补丁、证据、结论卡，状态签显示“已回复”）；明确要求修改且已选仓库才转成仓库任务；没选仓库就请你先选一个。提示词 `prompts/chat.md`（v1），对话调用记入账本（类别 `chat`），受高峰闸门与预算上限约束。
- **多轮会话**：同一会话里继续发消息就是跟进，核心沿 `turn.json` 链带上最近 20 轮历史（`tw run --jsonl --parent-run <run_id>`）；之前各轮显示在上面，重试 / 编辑只作用于最后一轮。
- 事件 `user_message` / `turn_finished`（tw-events/1 新增 kind，旧轨迹照常显示）；桥接结果多了 `kind`（`chat` / `task`）和 `reply`。
- 高峰时段被拒时给出可操作的提示（桥接 `error.code = peak_blocked`，去 设置 → 预算 允许高峰调用）。
- 测试用本机 OpenAI 兼容模拟服务（`packaging/mock_llm.py`）+ 仅限 127.0.0.1 的 `TW_LLM_BASE_URL_OVERRIDE`：CI 和打包冒烟用它跑真实适配器 → SSE 流式 → 对话轮 → Executor 全链路（「你好」直接回复、多轮复述、未选仓库、一个小任务），¥0、不需要密钥。

### 移除
- 前端的演示 / 回放 / 压测来源和“运行方式”设置（开发构建仍可用）。

## [0.3.0-preview] - 2026-10-11

第一个公开预览版。

### 新增
- **安装包自带核心**：核心用 PyInstaller 打成 onedir（`tw.exe` + `_internal/`），作为 Tauri 资源装到 `<安装目录>\core\`。桌面端先找内置核心，找不到再退回 `TW_CORE` / PATH 上的 `tw` / `python -m triwitness`（开发用）。不需要另装 Python。
- **预算页接真实账本**：设置 → 预算 和状态栏余额改为读本机 `~/.triwitness/ledger.sqlite`（新命令 `tw budget --json`，只读、不联网）；没连上核心时显示“—”，不再显示示例数据。
- **结论卡交付按钮**：“复制 PR 说明”“打开运行目录”。
- **检查更新**：打开 GitHub Releases 页面（预览版不自动更新）。
- Windows 打包 CI（`package-windows.yml`）：在 windows-latest 上构建核心和 NSIS 安装包，对打包后的 `tw.exe` 做冒烟（`--version`、`budget --json`、两次 `run --demo --jsonl` 往返），再静默安装一遍、对装好的核心再冒烟一次，安装包和 sha256 作为 artifact 上传。
- 打 `v*` 标签时的发布流程（`release.yml`）：构建安装包，从本文件取说明，创建**草稿** Release（附安装包和 `.sha256`）。
- ADR-0006（单厂商路由与默认 harness）采纳。

### 变更
- **如实表述交付**：界面、README、文档统一为“生成本地分支 + PR 说明”；状态名“待批 PR / PR 已开”改为“待确认交付 / 分支已就绪”。TriWitness 目前不推送、不在 GitHub 上创建 PR。
- 版本号：桌面端 0.2.1 → 0.3.0-preview；核心 0.0.1 → 0.3.0a1。界面版本号集中在一处。
- README 重写（安装、SmartScreen、快速开始、权限模式、成本、已知限制、路线图）。

### 修复
- 冻结（打包）后的核心能正确找到 `configs/`（风险策略、模型、价格），也能用 `tw.exe -m unittest` 跑演示仓库的测试。
- 预算页账本按时间从新到旧排序。
- Windows：核心在 PowerShell / 桌面端环境里起任务时可能卡在“查找 Git Bash”（`git --exec-path` 超时后被管道拖住，永不返回）；现在先按 PATH 上的 git 位置和常见安装目录找 bash.exe，最后才问 git，并且不再用管道读它的输出。

## [0.2.1] - 2026-10-11

Eva 0.2.0 真机反馈的 5 个问题和 3 条建议（权限四种模式、仓库选择对话框、纸书配色深色模式、长会话性能等），见 `apps/desktop/STATUS.md`。

## [0.2.0] - 2026-10-10

第一个 Windows 安装包（内部试用，不含 Python 核心）。
