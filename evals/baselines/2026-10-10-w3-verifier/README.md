# W3-14 verifier 三档对比（2026-10-10，北京时间 20:00–20:45）

在 W2-25 基线已保存的补丁上**只重跑验证阶段**（不重跑 Executor、不重新判分），三档：

- `none`：不验证（等于采信 Agent 自称是否修好）；
- `deterministic`：干净沙箱复跑 Agent 的复现测试（基线必须失败、打补丁后必须通过）+ 回归对比（只算新增失败）+ 防作弊 7 条 + 声明审计，¥0；
- `model`：在同一份确定性证据上加 Verifier 模型（deepseek-flash 思考档）判读，**每个补丁独立判 3 次**（多数票，并列取保守），最终 = 确定性结论与模型多数票中更保守者。

命令（Eva 批准：模型档每补丁 3 次、上限 ¥5、空闲时段）：

```bash
tw eval reverify --results evals/results/2026-10-10-w2-{test,dev} --out evals/results/2026-10-10-w3-verifier-{test,dev} \
  --mode none --mode deterministic --concurrency 3
tw eval reverify ... --mode model --live --model-repeats 3 --max-total-cny {4.3,1.5}   # 复用 deterministic 档证据，不再起沙箱
uv run python scripts/analyze_verifier_tiers.py evals/baselines/2026-10-10-w3-verifier/{test,dev} --out evals/baselines/2026-10-10-w3-verifier
```

- `test/`、`dev/`：每档每个 attempt 的 `result.json`（判分真值沿用 W2）+ `verification.json`（复跑证据、风险等级、model 档 3 次判读明细）；`report.md/json` 为 `tw eval report` 生成。`run.json` 记录的是最后一次调用（model 档）的元数据。
- `tiers.md/json`：脚本生成的对比数据表；`analysis.md`：解读与结论。
- 花费：model 档 ¥2.9437（144 次 Verifier 调用 = 48 个补丁 × 3，含 2 个 infra 题），本地账本 ¥10.6761 → ¥13.6199，高峰调用 0。
