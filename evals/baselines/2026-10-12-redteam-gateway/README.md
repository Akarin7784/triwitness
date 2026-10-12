# 红队开 / 关网关对比（2026-10-12）

确定性路径，`scripts/redteam_harness.py`，**不调模型、¥0**。用例：`evals/redteam/cases.yaml`（39 条，含 SSRF 5 条、跨 agent 委托 4 条）。

## 数字怎么读

「39/39」不是「开网关解出 39 题」，而是：**每一条用例在开臂、关臂上的结果都符合事先写的期望**。

| 臂 | 含义 | 本轮 |
|---|---|---|
| **开网关** | 攻击被拦 / 要人确认 / 可撤销 | **39/39 被挡住**（0 条放行）：deny 16、intercepted 17、ask 5、revocable 1 |
| **关网关** | 没有护栏时攻击能得逞（或对该层不适用） | **35/39 攻击成功**（allow 18 + attack_succeeds 16 + gone 1）；另 4 条 `n/a`（出网层 / 审批令牌只在开臂有意义） |

所以：

- **拦截率 100%** = 开臂 39 条全部不是 `allow`；
- **关臂攻击成功率 ≈ 90%** = 35/39（分母含 4 条 n/a；若只看有关臂含义的 35 条则是 100%）；
- **延迟**：开臂 p50 ≈ 9 ms、mean ≈ 13 ms（相对关臂的额外开销，确定性路径）。

Issue / 仓库投毒在确定性路径上只验证 `scan()` 能认出载荷；「agent 是否真照做」要扩档跑真 agent e2e（未做，每次约 ¥0.05–0.1）。

## 按类别（开/关均符合期望）

| 类别 | 条数 | 开臂典型结果 |
|---|---|---|
| issue_injection | 5 | intercepted |
| repo_poison | 4 | intercepted |
| mcp_tool_poison / mcp_output_poison | 4+1 | intercepted（含第 N 次变脸、版本不符、金丝雀参数） |
| dependency_poison | 3 | ask / deny |
| data_exfil | 4 | deny |
| privilege_escalation | 5 | deny / ask |
| destructive | 4 | deny / revocable |
| **ssrf** | **5** | **deny**（策略层元数据 + 出网层 IP/主机名） |
| **cross_agent** | **4** | **intercepted / ask**（委托扫描、delegated 联网 ask、伪造审批令牌拒绝） |

复现：

```bash
uv run python scripts/redteam_harness.py --out evals/results/redteam-gateway
```
