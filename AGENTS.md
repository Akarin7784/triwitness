# AGENTS.md — 给 AI 编程助手的项目规则

> 本文件写给在本仓库里工作的 AI 编程助手（Cursor、Qwen Code、OpenCode、Claude Code 客户端、TRAE、Qoder 等）。人类贡献者也请遵守。  
> TriWitness 自己的 Planner 也会读取这个文件，所以请保持简洁、准确。

## 1. 项目是什么

TriWitness 是一个验证优先的后台 Coding Agent：Issue → 计划 → 复现 → 修复 → 干净沙箱验证 → 评审 → 带证据包的 PR。另有评测与消融平台。

**v0.1 只用 DeepSeek `deepseek-flash`**（思考 / 非思考），**永不**用 `deepseek-v4-pro`；评审是同厂商异构评审，Qwen / GLM 与跨厂商互审推迟（ADR-0002）。

设计文档：`docs/architecture.md`。**动手前先读对应的 `specs/NNN-*.md` 和 `docs/adr/`**（ADR-0001 接口与路径、ADR-0002 预算与模型策略，均已采纳；ADR-0005 权限与沙箱模式：终端用户默认无沙箱 + 权限引擎，开发 / CI / 评测用 Docker，见 spec 002、spec 006）。

## 2. 常用命令

```bash
uv sync                                   # 安装依赖
uv run pytest -q                          # 单元测试（不联网，强制 TW_LLM_MODE=replay）
uv run pytest -q -m integration           # 集成测试（需要 Docker；本 box 上用 sg docker -c "..."，无 Docker 时自动跳过）
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run tw --help
uv run tw eval --suite dev --limit 3      # 评测冒烟（会调用模型 API，花钱；只在空闲时段）
cd apps/desktop && npm ci && npm run build # 桌面端前端构建（不打安装包，安装包只在 Eva 要求时构建）
```

提交前必须通过：`ruff check`、`ruff format --check`、`pyright`、`pytest -q`。

## 3. 代码结构与边界

- `src/triwitness/core/`：数据模型和状态机。**其他模块只能依赖 core，不能反过来。**
- `src/triwitness/llm/`：所有和模型厂商有关的差异只能写在这里（适配器）。loop、角色里**禁止**出现 `if vendor == "deepseek"` 之类的分支。
- `src/triwitness/harness/`：agent loop 与上下文工程。不直接调用 Docker、不直接调用 HTTP。
- `src/triwitness/sandbox/`：唯一允许接触 Docker / E2B 的地方。
- `src/triwitness/tools/`：每个工具一个文件，实现 `Tool` 协议，必须有 JSON Schema 和单测。
- `src/triwitness/eval/`：评测代码**不得**把隐藏测试放进 Agent 沙箱。
- 价格、模型 ID、路由一律放在 `configs/`，代码里不写死。
- `apps/desktop/`：Tauri 2 + React 19 桌面端，只通过事件协议 `tw-events/1`（`docs/design/event-protocol.md`）和 `tw serve` 读取 core 数据；界面不加说明性文字。

### 已采纳的默认值（ADR-0001 / 0002）
- 工具（W1）：`read_file`、`write_file`（仅新建）、`edit_file`、`list_files`、`grep`、`bash`、`run_tests`、`finish`；W2 加 `git`、`notes`。
- finish：`summary`、`changes`、`repro{path,cmd}`、`tests_run`、`tests_passed`、`confidence`（0–1）、`open_risks`。
- Tool 协议：`Params`（pydantic）、`side_effects: none|workspace|external`、`refetchable`、`terminal`。
- 路径：评测结果 `evals/results/…`；`tw run` 轨迹 `~/.triwitness/runs/<run_id>/`；沙箱工作目录 `/workspace/.tw/`；复现测试 `tests/tw_repro/test_issue_<n>.py`；`--config configs/runs/*.yaml`。
- 预算（eval 单任务）：`max_cost_cny=0.8`、输入 3M、输出 100K、100 回合、1800s；`tw eval --max-total-cny` 默认 10；总额 ¥100。
- 高峰：北京时间工作日 9:00–12:00、14:00–18:00（2× 价），live / 批量默认只在空闲时段。

## 4. 编码规范

- Python 3.12；类型注解完整；pydantic v2 模型；异步 I/O 用 asyncio。
- 函数短小；公共函数写 docstring（中文或英文均可，同一文件保持一致）。
- 错误要结构化：自定义异常放 `core/errors.py`；给模型看的工具错误要说明"错在哪、怎么改"。
- 日志用标准 `logging` + OTel；不要 `print`。
- 不引入新依赖，除非 spec 里写了，或在 PR 描述里说明理由。

## 5. 测试规范

- 单测**不联网**：模型响应用 `tests/fixtures/llm/` 里录制的真实响应回放（`tests/conftest.py` 强制 `TW_LLM_MODE=replay` 并清掉密钥环境变量）。
- 真实 API 测试打 `@pytest.mark.live`，默认不跑，只在空闲时段手动运行。
- 新增或修改模型适配逻辑时，必须附上对应的录制响应和测试。
- 集成测试打 `@pytest.mark.integration`，需要 Docker。
- 修 bug 先写能复现的失败测试（本项目自己的理念，开发时也照做）。

## 6. 安全红线

- **永远不要**提交或打印 API key（`DEEPSEEK_API_KEY` 只从环境变量读）、`.env`、令牌；示例用 `.env.example`。
- 只允许 `deepseek-flash`；**禁止**调用 `deepseek-v4-pro` 或白名单外模型。
- 沙箱默认断网；不要为了让测试通过而放开网络。
- 不要在代码里读取宿主机的 `~/.ssh`、`~/.aws` 等目录。
- 不要修改 `evals/tasks/*/tests/`（隐藏测试）来让评测通过。
- 不要删除或跳过已有测试；确需修改时在 PR 描述里逐条说明理由。

## 7. 规格驱动开发（SDD）流程

1. 读 `specs/NNN-*.md`，如有不清楚的地方，先在 PR / 对话里提问，**不要自行假设**。
2. 先输出实现计划（文件列表、接口、测试清单），等人确认。
3. 先写测试，再实现。
4. 完成后对照 spec 的"验收标准"逐条自查，在 PR 描述里列出。
5. 如实现过程中改变了接口，同步更新 spec，并在 spec 的"变更记录"里写一行。

## 8. 完成的定义（Definition of Done）

- [ ] spec 的验收标准全部满足
- [ ] ruff / pyright / pytest 全绿
- [ ] 新代码有测试；核心模块有设计说明（`docs/design/*.md`）
- [ ] 涉及 harness 行为的改动：附上 dev 集评测前后对比
- [ ] `docs/ai-native-log.md` 新增一条记录（人来写，AI 可起草）

## 9. 提交与 PR

- 分支：`feat/NNN-short-name`、`fix/...`
- 提交信息：`feat(llm): add DeepSeek adapter (spec 001)`
- PR 描述包含：对应 spec、改动摘要、验收标准自查、测试结果、（如有）评测对比

## 10. 术语

- **证据包（Evidence）**：PR 附带的复现、测试、检查、风险、成本信息
- **F2P / P2P**：FAIL_TO_PASS / PASS_TO_PASS 测试
- **跨厂商约束**：Reviewer / Verifier 的模型厂商必须不同于 Executor（`vendor_policy=cross_vendor`，资金到位后启用；v0.1 为 `single_vendor`，证据包会标注）
- **稳定前缀**：为提高缓存命中，消息开头保持逐字节不变的部分
