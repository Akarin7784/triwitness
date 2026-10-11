# 更新记录

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。桌面端版本号用 SemVer（`0.3.0-preview`），核心 Python 包用 PEP 440（`0.3.0a1`）。
发布流程（`.github/workflows/release.yml`）会把下面对应版本的整节内容作为 GitHub Release 说明。

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

## [0.2.1] - 2026-10-11

Eva 0.2.0 真机反馈的 5 个问题和 3 条建议（权限四种模式、仓库选择对话框、纸书配色深色模式、长会话性能等），见 `apps/desktop/STATUS.md`。

## [0.2.0] - 2026-10-10

第一个 Windows 安装包（内部试用，不含 Python 核心）。
