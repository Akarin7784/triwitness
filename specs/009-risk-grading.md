# Spec 009：风险分级

- 状态：草稿（已实现；Eva 延后审阅，按默认采纳）｜负责人：Eva｜目标周：W3｜依赖：008
- 相关文档：04-detailed-design.md 第 4.6 节；`configs/policies/risk.yaml`；`src/triwitness/verify/risk.py`

## 1. 背景

审查者最缺的是时间。风险分把“这个 PR 该看多仔细”变成一个有理由的数字：每个加分项都写进证据包，回答“为什么是 L2”。

## 2. 目标

1. 分数 0–100 → L0–L3；阈值、因子分值、敏感路径全部可配置（risk.yaml）。
2. 每个加分项都是一条 `RiskFactor(code, points, detail)`，detail 是给人看的中文原因。
3. 阻断规则与“下限”（floor）独立于分数：只抬等级、不改分数，并作为 `floor:<name>` 因子写明原因。

## 3. 非目标

- 用数据自动学权重（W3-13 只统计“等级 vs 隐藏测试通过率”的相关性，人工调参）。
- 按仓库定制敏感路径（v1：仓库内 `.triwitness/risk.yaml` 覆盖）。

## 4. 等级

| 等级 | 分数 | 动作 |
|---|---|---|
| L0 | 0–14 | 可自动开 PR，仍需人工合并 |
| L1 | 15–39 | 开 PR 前确认一次 |
| L2 | 40–69 | Draft PR，标出重点审查点 |
| L3 | ≥ 70 或命中阻断 | 不开 PR，`NEEDS_HUMAN` |

## 5. 因子（默认值）

| code | 分 | 条件 |
|---|---|---|
| lines_over_200 / lines_over_500 | 10 / 20 | 改动行数（增 + 删）；二者取其一 |
| sensitive_path | 25 | 命中 sensitive_paths（auth、crypto、security、permission、payment、migrations…） |
| ci_build_deps | 20 | CI / 构建 / 依赖文件（build_files） |
| existing_test_modified | 20 | 防作弊同名 flag |
| low_coverage | 15 | 改动行覆盖率 < coverage_threshold（0.5）；没有数据不加分 |
| repro_not_reproduced | 15 | repro_status ∈ {not_applicable, inconclusive, failed} |
| verifier_uncertain | 20 | verdict = inconclusive 或置信度 < 0.6 |
| review_major_open | 25 | Reviewer 有未解决的 major / blocker |
| public_api_changed | 10 | 删除或改签名的公共 `def` / `class`（非 `_` 开头、非测试文件） |
| security_scan | 20 | bandit 中 / 高告警 > 0 |
| claim_audit | 15 | 声明审计有 flag（spec 008 §5.4） |

## 6. 下限（floors）

| 名称 | 下限 | 条件 |
|---|---|---|
| anticheat_block | L3 | 防作弊 block 规则 |
| anticheat_review | L2 | 防作弊 review / approval 规则 |
| clean_env_unverified | L2 | 未在干净环境复跑（无沙箱） |
| repro_not_reproduced | L1 | 复现未成立 |

## 7. 验收标准

- [x] AC1：等级边界 14/15、39/40、69/70（`test_risk.py`）。
- [x] AC2：每个因子单独触发并带 detail；行数因子互斥。
- [x] AC3：下限只在抬高等级时出现，作为 `floor:*` 因子、0 分。
- [x] AC4：自定义 risk.yaml 可改阈值与分值。
- [x] AC5：PR 正文列出加分项与等级下限（spec 008 快照）。
- [ ] AC6：W3-13 报告中“风险等级 vs 隐藏测试通过率”。

## 8. 开放问题

- 覆盖率数据来源（W3-08 静态检查是否同时跑 coverage）。
- claim_audit 15 分是否偏低：crosstl 类任务目前只到 L1–L2，W3-14 对比后再调。

## 9. 变更记录

- 2026-10-10：初稿（W3-02），实现 3d7c7f3。新增 04 未列出的 `claim_audit` 因子与 floors 段。
- 2026-10-10：W3-14 后续：`skip_or_xfail_added` 单独出现时归入 anticheat_review（L2），与 `assertion_weakened` 同时出现才归 anticheat_block（L3）。W3-14：3 次触发 2 次是正确补丁。
