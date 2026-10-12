"""记忆与技能（spec 013，W6）：仓库事实 / 经验片段 / Skill 的存储、使用、蒸馏、检查、门禁、监控与导出。

存储格式对齐 Cognition 开放的 Agent Memory Repo 规范（git 仓库 + Markdown，`MEMORY.md` 为入口，一行一条，
行尾 `[source: …; added: YYYY-MM-DD]`），Skill 遵循 Agent Skills 规范（`SKILL.md`，版本等写在 `metadata`）。
评测 / 自动化会话默认不读不写记忆（`memory_allowed`）。
"""
