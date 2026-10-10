# Spec 003：Agent 循环与工具

- 状态：草稿｜负责人：Eva｜目标周：W1（最小版）→ W2（完整版）｜依赖：001、002
- 相关文档：04-detailed-design.md 第三节

> ⚠️ 核心模块：实现后必须有人写的设计说明 `docs/design/agent-loop.md`，面试时要能逐行讲清楚。

## 1. 背景

这是 TriWitness 的心脏：一个"模型 → 工具 → 观察 → 模型"的循环，加上工具注册、预算控制、死循环检测和完成契约。W1 先做单角色（Executor）最小版，能在沙箱里修好一个简单 bug；之后的 spec 在此之上加多角色和上下文工程。

## 2. 目标

1. `AgentLoop`：单角色运行，直到调用 `finish`、预算耗尽或被判定卡死。
2. `Tool` 协议与 `ToolRegistry`：JSON Schema 自动生成、参数校验、错误包装。
3. 核心工具（W1，ADR-0001 #2）：`read_file`、`write_file`（仅新建）、`edit_file`、`list_files`、`grep`（ripgrep）、`bash`、`run_tests`、`finish`。W2 增加 `git`、`notes`，合成 04 所说的“9 个核心工具 + finish”；`repo_map` / `lsp` 仅作消融开关；`ask_human` 在 W4。
4. 预算：人民币、输入 token、输出 token、回合数、墙钟时间五种上限（04 §8 拆分字段，ADR-0002），任一触发即停止；达到 `warn_ratio` 时提醒收尾。
5. 死循环检测器（三种信号，三级响应）。
6. 每一步写 `Step` 事件（交给 spec 005 持久化）。

## 3. 非目标

- 多角色编排、Planner / Reviewer（spec 010）。
- 上下文压缩、仓库地图（spec 007；本 spec 只做"工具结果截断"和固定前缀）。
- 并行工具调用（W1 串行执行；模型返回多个调用时按顺序执行）。

## 4. 接口

```python
class ToolContext(BaseModel, arbitrary_types_allowed=True):
    sandbox: Sandbox
    task: Task
    step_index: int
    budget: Budget


class ToolResult(BaseModel):
    ok: bool
    content: str  # 给模型看的文本（已截断）
    data: dict | None = None  # 结构化结果（写入轨迹，不进上下文）
    error_code: str | None = None


class Tool(Protocol):  # ADR-0001 #4
    name: str
    description: str  # 写给模型：何时用、何时不用、示例
    Params: type[BaseModel]  # 参数模型 → JSON Schema
    side_effects: Literal["none", "workspace", "external"]
    refetchable: bool  # 结果可被“工具结果清理”替换为占位符（read_file / grep / list_files 等）
    terminal: bool = False  # 调用成功即结束循环（finish）

    async def run(self, params: BaseModel, ctx: ToolContext) -> ToolResult: ...


class ToolRegistry:
    def register(self, tool: Tool) -> None: ...
    def schemas(self) -> list[dict]: ...  # 按名称排序，保证前缀稳定
    async def dispatch(self, call: ToolCallSpec, ctx: ToolContext) -> ToolResult: ...


class Budget(BaseModel):  # ADR-0002（eval 模式默认值）
    max_cost_cny: float = 0.8
    max_input_tokens: int = 3_000_000  # 含缓存命中
    max_output_tokens: int = 100_000
    max_turns: int = 100
    max_wall_seconds: int = 1800
    warn_ratio: float = 0.8
    # `tw run` / dogfooding：max_cost_cny=1.0、max_wall_seconds=2700


class LoopOutcome(BaseModel):
    status: Literal["finished", "budget_exhausted", "stuck", "error"]
    finish: FinishReport | None
    steps: int
    reason: str | None


class AgentLoop:
    def __init__(
        self,
        router: Router,
        registry: ToolRegistry,
        role: Role,
        system_prompt: str,
        budget: Budget,
        recorder: TrajectoryRecorder,
    ): ...
    async def run(self, task: Task, sandbox: Sandbox) -> LoopOutcome: ...
```

`finish` 工具参数（完成契约）：

```python
class ReproRef(BaseModel):
    path: str  # tests/tw_repro/test_issue_<n>.py（ADR-0001 #8）
    cmd: str  # 复现命令，如 "pytest -q tests/tw_repro/test_issue_87.py"


class FileChange(BaseModel):
    path: str
    kind: Literal["added", "modified", "deleted"]
    note: str = ""


class FinishReport(BaseModel):  # ADR-0001 #3（采用 04 §3.4）
    summary: str  # 改了什么、为什么
    changes: list[FileChange]
    repro: ReproRef | None
    tests_run: list[str]  # 运行过的测试命令
    tests_passed: bool
    confidence: float  # 0–1；风险分级规则“< 0.6”直接使用
    open_risks: list[str] = []
```

## 5. 行为细节

### 5.1 循环

```text
messages = [system(稳定前缀：角色提示 + AGENTS.md 摘要 + 工具说明), user(任务)]
while True:
    检查预算 → 超限则 budget_exhausted
    resp = router.complete(LLMRequest(role, messages, tools=registry.schemas()))
    记录 Step(model_call)
    if 没有 tool_calls:
        追加提醒 "请调用工具继续，或调用 finish 结束"；连续 3 次无工具调用 → stuck
        continue
    for call in resp.tool_calls:
        result = registry.dispatch(call)    # 参数错误 → ok=False，带修正提示
        记录 Step(tool_call)
        if call.name == "finish" and result.ok: return finished
    死循环检测 → 按级别处理
```

### 5.2 工具约定

- `bash`：参数 `command`、`timeout_s`（默认 120，最大 600）；在沙箱执行；返回 exit_code + 截断后的输出。禁止交互式命令（检测 `vim`、`less`、`top` 等直接拒绝并提示）。
- `read_file`：参数 `path`、`start_line`、`end_line`；带行号返回；单次最多 400 行。
- `edit_file`：参数 `path`、`old_str`、`new_str`；`old_str` 必须唯一匹配，否则返回 0 次或多次匹配的位置提示。
- `write_file`：仅用于新建文件；文件已存在时报错，提示用 `edit_file`。
- `grep`：ripgrep，参数 `pattern`、`path`、`glob`；W1 最多 100 条匹配（W2 增加 `context`、`max_matches` 与正则错误修正建议）。
- `list_files`：参数 `path`、`glob`、`max`（默认 200）；W2 起遵守 `.gitignore`。
- `run_tests`：参数 `selector`（可选）；用任务配置里的测试命令；解析 pytest 输出得到通过/失败列表放进 `data`。
- `finish`：参数校验失败时返回具体缺哪一项；`tests_passed=True` 但最近一次 `run_tests` 有失败时拒绝并提示。

### 5.3 工具结果截断

单个工具结果超过 8K token（按字符估算 ≈ 4 字符/token）时保留头 60% + 尾 40%，中间注明省略量，并把完整内容写到沙箱 `/workspace/.tw/outputs/<step>.txt`，提示模型可用 `read_file` 查看。

### 5.4 死循环检测

信号（最近 8 步窗口）：
1. 相同工具 + 相同参数（规范化后哈希）出现 ≥ 3 次；
2. 连续 5 次工具调用失败（`ok=False` 或非零退出码）；
3. 连续 6 步没有任何文件修改且没有新的读取目标。

响应：第一次 → 插入一条系统提醒（列出重复的动作，建议换思路）；第二次 → 回滚到最近一次 `run_tests` 通过数最多的快照并提醒；第三次 → `stuck` 结束。

### 5.5 错误处理

- 模型调用异常（`LLMUnavailable`）→ `error` 结束，记录原因。
- 工具内部异常 → 包装成 `ok=False`，`error_code="internal"`，不终止循环。
- 沙箱崩溃 → `error` 结束。

## 6. 验收标准

- [ ] AC1：用"脚本化假模型"（按预设顺序返回工具调用）跑通 read → edit → run_tests → finish，产生 `finished`，步数正确。
- [ ] AC2：`ToolRegistry.schemas()` 输出稳定（两次调用逐字节相同）；每个工具的 schema 都通过 JSON Schema 校验。
- [ ] AC3：参数类型错误时返回 `ok=False` 且 content 中包含字段名和期望类型。
- [ ] AC4：`edit_file` 在 0 次 / 2 次匹配时都返回可操作的错误提示。
- [ ] AC5：假模型连续 3 次相同 `bash` 调用 → 插入提醒；持续重复 → 最终 `stuck`。
- [ ] AC6：`Budget()` 默认值与 ADR-0002 一致；`max_cost_cny=0.01` 时，第一次模型调用后即 `budget_exhausted`。
- [ ] AC7：`finish(tests_passed=True)` 而最近一次 `run_tests` 失败 → 被拒绝。
- [ ] AC8：（集成 + 真实模型）只在 DeepSeek 空闲时段，在 `evals/tasks/dev/001-*` 上用 deepseek-flash 跑通并通过隐藏测试（允许重试 3 次中至少 1 次成功）。

## 7. 测试计划

- 单测：`FakeRouter`（脚本化响应）+ `FakeSandbox`（内存文件系统）覆盖 AC1–AC7。
- 集成：AC8 用 Docker + 真实 API（`-m live`）。

## 8. 评测影响

工具描述、截断阈值、死循环检测参数都是消融变量，必须从 `configs/harness/*.yaml` 读取，并写入 Trajectory 的 `harness_config`。

## 9. 开放问题

- 是否默认开启并行工具调用？→ W2 消融决定。
- `bash` 与专用工具是否重复？→ 保留两者，消融"只有 bash"对比"完整工具集"。

## 10. AI 实施提示

- 先写 `FakeRouter` 和 `FakeSandbox`，用它们驱动 TDD。
- 工具描述是给模型看的提示词，写在 `src/triwitness/tools/descriptions/*.md`，不要埋在代码字符串里。
- 不要在循环里直接拼厂商参数，一律通过 `Router`。

## 11. 变更记录

- 2026-10-10：初稿
- 2026-10-10：按 ADR-0001（W1 接口与路径）与 ADR-0002（预算与模型策略）修订：工具名（list_files/grep/bash）、Tool 协议（side_effects/refetchable/terminal）、finish 契约（04）、Budget 默认（0.8 等）。
- 2026-10-10：按 ADR-0005 修订：工具调用前经权限引擎判定（spec 006）；Windows 无沙箱且无 Git Bash 时以 `powershell` 工具替代 `bash`（工具列表随平台变化仅此一处）；被拒绝的调用以工具结果返回拒绝原因。
- 2026-10-10：W1-18～W1-21 实现（工具注册表、文件/命令工具、finish 契约、AgentLoop）。偏差：list_files / grep 在宿主机后端用 Python 遍历，其他后端用 find / grep，不依赖 ripgrep；死循环检测只实现“重复动作”和“连续失败”，“无进展”与二级回滚待 W1-25；轨迹先用最小 EventEmitter（W1-24 TrajectoryRecorder 未做）。AC1–AC7 用 FakeRouter / FakeSandbox 离线覆盖；finish 在最近一次 run_tests 失败后拒绝 `tests_passed=true`。
