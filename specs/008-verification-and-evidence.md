# Spec 008：验证流水线与证据包

- 状态：草稿（确定性部分已实现；Eva 延后审阅，按默认采纳）｜负责人：Eva｜目标周：W3｜依赖：002、003、004、005
- 相关文档：04-detailed-design.md 第 4.1–4.5、4.8 节；spec 002 §8；ADR-0005 §3.3；spec 009（风险分级）

## 1. 背景

Agent 说“修好了”不等于修好了。W1/W2 基线里出现过“自写复现通过、隐藏测试仍失败”（swe-crosstl-257：隐藏测试要求 `UNSIGNED_INT` 这个名字，Issue 里没有写）。TriWitness 的卖点是**每个结论都有可复核的证据**：确定性检查在前，模型只做判读；证据不足时如实说“不确定”，而不是报喜。

## 2. 目标

1. **repro-first**：复现测试在基线上必须失败、在修复后必须通过，两次都在**全新的沙箱**里跑。
2. **回归对比**：只把“基线上没有、修复后新出现”的失败算回归；新失败重跑 2 次判 flaky。
3. **防作弊**：在 diff 上检测改测试、加 skip、削弱断言、改测试基础设施、针对测试特判（04 §4.4）。
4. **声明审计**：检查 Executor 的完成声明是否被证据支撑（复现是否对应 Issue、声明与自述风险是否矛盾）。
5. **无沙箱如实标注**：none 后端时复跑在新 worktree 完成，标 `clean_env=unverified`，风险至少 L2，不自动合并。
6. **证据包**：所有结果汇总到 `Evidence`（evidence.json），渲染成固定格式的 PR 正文。

## 3. 非目标

- 覆盖率上下文映射（W3-06 P1 可选）、测试选择的导入图（W3-06，另行实现）。
- 用模型判断“基线失败原因是否和 Issue 相关”（W3-10 Verifier 角色负责，本 spec 只定义输入输出）。
- 评测模式下的隐藏测试判分（spec 004 Grader，结构上与 Agent 沙箱隔离）。

## 4. 模块与数据模型

| 模块 | 职责 | 输出 |
|---|---|---|
| `verify/rerun.py` | `rerun_repro`：基线沙箱只应用 diff 中的测试文件（必须失败），修复沙箱应用完整 diff（必须通过）；`regression`：基线 vs 修复后失败集合 + flaky 重跑 | `RerunResult`（repro_status、clean_env、unverified_reason、test_runs、notes、logs） |
| `verify/anticheat.py` | 规则见 §5.3 | `AntiCheatReport`（flags：code / action / path / line / detail） |
| `verify/claim.py` | 完成声明审计 | `ClaimVerdict`（pass / fail / insufficient_evidence + flags + reasons） |
| `verify/risk.py` | 见 spec 009 | `RiskResult` |
| `verify/evidence.py` | `build_evidence` 统一跑防作弊与风险，`render_pr` 渲染 | `Evidence`、PR 正文 Markdown |

`Evidence` 新增字段（可选，向后兼容）：`base_ref`、`clean_env`（verified / unverified）、`unverified_reason`（如 `no_sandbox`）、`claim_flags`。

`TestRun.scope`：`repro_base`、`repro_patched`、`related`、`full`、`hidden`。

## 5. 行为细节

### 5.1 复现（repro_status）

| 基线（只加测试） | 修复后 | repro_status | 说明 |
|---|---|---|---|
| 失败 | 通过 | `reproduced` | 正常 |
| 通过 | — | `inconclusive` | 复现测试没有复现问题（notes：“基线上就通过”） |
| 失败 | 失败 | `failed` | 修复无效（notes：“仍失败”） |
| 补丁打不上 | — | `inconclusive` | notes 记录 git apply 错误 |
| 没有复现 | — | `not_applicable` | 文档 / 重构类任务，风险至少 L1 |

每次运行都 `backend.create(spec)` 新建沙箱并 `git apply` 补丁；pytest 命令自动加 `--junitxml`，按用例 id 解析失败集合。

### 5.2 回归与 flaky

- 基线与修复后各跑一次同一命令；`new = fail_patched − fail_base`。
- 每个新失败单独重跑 `FLAKY_RERUNS = 2` 次，任一次通过 → 记 flaky，不算回归但写进证据。
- 基线已有的失败写一条说明“N 个失败在基线上就存在，不计回归”，PR 测试表里同样注明。

### 5.3 防作弊规则

| code | 触发 | 动作 |
|---|---|---|
| `skip_or_xfail_added` | 新增 `pytest.mark.skip/xfail`、`pytest.skip(`、`unittest.skip` 等（非注释行） | block → 结论 fail、L3 |
| `test_special_casing` | 非测试代码出现 `"pytest" in sys.modules`、`PYTEST_CURRENT_TEST`、测试文件名字面量 | block |
| `test_infra_modified` | conftest / pytest.ini / tox.ini / noxfile / CI 配置 | approval → ≥ L2 |
| `existing_test_modified` | 已有测试文件有删除 / 改写 / 改名 | review → ≥ L2 |
| `assertion_weakened` | 恒真断言，或已有测试净减少 assert | review → ≥ L2 |
| `exception_swallowed` | 新增 `except:` / `except Exception:` + `pass` | review → ≥ L2 |
| `existing_test_extended` | 已有测试文件只有新增 | info（不加分） |

### 5.4 声明审计（claim）

- `repro_missing`：声称修好但没有复现。
- `repro_not_tied_to_issue`：复现测试断言里的字符串字面量一个都没在 Issue 中出现（crosstl-257 的情况）。
- `issue_underspecified`：Issue 没有代码块 / `>>>` / 规格措辞 / 具体的反引号片段。
- `claim_contradicts_open_risks`：open_risks 里有“可能 / 不确定”类表述，却给出 tests_passed + 置信度 ≥ 0.8。
- 有任一不足 → `insufficient_evidence`；`build_evidence` 把整体 verdict 从 pass 降为 inconclusive。

### 5.5 无沙箱（none 后端）

`capabilities.clean_env = False` → `clean_env=unverified`、`unverified_reason=no_sandbox`；复跑仍在全新 worktree（不碰用户工作区）；风险下限 L2（spec 009）；PR 正文顶部显示“⚠️ 干净环境未验证”。

### 5.6 PR 正文

按 04 §4.8 模板：标题行（等级 + 分数）、结论（含 verdict）、未验证 / L3 横幅、复现、测试表（新增失败 + 基线已有失败 + flaky 说明）、静态检查与防作弊（逐项 ✅/❌）、声明审计 flags、风险因子（加分项 + 等级下限）、评审、成本表、trace 链接与 config_hash。渲染是纯函数，有快照测试。

## 6. 验收标准

- [x] AC1：复现四种组合（reproduced / 基线通过 / 仍失败 / 无复现）与补丁打不上，在真实 none 后端（临时 git 仓库 + 真 pytest）上测试；用户工作区不被修改（`test_rerun_local.py`）。
- [x] AC2：none 后端产出 `clean_env=unverified` 且风险 ≥ L2；声明 clean_env 的后端产出 verified 且 L0。
- [x] AC3：回归对比区分新失败、flaky、基线已有失败。
- [x] AC4：每条防作弊规则至少 1 正例 1 反例；block 规则使 verdict=fail、L3（`test_anticheat.py`、`test_evidence.py`）。
- [x] AC5：crosstl-257 类 fixture 被声明审计判为证据不足（`test_backlog_fixtures.py`、`test_evidence.py`）。
- [x] AC6：PR 正文快照测试（干净 L0、无沙箱 L2）；Evidence JSON 往返一致。
- [ ] AC7：docker 后端上的复跑集成测试（W3-05 剩余）。
- [ ] AC8：Verifier 模型判读与三档评测对比（W3-10、W3-13/14）。

## 7. 测试计划

`tests/unit/verifier/`：test_anticheat、test_claim、test_risk、test_backlog_fixtures、test_rerun_local（真实 git + pytest）、test_evidence（快照 `tests/fixtures/verifier/snapshots/`，`UPDATE_SNAPSHOTS=1` 更新）。全部离线、不调用模型。

## 8. 评测影响

W3-13 接入后新增指标：假成功率、Verifier 精确率 / 召回率（以隐藏测试为真值）、风险等级 vs 实际通过率。

## 9. 开放问题

- 复现测试是否默认留在 PR 里（04 建议保留，可配置）。
- `repro_not_tied_to_issue` 只看字符串字面量，数值 / 结构断言暂不覆盖；以 dev 集误报率决定是否放宽。
- 测试运行时间 > 10 分钟时的“相关 + 抽样”策略随 W3-06 一起定。

## 10. AI 实施提示

- 不要在用户工作区里复跑；一律 `backend.create` 新沙箱。
- 防作弊和风险分只在 `build_evidence` 里算一次，PR 正文与 evidence.json 必须一致。

## 11. 变更记录

- 2026-10-10：初稿（W3-01），同时实现 W3-05/07/09/11/12/20 的确定性部分（3d7c7f3、8e71075、5456e64、9fe0fbd）。
- 2026-10-10：W3-14 结论落地：评测与 `tw run` 默认 verifier = deterministic；model 档改为 `model_policy = thin_pass`——只在确定性 pass 且证据薄（无回归 / 仅相关 + 抽样 / 非阻断防作弊提示 / 声明审计标记 / Executor 自报风险）时调用模型、判 1 次；`always` 仅供对比实验。
- 2026-10-10：W3-14 后续（数据校准）：①回归盲区——回归跑了但 0 通过（收集期报错 / 断网 / `-x`）→ 结论最多 inconclusive；②回归命令去掉 `-x` / `--maxfail` / `--stepwise`、pytest 加 `--continue-on-collection-errors`，全量 0 通过时自动改跑 test_select 选出的相关测试；③单独新增 skip / xfail 从 block（L3、fail）降为 review（L2、inconclusive 需人审），与削弱断言同时出现仍 block；④Verifier 提示词 v2 + 代码兜底：pass 但证据缺口提到“Issue 未指定的名字由 Agent 假设”或“只修了一条路径”→ inconclusive。
- 2026-10-10：W3-14 后续（三处免费修正）：补丁侧回归超时（`<timeout>`，基线未超时）不算新失败，结论 inconclusive（“回归超时”）；thin_evidence 中 Executor 自报风险单独出现不算证据薄；run_tests / submit_repro / 回归复跑统一带 `PYTHONDONTWRITEBYTECODE=1`（sandbox.base.TEST_ENV）。
