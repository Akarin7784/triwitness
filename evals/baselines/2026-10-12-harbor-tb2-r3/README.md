# W5-13 外部对照第三轮 · Terminal-Bench 2.0 子集 × TriWitness（Harbor）· 10 题 × 3 次 · 2026-10-12（box）

- **是什么**：第二轮（`../2026-10-12-harbor-tb2-r2/`，26/30，¥1.86）的对照复跑。同一个 10 题子集、同一个 Harbor 0.24.0 + terminal-bench-2@`2fd12b88aafd`，Agent 同样是 TriWitness `harness=baseline` + deepseek-flash 非思考。
  本轮代码 `f5e5c06`（含 `731a2de` 引入的 `src/triwitness/harness/timeouts.py`）：Harbor 默认 `timeout_guard=block`，超时后注入提醒、按剩余墙钟压 `timeout_s`，并对几乎相同的长命令拦截重跑。
- **在哪跑**：box（Linux）。Eva 于北京时间约 13:30 批准预算并要求立刻开跑（不再等原定 18:07）。`scripts/wsl/run-harbor-tb2.sh --repeats 3 --tag r3 --concurrency 2 --allow-peak`；工作区 `$HOME/tw-harbor`，账本 `TW_HOME=$HOME/tw-harbor/tw-home`。
- **怎么跑**：每次重复一个 Harbor job：`rep0` / `rep1` / `rep2`。北京时间约 **13:32–14:31**（墙钟约 59 分钟）。三个 job 分别约 18.5 / 22.7 / 16.6 分钟（concurrency=2）。
- **完整性**：30/30 完成，Harbor 记 0 异常、0 重试。高峰调用 496/890（14:00 后进入 DeepSeek 工作日高峰价；Eva 已批准 `--allow-peak`）。
- **花费（账本）**：类别 `harbor-external` 共 890 次调用，**¥3.0144**，与逐题 Agent 上报之和一致。served_model 全部是 deepseek-flash。高于第二轮主要因为高峰价 + polyglot 个别试次步数/花费偏大（最高单次 ¥0.522）。
- **入库内容**：`report.md` / `summary.json`（脚本原样输出）、`analysis.json`（逐次试验的账本、tokens、命中率、步数、工具、耗时、超时事件；由 box 上分析脚本从 result.json、轨迹和账本算出）、三个 job 的 `config.json` / `result.json`。
  轨迹、artifacts、verifier 输出不入库；`scripts/secret_scan.py` 对入库路径扫描。

## 结果

| 题 | 第一轮 | 第二轮 k/3 | 第三轮 k/3 | 失败原因 | 每次平均 ¥ |
|---|---|---|---|---|---|
| cobol-modernization | 1 | 2/3 | **3/3** | | 0.235 |
| constraints-scheduling | 1 | 3/3 | 3/3 | | 0.042 |
| fix-git | 1 | 3/3 | **1/3** | rep1/rep2：**verifier** 装 curl 时 debian 镜像 500/404，`curl`/`uvx` 缺失，测试脚本没跑起来；Agent 两侧都已 merge dangling commit 并 finish | 0.040 |
| git-leak-recovery | 1 | 3/3 | 3/3 | | 0.043 |
| multi-source-data-merger | 1 | 3/3 | 3/3 | | 0.039 |
| nginx-request-logging | 1 | 3/3 | 3/3 | | 0.052 |
| openssl-selfsigned-cert | 1 | 3/3 | 3/3 | | 0.045 |
| overfull-hbox | 1 | **1/3** | **3/3** | 本轮无 Harbor 取消；见下方超时守卫 | 0.106 |
| polyglot-c-py | 0 | 2/3 | **3/3** | | 0.369 |
| prove-plus-comm | 1 | 3/3 | 3/3 | | 0.035 |

| 指标 | 第三轮（30 次） | 第二轮（30 次） | 第一轮（10 次） |
|---|---|---|---|
| 解决 | **28/30 = 93.3%**（Wilson 79%–98%；按题聚类 bootstrap 约 80%–100%） | 26/30 = 86.7%（70%–95%） | 9/10 = 90% |
| 每题至少一次解决 / 三次全过 | 10/10 / 8/10 | 10/10 / 7/10 | — |
| 花费 | ¥3.014，每次中位约 ¥0.05，最高 ¥0.522 | ¥1.862，中位 ¥0.035，最高 ¥0.238 | ¥0.661 |
| tokens | 输入约 15.0M（缓存命中约 **97.7%**），输出约 295k，890 次调用 | 15.7M（97.9%），307k，924 次 | 5.11M（97.5%），109k，318 次 |
| 步数 / Agent 秒 | 中位约 18 步 | 中位 18 步 / 65 秒 | 21.5 / 68 |
| 上下文清理 / 压缩 | 0 | 0 | 0 |

## 超时守卫（本轮重点）

第二轮 overfull-hbox 在 rep0/rep1 上用 perl 暴力搜索，命令多次超时后撞上 Harbor 750s Agent 超时被取消（1/3）。
本轮默认打开 `timeout_guard=block`（`harness/timeouts.py`）：

- **overfull-hbox 3/3 全过**。三次里两次各出现 1 次工具超时（exit 124）；超时后轨迹里出现守卫注入的用户提醒（「不要原样重跑同一条长命令…」「timeout_s 已按剩余时间压到 …」），模型改走更短/后台/缩小搜索，没有再撞 Harbor 取消。
- rep2 的 overfull 甚至 0 次工具超时（直接用了更克制的搜索）。
- 轨迹里可见提醒文本；本轮没有观察到 `repeat_timeout` 硬拦截落地（模型在提醒后就改策略了）。元数据字段 `timeout_guard` 记录的是模式字符串 `block`，不是「是否触发过」。

结论：**超时循环守卫对 overfull-hbox 这类「长命令重试 → 墙钟耗尽」路径有效**；本轮该题从 1/3 → 3/3，且无 Harbor agent cancel。

## 和其它失败的关系

- **fix-git 1/3**：不是回归。rep1/rep2 的 verifier `test.sh` 依赖临时 `apt-get install curl` + 安装 uv；当天 debian 镜像对 bookworm InRelease 返回 500、包 404，导致 `curl: command not found` / `uvx: command not found`，pytest 根本没跑。Agent 两侧 finish 内容都表明已找到 dangling commit `650dba4` 并 merge/解决冲突。rep0 同一 verifier 路径 apt 正常 → 2 passed。
- **cobol / polyglot**：本轮 3/3，比第二轮（2/3、2/3）好；polyglot 花费偏高（个别试次 80–120 步），属于方差，不是超时取消。

## 结论

- 超时守卫达到设计目的：overfull-hbox 不再因重复超时被 Harbor 取消。
- 总解决率 28/30（93.3%）高于第二轮 26/30；扣掉 fix-git 的两条 verifier 基建噪声，Agent 侧可视为 30/30。
- 花费 ¥3.01 > 预期约 ¥2，主因是 14:00 后高峰价（已批准）+ polyglot 贵试次，不是超时重试烧掉的。
- 子集是挑过的，n 小，只作外部参照，不和公开榜单或 dev / test 比较。

## 环境备忘

- iptables-legacy `DOCKER-USER` ACCEPT（自定义 bridge 出网）开跑前仍在。
- Docker 镜像/缓存本轮后约占用升高；结果入库后已/将做 dangling prune。
