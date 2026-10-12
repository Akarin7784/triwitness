# 架构决策记录（ADR）

| 编号 | 文件 | 主题 |
|---|---|---|
| 0000 | [0000-record-architecture-decisions.md](0000-record-architecture-decisions.md) | 采用 ADR |
| 0001 | [0001-w1-interfaces-and-paths.md](0001-w1-interfaces-and-paths.md) | W1 接口与路径 |
| 0002 | [0002-budget-and-model-policy.md](0002-budget-and-model-policy.md) | 预算与模型策略（0.3.2 起预算控制已移除，账本保留） |
| 0003 | [0003-python-and-thin-harness.md](0003-python-and-thin-harness.md) | Python + 自研 thin harness（不选 LangGraph） |
| 0005 | [0005-permissions-and-sandbox-modes.md](0005-permissions-and-sandbox-modes.md) | 权限与沙箱模式（Docker 优先于 E2B） |
| 0006 | [0006-routing.md](0006-routing.md) | 模型路由 |
| 0007 | [0007-default-reviewer-checklist.md](0007-default-reviewer-checklist.md) | 默认 Reviewer = checklist_t10 |

缺 0004（命名）见 TASKS W1-02 延后项。Temporal 取舍见 architecture 编排章节（进程内状态机，不用 Temporal）。
