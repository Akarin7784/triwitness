# Spec 001：模型适配层与网关

- 状态：草稿｜负责人：Eva｜目标周：W1｜依赖：无
- 相关文档：04-detailed-design.md 第五节


> **v0.1 范围（ADR-0002，已采纳）**：只实现 `DeepSeekAdapter`；模型白名单仅 `deepseek-flash`（= `deepseek-v4.1-flash`，思考 / 非思考），**永不**路由 `deepseek-v4-pro`。`QwenAdapter` / `GLMAdapter` 与跨厂商路由推迟到资金到位（TASKS DF-01～DF-04），下文相关内容保留为最终目标，对应验收标准标 ⏸。

## 1. 背景

TriWitness 只用 DeepSeek、Qwen、GLM 三家模型。三家都提供 OpenAI 兼容接口，但在思考模式、工具调用约束、缓存计费上差异很大，如果把这些差异散落在 agent loop 里，代码会很快失控，也没法做公平的评测对比。本 spec 把所有厂商差异关进 `src/triwitness/llm/`。

## 2. 目标

1. 统一的 `LLMRequest` / `LLMResponse` / `Usage` 数据结构。
2. 三个适配器：`DeepSeekAdapter`、`QwenAdapter`、`GLMAdapter`，处理请求构造、历史预处理、响应解析、用量归一。
3. 角色路由器 `Router`：按 `configs/models.yaml` 选模型；支持回退链；强制跨厂商约束。
4. 价格表 `configs/pricing.yaml` 与计价函数（含 DeepSeek 高峰 / 空闲时段）。
5. 两种传输：经 LiteLLM Proxy（默认）或直连厂商 OpenAI 兼容端点（降级）。

## 3. 非目标

- 不做流式输出给终端（W1 只用非流式；内部可以用流式聚合）。
- 不做 embedding、视觉输入。
- 不做自动按难度路由（之后的 spec）。

## 4. 已核对的厂商事实（2026-10-10）

| | DeepSeek | Qwen（百炼） | GLM（智谱） |
|---|---|---|---|
| 模型 ID | `deepseek-flash` | `qwen3.8-max`、`qwen3.8-flash` | `glm-5.3`、`glm-5.3-flash`、`glm-4.7-flash`（免费） |
| Base URL | `https://api.deepseek.com` | `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`（旧 `https://dashscope.aliyuncs.com/compatible-mode/v1` 仍可用） | `https://open.bigmodel.cn/api/paas/v4` |
| 思考开关 | `extra_body={"thinking":{"type":"enabled"/"disabled"}}`，`reasoning_effort` low/high/max | `extra_body={"enable_thinking": bool}` | 始终开启；只能设 `reasoning_effort` low/high/max（默认 max） |
| 关键约束 | 带 `tools` 时，**之前所有 assistant 消息的 `reasoning_content` 必须回传**，否则 400；思考模式下 temperature 不生效 | 思考模式下 `tool_choice` 不能是 `"required"` 或指定函数（会报错）；支持 `parallel_tool_calls` | temperature 取值 (0,1)，不支持 0；通过百炼调用时需 `tool_stream`（glm-5.3 默认 true） |
| 环境变量 | `DEEPSEEK_API_KEY` | `DASHSCOPE_API_KEY`（按地域绑定） | `ZAI_API_KEY` |
| LiteLLM 前缀 | `deepseek/` | `dashscope/` 或 `qwen_ai_platform/` | `zai/` |

来源：DeepSeek [价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing)、[思考模式](https://api-docs.deepseek.com/guides/thinking_mode)；百炼 [OpenAI 兼容](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)、[Function Calling](https://help.aliyun.com/zh/model-studio/qwen-function-calling)；智谱 [GLM-5.3](https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3)、[OpenAI 兼容](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)；LiteLLM [DeepSeek](https://docs.litellm.ai/docs/providers/deepseek)、[Z.AI](https://docs.litellm.ai/docs/providers/zai)、[QwenCloud](https://docs.litellm.ai/docs/providers/qwencloud)。

**实测（2026-10-10 周六，空闲价，6 次调用共 ¥0.0054）**：`/models` 只列出 `deepseek-flash`（DeepSeek-V4.1-Flash，1M 上下文）与 `deepseek-v4-pro`；`served_model` 返回 `deepseek-flash`；用量字段为 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`（同时有 OpenAI 风格 `prompt_tokens_details.cached_tokens`），推理 token 在 `completion_tokens_details.reasoning_tokens`（非思考模式不返回）；约 3.5K token 的稳定前缀第二次请求命中 3328/3523（94%）。录制见 `tests/fixtures/llm/deepseek/`。

**实现时必须先用真实调用验证上表**（尤其是 GLM 和 Qwen 的推理内容回传规则、各家缓存命中字段名），并把响应录制为 fixture。

## 5. 接口

```python
# src/triwitness/llm/types.py
class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    reasoning_content: str | None = None  # 原样保存，由适配器决定是否回传
    tool_calls: list[ToolCallSpec] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class LLMRequest(BaseModel):
    role: Role  # 用于路由和记账
    messages: list[Message]
    tools: list[dict] | None = None  # OpenAI function 格式
    tool_choice: Literal["auto", "none", "required"] | dict = "auto"
    thinking: bool = True
    effort: Literal["low", "high", "max"] | None = None
    max_output_tokens: int | None = None
    response_schema: dict | None = None  # 期望的结构化输出（用于校验，不强依赖厂商能力）


class LLMResponse(BaseModel):
    message: Message
    usage: Usage
    served_model: str | None
    finish_reason: str | None
    raw: dict  # 原始响应（落盘到产物，不进上下文）
    degraded: list[str] = []  # 例如 ["tool_choice_required->auto"]


# src/triwitness/llm/adapter.py
class ModelAdapter(Protocol):
    vendor: Vendor

    def capabilities(self, model: str) -> Caps: ...
    def prepare_history(self, msgs: list[Message], has_tools: bool) -> list[dict]: ...
    def build_request(self, model: str, req: LLMRequest) -> dict: ...
    def parse_response(self, raw: dict) -> LLMResponse: ...
    def normalize_usage(self, raw_usage: dict) -> Usage: ...


# src/triwitness/llm/router.py
class Router:
    async def complete(
        self,
        req: LLMRequest,
        *,
        executor_vendor: Vendor | None = None,
        mode: Literal["background", "eval"] = "background",
    ) -> LLMResponse: ...


# src/triwitness/llm/pricing.py
def price_call(vendor: Vendor, model: str, usage: Usage, at: datetime) -> tuple[float, bool | None]:
    """返回 (人民币费用, 是否高峰)。高峰判断仅对 DeepSeek 有效，时区为 Asia/Shanghai。"""
```

`configs/models.yaml` 示例：

v0.1 实际配置（单厂商模式）：

```yaml
transport: direct             # direct | litellm（LiteLLM 在 W2-01 接入）
vendor_policy: single_vendor  # single_vendor | cross_vendor（资金到位后启用）
allowed_models: [deepseek-flash, deepseek-v4.1-flash, deepseek-v4-flash]   # 白名单；deepseek-v4-pro 永不允许
roles:
  executor:   {model: deepseek/deepseek-flash, thinking: true, effort: high}
  planner:    {model: deepseek/deepseek-flash, thinking: true}
  verifier:   {model: deepseek/deepseek-flash, thinking: true}
  reviewer:   {model: deepseek/deepseek-flash, thinking: true, effort: max, variant: adversarial}
  summarizer: {model: deepseek/deepseek-flash, thinking: false}
```

最终目标（资金到位后，`vendor_policy: cross_vendor`）：

```yaml
transport: litellm            # litellm | direct
litellm_base_url: http://localhost:4000
roles:
  executor:   {model: deepseek/deepseek-flash, thinking: true, effort: high,
               fallback: [zai/glm-5.3, dashscope/qwen3.8-max]}
  planner:    {model: dashscope/qwen3.8-max, thinking: true,
               fallback: [zai/glm-5.3, deepseek/deepseek-flash]}
  reviewer:   {model: zai/glm-5.3, effort: high, fallback: [dashscope/qwen3.8-max]}
  verifier:   {model: dashscope/qwen3.8-flash, thinking: true, fallback: [zai/glm-5.3-flash]}
  summarizer: {model: dashscope/qwen3.8-flash, thinking: false, fallback: [deepseek/deepseek-flash]}
constraints:
  different_vendor_from_executor: [reviewer, verifier]
```

## 6. 行为细节

1. **历史预处理**：
   - DeepSeek：请求带 `tools` 时，把每条 assistant 消息的 `reasoning_content` 原样带上；不带 `tools` 时可以省略。
   - Qwen、GLM：按各自文档处理（实现前先查"传递思考过程"相关文档并录制验证）。
2. **tool_choice 降级**：如果目标模型在当前模式下不支持 `required` 或指定函数（Qwen 思考模式），改为 `auto`，并在 `LLMResponse.degraded` 中记录；调用方负责校验和重试。
3. **参数清理**：GLM 不发送 `temperature=0`；DeepSeek 思考模式不发送 temperature / penalty 参数；各家不支持的参数一律在适配器里丢弃并打 debug 日志。
4. **用量归一**：`Usage.input_tokens` 为总输入（含缓存命中），`cached_input_tokens` 为命中部分；字段映射写在各适配器里，并有 fixture 测试。
5. **漂移检测**：如果 `served_model` 与请求的模型族不一致（例如请求 `deepseek-v4-pro` 返回 Flash），记录 WARNING 事件。
6. **重试与回退**：429 / 5xx / 超时 → 同模型指数退避 2 次（1s、4s，带抖动）→ 回退链下一个（必须满足跨厂商约束）→ 全部失败抛 `LLMUnavailable`。`mode="eval"` 时**禁止回退**，只重试。
7. **白名单与跨厂商约束**：请求的模型不在 `allowed_models` 时抛 `ModelNotAllowed`（`deepseek-v4-pro` 永远被拒）。`vendor_policy=single_vendor`（v0.1 默认）时允许同厂商评审，并在 Trajectory / 证据包标注 `vendor_policy` 与评审变体；`cross_vendor` 时：路由 reviewer / verifier 时，如果主选和 executor 同厂商，跳到回退链里第一个不同厂商的模型；找不到则抛 `ConstraintViolation`（background 模式可配置为降级并记录）。
8. **计价**：价格从 `configs/pricing.yaml` 读取；费用 = 未命中输入 × 单价 + 命中输入 × 单价 + 输出 × 单价；DeepSeek 按调用时刻（Asia/Shanghai）判断高峰：工作日（不含法定节假日）9:00–12:00、14:00–18:00 为高峰（2×），其余时段（含周末、法定节假日）为空闲；节假日与调休表放 `configs/cn_holidays.yaml`。**批量 / live 调用默认只在空闲时段**（空闲闸门，TASKS W1-14）。

## 7. 验收标准

- [ ] AC1：DeepSeek 至少 4 个录制 fixture（纯文本、非思考单次工具调用、思考模式多轮工具调用含推理内容、带缓存命中字段），单测回放全部通过（Qwen / GLM fixture ⏸）。
- [ ] AC2：DeepSeek 带 tools 的多轮请求，构造出的 payload 中每条 assistant 消息都包含 `reasoning_content`（单测断言）。
- [ ] ⏸ AC3：Qwen 思考模式 + `tool_choice="required"` 时，payload 中 `tool_choice == "auto"` 且 `degraded` 非空。
- [ ] ⏸ AC4：GLM 请求中永远不出现 `thinking.type == "disabled"` 和 `temperature == 0`。
- [ ] AC5：`price_call` 对 DeepSeek 在周三 10:00 和周三 20:00（北京时间）分别返回高峰和空闲价格；法定节假日的工作日返回空闲价；DeepSeek 计价单测数值与 pricing.yaml 一致。
- [ ] AC6：请求 `deepseek-v4-pro` 抛 `ModelNotAllowed`；`cross_vendor` 策略下（FakeRouter）reviewer 路由在 executor 为 deepseek 时不会返回 deepseek 模型，构造无法满足约束的配置时抛出 `ConstraintViolation`。
- [ ] AC7：eval 模式下模拟 429，最终抛出异常而不是回退到其他模型。
- [ ] AC8：`tw doctor` 命令对三家各发一次最小请求（需要 key），打印模型 ID、served_model、延迟、用量、费用。
- [ ] AC9：`docker compose up litellm` 后，经 LiteLLM 调三家都能成功（集成测试，手动触发）。

## 8. 测试计划

- 单测：`tests/unit/llm/test_{deepseek,qwen,glm}_adapter.py`、`test_router.py`、`test_pricing.py`
- fixture：`tests/fixtures/llm/{vendor}/{case}.json`（请求 + 响应），录制脚本 `scripts/record_llm_fixture.py`（录制时自动去掉 key 和请求头）
- 集成：`tests/integration/test_live_models.py`（`-m live`，默认跳过）

## 9. 评测影响

本 spec 决定了所有评测结果的可比性：评测模式禁止回退、记录 served_model、价格表版本写入结果。

## 10. 开放问题

- Qwen / GLM 多轮工具调用时是否需要回传推理内容？回传会增加多少输入 token？→ W1 用实测回答，写进第 1 篇博客。
- 直接用各家 Responses API 是否更好？→ 暂不做，统一用 Chat Completions，降低复杂度。

## 11. AI 实施提示

- 先写 `types.py` 和三个适配器的单测（用手写的最小 fixture），再接真实 API 录制。
- 不要在 `harness/` 或 `roles/` 里写任何厂商判断。
- 不要把 API key 写进 fixture；录制脚本必须做脱敏。

## 12. 变更记录

- 2026-10-10：初稿
- 2026-10-10：按 ADR-0001（W1 接口与路径）与 ADR-0002（预算与模型策略）修订：只做 DeepSeek；白名单拒 v4-pro；vendor_policy；高峰窗口与节假日表；AC1/AC5/AC6 修订，AC3/AC4 推迟。
- 2026-10-10：W1-07/08/11/12 落地（types、ModelAdapter、DeepSeekAdapter、录制/回放、pricing + 节假日表、单任务守卫 + 全局账本）；记录实测字段名；调休上班的周末按官方字面视为空闲（`adjusted_workdays_are_peak: false` 可切换）。
- 2026-10-10：W1-13 Router 落地（llm/router.py：角色路由、vendor_policy、eval 禁止回退、回退标注 degraded、漂移告警）；W1-14 批量层闸门（llm/gate.py：高峰拒绝启动、跨入高峰停止派发、allow_peak 报告标注、`tw eval estimate` 双价估算）。AC6（v4-pro 拒绝 + cross_vendor FakeClient）与 AC7（eval 模式 429 重试 2 次后抛出、不回退）单测通过。
- 2026-10-11：UI-20 流式输出（llm/stream.py）：交互运行时 DeepSeek 走 `stream=true` + `stream_options.include_usage`，SSE 分块拼回非流式形状——回放缓存 key 与录制内容仍按非流式请求，不受影响；已收到分块后不再重试。回放命中时把缓存回复切片送出（¥0）。桌面端思考强度 off / low / medium / high → `thinking` 关 / `reasoning_effort` low / high / max（router.executor_override；模型只认 deepseek-flash，v4-pro 照旧拒绝）。只用合成 SSE 夹具与回放测试，未真调。
- 2026-10-11（0.3.2）：按 ADR-0002 修订“去掉预算控制”（Eva 19:14）：LLMClient 去掉调用级高峰闸门（`PeakHourBlocked` 不再抛出）与全局账本预检；账本只记录（`tw usage`）。白名单（拒 v4-pro）不变。
