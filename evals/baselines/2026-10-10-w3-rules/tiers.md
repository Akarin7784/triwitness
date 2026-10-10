# W3-14 verifier 三档对比 · 数据表（自动生成）

来源：evals/baselines/2026-10-10-w3-rules/test, evals/baselines/2026-10-10-w3-rules/dev；infra 排除：swe-ultraplot-696, swe-xcp_d-1433

| 档位 | n | 判 pass | 精确率 | 召回率 | 放过的假成功 | 误报（真解决被拦） | 已知 8 个假成功拦下 | 花费 |
|---|---|---|---|---|---|---|---|---|
| none | 48 | 29 | 72% | 75% | 8 | 7 | 0/8 | ¥0.0000 |
| deterministic | 48 | 17 | 88% | 54% | 2 | 13 | 6/8 | ¥0.0000 |

## 分集合

| 档位 | 集合 | n | 判 pass | 精确率 | 召回率 | 放过 | 误报 |
|---|---|---|---|---|---|---|---|
| none | dev | 15 | 12 | 83% | 83% | 2 | 2 |
| none | test | 33 | 17 | 65% | 69% | 6 | 5 |
| deterministic | dev | 15 | 9 | 100% | 75% | 0 | 3 |
| deterministic | test | 33 | 8 | 75% | 38% | 2 | 10 |

## 已知 8 个假成功

| 任务 | none | deterministic |
|---|---|---|
| swe-canvasapi-716 | ❌ 放过（agent_claim） | ❌ 放过（pass，L2；） |
| swe-conan-19750 | ❌ 放过（agent_claim） | ✅ 拦下（fail，L0；regression） |
| swe-django-components-489 | ❌ 放过（agent_claim） | ✅ 拦下（inconclusive，L1；claim_audit） |
| swe-llm-sandbox-101 | ❌ 放过（agent_claim） | ✅ 拦下（inconclusive，L2；） |
| swe-loguru-1306 | ❌ 放过（agent_claim） | ✅ 拦下（inconclusive，L2；repro_missing+claim_audit） |
| swe-microsoft-authentication-library-for-python-730 | ❌ 放过（agent_claim） | ❌ 放过（pass，L0；） |
| swe-crosstl-257 | ❌ 放过（agent_claim） | ✅ 拦下（inconclusive，L1；claim_audit） |
| swe-h-transport-materials-224 | ❌ 放过（agent_claim） | ✅ 拦下（inconclusive，L2；claim_audit） |

## 误报（隐藏测试通过、验证器没放行）

- none（Agent 自己没声称成功但其实解决了）：swe-copier-2646, swe-icontract-297, swe-spikeinterface-3047, swe-sqlglot-7479, swe-stumpy-1015, swe-dymos-1021, swe-ro-crate-py-171
- deterministic（13）：swe-copier-2646=fail/L2[regression]；swe-cyclopts-633=inconclusive/L1[claim_audit]；swe-faststream-2701=inconclusive/L1[]；swe-icontract-297=inconclusive/L2[repro_missing]；swe-leanclient-24=inconclusive/L2[repro_missing+claim_audit]；swe-scrapy-7351_interface=inconclusive/L1[claim_audit]；swe-spikeinterface-3047=inconclusive/L2[repro_missing]；swe-spikeinterface-3778=inconclusive/L2[]；swe-sqlglot-7479=inconclusive/L2[repro_missing]；swe-stumpy-1015=inconclusive/L2[repro_missing+claim_audit]；csv-blank-line=inconclusive/L1[claim_audit]；swe-dymos-1021=inconclusive/L2[claim_not_asserted]；swe-ro-crate-py-171=fail/L1[regression]

## 风险等级 → 实际通过率

- deterministic：L0 13/17 = 76%；L1 5/11 = 45%；L2 10/20 = 50%

## 拦截信号（隐藏测试不过且没放行的 attempt）

- deterministic：repro_missing 8, claim_audit 4, regression 3, claim_not_asserted 1
