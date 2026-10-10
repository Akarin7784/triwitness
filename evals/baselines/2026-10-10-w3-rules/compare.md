# 确定性档：W3-14（旧规则）vs W3-14 后续（新规则），同一批 48 个 attempt（去 2 infra）

| 指标 | 旧 | 新 |
|---|---|---|
| 判 pass | 20 | 17 |
| 精确率 | 85% | 88% |
| 召回率 | 61% | 54% |
| 放过的假成功 | 3 | 2 |
| 误报（真解决却没判 pass） | 11 | 13 |
| 已知假成功拦下 | 5/8 | 6/8 |
| 回归盲区（全量/相关 0 通过） | 10 | 9 |
| 回退到相关测试 | 0 | 1 |
| skip/xfail 标记 | 3 | 3 |
| 风险 L0/L1/L2/L3 → 实际解决 | 14/18 · 3/9 · 9/18 · 2/3 | 13/17 · 5/11 · 10/20 · 0/0 |

放过的假成功：旧 swe-canvasapi-716, swe-conan-19750, swe-microsoft-authentication-library-for-python-730；新 swe-canvasapi-716, swe-microsoft-authentication-library-for-python-730

## 结论变化的 attempt

| 任务 | 集 | 真值 | 旧 | 新 | 新理由（前 3 条） |
|---|---|---|---|---|---|
| swe-conan-19750 | test | 假成功 | pass/L0 | fail/L0 | 新增失败 2 个：<command>, <timeout> |
| swe-copier-2646 | test | 解决 | fail/L3 | fail/L2 | 新增失败 2 个：<command>, <timeout>；没有复现测试（repro_status = not_applicable）：证据改为行为对比 / 静态论证，风险至少 L1 |
| swe-faststream-2701 | test | 解决 | pass/L0 | inconclusive/L1 | 回归盲区：full 一个测试都没通过（失败 1 / 错误 0），测试套件没真正跑起来，无回归证据；2 个失败在基线上就存在，不计回归 |
| swe-llm-sandbox-101 | test | 假成功 | fail/L3 | inconclusive/L2 | 需人审：skip_or_xfail_added |
| swe-ro-crate-py-171 | dev | 解决 | inconclusive/L2 | fail/L1 | 新增失败 1 个：tests/tw_repro/test_issue_103.py::test_issue_workflow[False]；没有复现测试（repro_status = not_applicable）：证据改为行为对比 / 静态论证，风险至少 L1；11 个失败在基线上就存在，不计回归 |
| swe-spikeinterface-3047 | test | 解决 | fail/L3 | inconclusive/L2 | 回归盲区：full 一个测试都没通过（失败 1 / 错误 0），测试套件没真正跑起来，无回归证据；需人审：skip_or_xfail_added；复现状态 not_applicable |
| swe-spikeinterface-3778 | test | 解决 | pass/L2 | inconclusive/L2 | 回归盲区：full 一个测试都没通过（失败 1 / 错误 0），测试套件没真正跑起来，无回归证据；2 个失败在基线上就存在，不计回归 |
