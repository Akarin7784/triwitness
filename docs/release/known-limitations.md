# 已知限制（v0.3.x → v1 方向）

更新：2026-10-12（北京时间）。对应桌面端 0.3.2-preview / 核心 0.3.2a1。逐项状态见 [v1-inventory.md](v1-inventory.md)。

## GitHub 与发布（v1 范围）

- **不注册 GitHub App**（Eva 2026-10-12）。没有 Webhook、没有按任务签发的安装令牌、不会因 Issue 标签自动开工、也不会自动回帖 Issue。
- **默认产物是本地的**：分支 `tw/<run_id>`、`~/.triwitness/runs/<run_id>/pr.md`（PR 说明 + 证据包）、`patch.diff`。
- **可选开 PR**：你确认后，用本机已登录的 `gh` 或设置里的细粒度 PAT 推送并开 PR（`tw run --open-pr` / 桌面端「开 PR」）。只支持 github.com；不强推、不合并。
- CI 回流与失败返工在编排器里已有（轮询 check runs）；没有 App 时不能靠 Webhook 推送事件。

## 记忆与 Skill（spec 013，Eva 2026-10-12 已确认）

- `tw run` **默认读本仓库记忆**（`--no-memory` 可关）；评测 / Harbor / 基线从不读写记忆。
- 蒸馏结果只进候选区，须 `tw memory accept`；Skill 经门禁或（同仓库）人工审核后合入；监控相对基线掉 15 个百分点以上自动回滚。
- 导出只到 `.claude/skills` / `.opencode/skills` / `.agents/skills`（默认 `~/.triwitness/exports/`），**不写进你的代码仓库**。
- 桌面端尚未展示「本次用了哪些记忆」（见 `apps/desktop/STATUS.md` TODO）。

## 模型与费用

- **需要你自己的 DeepSeek API 密钥**：每条消息（包括闲聊）都是真实调用，计入本机账本。直接回复通常不到 ¥0.001；修复任务通常 ¥0.05–0.30。
- 只支持 DeepSeek `deepseek-flash`；Qwen / GLM、跨厂商互审在界面上是灰的。
- 真实模式按 DeepSeek 官方价计费（高峰 2×，照常可用、照实记账）。没有金额上限 / 高峰拦截 / 熔断；每个任务只有防失控上限（轮数、时限、token 兜底）。

## Agent 能力（相对早期预览的进展）

- 已有多角色编排（Planner / Executor / Reviewer）、计划确认、验证器与证据包、CI 失败返工、记忆与 Skill、安全网关（出网白名单 + 凭证占位符 + MCP 指纹）。默认 harness 仍可能是单角色长上下文配置，见 `configs/harness/`。
- 修的主要是 **Python 仓库**（复现测试与静态检查按 Python）；其他语言能改代码，验证会弱很多。
- **终测排行榜数字尚未冻结**（W8-01 未跑）；对外不要引用未发布的 Resolved@1。

## 环境（Windows）

- 需要 **Git for Windows**。内置核心不含你项目的依赖；跑测试用你项目自己的 Python 环境。
- 沙箱默认「无沙箱」（本机 + worktree）；Docker 需自备。WSL2 后端未做。
- **没有代码签名**（SmartScreen 会拦）；**没有自动更新**（「检查更新」只打开 Releases）；只有 x64 NSIS。

## 隐私

- 不收集遥测。数据在本机 `~/.triwitness`；API 密钥在系统凭据库。诊断包已脱敏但仍含代码片段——外发前请自查。
