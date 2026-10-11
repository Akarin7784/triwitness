# W5-13 外部对照第二轮 · Terminal-Bench 2.0 子集 × TriWitness（Harbor）· 10 题 × 3 次 · 2026-10-12（box）

- **是什么**：第一轮（`../2026-10-12-harbor-tb2/`，Eva 本机，每题 1 次，9/10）的重复版。同一个 10 题子集、同一个 Harbor 0.24.0 + terminal-bench-2@`2fd12b88aafd`，
  Agent 同样是 TriWitness `harness=baseline` + deepseek-flash 非思考。代码 `a14ceec`：外部任务的复现测试默认写到 `/tmp/tw_repro/`，结束时清理任务目录里新出现的 `tw_repro/` 和缓存目录；轨迹记录实际生效的 thinking 值；脱敏后的 JSON 保持合法。
- **在哪跑**：box（Linux，Docker 26.1.5）。之前 box 跑不了，原因是自定义 bridge 网络的容器完全出不了网，DNS 失败只是表现。修复方法见文末。
- **怎么跑**：`scripts/harbor_external.py run --repeats 3 --concurrency 3`（等同 `run-harbor-tb2.ps1 -Repeats 3 -Tag r2`）。每次重复一个 job：`rep0` / `rep1` / `rep2`，北京时间 04:41–05:48，三个 job 墙钟分别 33.4 / 21.2 / 12.8 分钟。
  rep0 中间 box 卡住了约 12 分钟，所以 rep0 有几题的耗时偏大，包括 overfull-hbox 第 1 次。
- **完整性**：30/30 完成，Harbor 记 0 异常、0 重试；高峰调用 0。
- **花费（账本）**：类别 `harbor-external` 共 924 次调用，**¥1.8624**，与逐题 Agent 上报之和一致。served_model 全部是 deepseek-flash，同一时间窗口内账本没有其他类别的调用。
- **入库内容**：`report.md` / `summary.json`（脚本原样输出）、`analysis.json`（逐次试验的账本、tokens、命中率、步数、工具、耗时、清理记录；由 box 上的一次性脚本从 result.json、轨迹和账本算出）、三个 job 的 `config.json` / `result.json`。
  轨迹、artifacts、verifier 输出不入库；`scripts/secret_scan.py` 0 命中。

## 结果

| 题 | 第一轮 | 第二轮 k/3 | 失败原因 | 每次平均 ¥ |
|---|---|---|---|---|
| cobol-modernization | 1 | 2/3 | rep1 用完 100 步上限（ACCOUNTS.DAT 内容不对）；rep0 也用完 100 步，但已经做对 | 0.188 |
| constraints-scheduling | 1 | 3/3 | | 0.033 |
| fix-git | 1 | 3/3 | | 0.031 |
| git-leak-recovery | 1 | 3/3 | | 0.031 |
| multi-source-data-merger | 1 | 3/3 | | 0.046 |
| nginx-request-logging | 1 | 3/3 | | 0.036 |
| openssl-selfsigned-cert | 1 | 3/3 | | 0.032 |
| overfull-hbox | 1 | **1/3** | rep0/rep1 改用 perl 暴力搜索，命令多次超时，撞到 Harbor 的 750s Agent 超时被取消 | 0.080 |
| **polyglot-c-py** | **0** | **2/3** | rep0：用完 100 步，并且目录里留下了编译产物 `cmain`（题面给出的 gcc 命令生成的）；**没有** tw_repro 残留 | 0.124 |
| prove-plus-comm | 1 | 3/3 | | 0.019 |

| 指标 | 第二轮（30 次） | 第一轮（10 次） |
|---|---|---|
| 解决 | **26/30 = 86.7%**（Wilson 70%–95%；按题聚类 bootstrap 70%–100%） | 9/10 = 90%（60%–98%） |
| 每题至少一次解决 / 三次全过 | 10/10 / 7/10 | — |
| 花费 | ¥1.862，每次 ¥0.062（中位 ¥0.035，最高 ¥0.238） | ¥0.661，每次 ¥0.066 |
| tokens | 输入 15.7M（缓存命中 **97.9%**），输出 307k，924 次调用 | 5.11M（97.5%），109k，318 次 |
| 步数 / Agent 秒 | 中位 18 步 / 65 秒 | 21.5 / 68 |
| 上下文清理 / 压缩 | 0 | 0 |

## 结论

- **复现测试修复有效**：30 次全部把复现脚本写在 `/tmp/tw_repro/`，没有一次写进任务目录。清理逻辑在 2 次里删掉了运行期间生成的 `__pycache__`。
  polyglot-c-py 从 0/1 变成 2/3；剩下那次失败的原因不同：撞到步数上限，并且留下了题面 gcc 命令生成的 `cmain`。
  清理逻辑只删复现测试和缓存目录，不会去猜别的产物该不该删，这是有意的。
- **另外两处修复也验证了**：924 个 model_call 事件都记 `thinking=false`；2903 份 JSON artifact 全部合法（第一轮有 3 份坏的）。
- **第二轮和第一轮没有可见差别**：86.7% 对 90%，区间大幅重叠。每题 3 次的配对比较要差约 23 个百分点才看得出（mde_paired）。
  新出现的失败（overfull-hbox 2 次、cobol 1 次）是同一配置的方差：长时间暴力搜索、100 步上限。不是回归：这几题第一轮也用了 52 / 70 步，接近上限。
- **可以改进的方向**（这次没改）：长命令超时后 Agent 继续反复超时，最后被 Harbor 取消；步数上限 100 对 cobol / polyglot 偏紧。
- 子集是挑过的，n 小，只作外部参照，不和公开榜单或 dev / test 比较。

## box 的 Docker 网络问题是怎么解决的

- **现象**：默认 `bridge` 网络的容器能联网；`docker network create` 出来的自定义网络（Harbor / compose 用的就是这种）里，DNS 超时，直接访问上游 DNS `10.0.0.2:53` 也超时。所以问题不在 DNS，而是整个网络不通。
- **原因**：box 上同时有两套 iptables。dockerd 用 iptables-nft，自定义网络的 NAT / 转发规则都在 nft 里，是正常的；但 iptables-legacy 里还残留着更早一次 dockerd 写的规则：`FORWARD` 默认 DROP，只放行 `docker0`。内核两套表都会检查，所以自定义网络 `br-*` 的转发包被 legacy 表丢掉了。
- **修复**：只加了一条规则，没有重启 dockerd，也没改 `daemon.json`（仍然只有 `{"storage-driver": "fuse-overlayfs"}`）：
  `sudo iptables-legacy -I DOCKER-USER 1 -m comment --comment "tw: ..." -j ACCEPT`。网络隔离仍由 nft 表里 Docker 自己的规则负责。修好后在自定义网络里测过：解析 pypi.org、HTTPS 返回 200。
- **回滚**：`sudo iptables-legacy -D DOCKER-USER 1`。改之前的规则备份在 box 的 `/tmp/iptables-legacy.before.rules` 和 `/tmp/nft.before.rules`。这条规则重启后会消失；那些残留的 legacy 规则本身也不持久。
