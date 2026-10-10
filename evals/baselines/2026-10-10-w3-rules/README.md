# 2026-10-10 W3-14 后续：新确定性规则复核（¥0）

- `tw eval reverify --mode none --mode deterministic` 作用于 evals/results/2026-10-10-w2-{test,dev}（W2-25 补丁），代码 656e108。
- test/、dev/：每个 attempt 的 verification.json（复跑 / 回归 / 防作弊 / 风险）与运行记录。
- compare.md / compare.json：与 W3-14 确定性档逐项对比（scripts/compare_verifier_rules.py）。
- tiers.md / tiers.json：两档总表（scripts/analyze_verifier_tiers.py）。
- analysis.md：结论与已知问题。
- 已知数据问题：dev 中 csv-blank-line、duration-minutes、lru-get-refresh 的沙箱清理出现 Docker 409/404，原因是与同时跑的 dev-smoke 冲突。verification.json 已完整写出，结论与旧档一致，因此保留。
