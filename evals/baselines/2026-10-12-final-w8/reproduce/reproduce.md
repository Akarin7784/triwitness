# 评测复现对比（tw eval reproduce）

> 注意：模型服务端可能已更新（同一模型 ID 不保证同一权重 / 同一推理栈），且采样有随机性；复现结果与原结果有差异是正常的，不代表代码回归。

- 原结果：`/out/final/results/baseline`
- 复现：`/out/final/reproduce`
- 对比 1 次；结论一致率 100%
- 解决数：原 1 → 现 1；花费：原 ¥0.0765 → 现 ¥0.0521
- 模型快照：原 {'deepseek-flash': 1917} → 现 {'deepseek-flash': 39}

- 复现缺少（基础设施错误或未跑）：final-baseline/swe-bedrock-agentcore-sdk-python-279_interface/1, final-baseline/swe-canvasapi-716/1, final-baseline/swe-ccflow-24/1, final-baseline/swe-cfn-python-lint-4368/1, final-baseline/swe-conan-19750/1, final-baseline/swe-copier-2646/1, final-baseline/swe-crosstl-98/1, final-baseline/swe-cyclopts-701/1, final-baseline/swe-django-components-489/1, final-baseline/swe-faststream-2701/1, final-baseline/swe-fromager-1106/1, final-baseline/swe-huggingface_hub-4056/1, final-baseline/swe-icontract-297/1, final-baseline/swe-isort-2491/1, final-baseline/swe-leanclient-24/1, final-baseline/swe-llm-sandbox-101/1, final-baseline/swe-loguru-1306/1, final-baseline/swe-loguru-1451/1, final-baseline/swe-marimo-6819/1, final-baseline/swe-marimo-8401/1, final-baseline/swe-microsoft-authentication-library-for-python-730/1, final-baseline/swe-openhands-resolver-123/1, final-baseline/swe-opensandbox-816/1, final-baseline/swe-param-1117/1, final-baseline/swe-ro-crate-py-193/1, final-baseline/swe-scrapy-7351_interface/1, final-baseline/swe-spikeinterface-3047/1, final-baseline/swe-spikeinterface-3778/1, final-baseline/swe-sqlfluff-7615/1, final-baseline/swe-sqlglot-7457/1, final-baseline/swe-sqlglot-7479/1, final-baseline/swe-stumpy-1015/1, final-baseline/swe-ultraplot-696/1, final-baseline/swe-xcp_d-1433/1

| 配置 | 任务 | 尝试 | 原 | 现 | 原 ¥ | 现 ¥ |
|---|---|---|---|---|---|---|
| final-baseline | swe-cyclopts-633 | 1 | ✓ | ✓ | 0.076458 | 0.05209 |
