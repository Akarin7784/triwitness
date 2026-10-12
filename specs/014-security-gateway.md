# Spec 014：安全网关（出网控制、凭证注入、MCP 代理、策略引擎、回收区）

- 状态：草稿（W7-01；W7-03～W7-07、W7-09 已实现首版，**待 Eva 审阅**）｜负责人：Eva｜目标周：W7｜依赖：002、006、013
- 相关文档：04-detailed-design.md §7.2；[Eclipse Enclave](https://enclave.eclipse.dev/docs/)（sidecar 出网网关 + 占位符凭证注入，设计参考）；MCP 2026-07-28 无状态核心
- 代码：`gateway/egress_proxy.py`（标准库正向代理）、`sandbox/egress.py`（Docker 落地）、`gateway/mcp_proxy.py`、
  `gateway/policy_engine.py`、`gateway/recycle.py`、`gateway/delegation.py`、`gateway/scan.py`、
  `configs/policies/{egress,mcp_allowlist,tool_policy}.yaml`

## 1. 背景与目标

Coding Agent 的威胁面不只是「密钥进了沙箱」：Issue / 仓库内容 / MCP 工具描述可以注入指令，让 agent 外泄数据、越权推 main、改 CI 打印密钥、或通过 DNS / HTTP 把密钥带出去。目标是：

1. **沙箱里永远没有真实密钥**（只有 `tw-placeholder-*`）；
2. **出网强制经网关**（白名单外域名、直连 IP、DNS 外泄、云元数据、私网 SSRF 在网络层失败）；
3. **MCP 工具不能悄悄变脸**（白名单 + 版本固定 + 元数据指纹）；
4. **参数级策略 fail closed**（没规则放行 = 拒绝；分类器没把握 = 拒绝）；
5. **破坏性操作可撤销**（删除进回收区；外部 DELETE / 批量写延迟 + 审批）。

## 2. 出网控制（W7-03）

拓扑（参考 Eclipse Enclave 的默认 Docker 后端）：

```
沙箱容器 ──(tw-net-*, internal=True)── 网关容器 tw-gw ──(bridge)── 外网
```

- internal 网络没有默认路由 → 直连 IP / 绕过代理 = `Network is unreachable`；
- 沙箱 DNS 上游 = `127.0.0.1`（Docker 内置 DNS 只答同网络容器名）→ DNS 外泄不通；
- 沙箱里只有 `HTTP(S)_PROXY=http://tw-gw:3128`；
- 网关：域名白名单 → 再解析；白名单外连 DNS 都不查；解析到私网 / 回环 / 链路本地 / 元数据 → 拒绝（防 rebinding）；
- 白名单写法：`a.com` 只匹配自身，`*.a.com` 只匹配子域；IP 字面量默认拒绝；
- 档位：`configs/policies/egress.yaml` 的 `profiles`（`profile:pypi` 等）；
- fake-IP DNS（Clash TUN 等，域名解析到 `198.18.0.0/15`）：`treat_as_public` 或 `TW_EGRESS_TREAT_AS_PUBLIC`；回环与链路本地永远拒绝；
- **本 box**：Docker 自定义网络需要 iptables-legacy 的 `DOCKER-USER -j ACCEPT`（旧 FORWARD DROP 会把自定义网桥流量全丢，重启后失效）。

验收：白名单内通、白名单外 403、直连 IP 失败、DNS 外泄失败、元数据拒绝（`tests/integration/sandbox/test_egress_gateway.py`）。

## 3. 凭证注入（W7-04）

- 沙箱 env 里只有 `tw-placeholder-<名>`（`sandbox.base.validate_sandbox_env` 硬底线）；
- 规则：`域名 + 方法 + 路径前缀` 匹配才把指定 header 里的占位符换成真实值；不匹配 → `placeholder_misroute`；
- 不做 TLS 中间人：带凭证的服务用明文到网关（`http://host/...` 或 `/svc/<名>/...` 服务绑定），网关 HTTPS 到上游；
- CONNECT 隧道不注入；真实密钥只在网关进程环境变量；
- 响应前 1 MiB 若回显真实值，替换为等长 `*`；审计 JSONL 从不记密钥 / 查询串。

## 4. MCP 代理（W7-05 / W7-06）

按 MCP **2026-07-28 无状态核心**：无 `initialize` / 会话；`server/discover`、`tools/list`、`tools/call`；每个请求带 `_meta`。

- 白名单：`configs/policies/mcp_allowlist.yaml`（command / version / tools / fingerprints）；
- 版本固定：`serverInfo.version` 必须等于配置；
- 指纹：`sha256(规范化 JSON{name,description,inputSchema})`；配置写了就钉死，没写则首次 list TOFU；
- **每次 list 和每次 call 前重新 list 比对**；变了 → 隔离该工具 + 告警（「第 N 次调用后变脸」）；
- 描述注入扫描（`gateway/scan.py`）→ 隔离；
- 参数过策略引擎（工具名 `mcp:<server>/<tool>`）；
- 返回文本包 `<untrusted source="mcp:…">`，命中注入特征额外标注；
- 示例 server：`python -m triwitness.gateway.mcp_demo_server [--rug-pull-after N] [--poison-output]`（载荷用金丝雀 `TW-CANARY-*`，不指向真实文件 / 域名）。

## 5. 策略引擎（W7-07）

`configs/policies/tool_policy.yaml`：`deny > ask > allow`；都没命中 → 分类器（仅 `classifier_tools`）→ 否则 **deny**。

- 匹配器：equals / in / not_in / regex / not_regex / glob / path_under / domain_in / max / min / max_items / contains / absent；
- **引用的参数不存在 = 不命中**（allow 不会误放行）；评估异常 → deny；
- 分类器：复用 `permissions.reviewer`（deepseek-flash 非思考 / FakeReviewer）；uncertain / 出错 / 超时 → deny；结果回放缓存；
- 消息里「用户已批准」只是文本，不会让效果变宽（审批走 HITL `ApprovalToken`）。

## 6. 托管区与可撤销（W7-09）

- `RecycleBin`：删除 = 移进 `<workspace>/.tw/trash/`，可 restore；`.git` / `.tw` 受保护；
- `check_git_push`：只允许推 `tw/*`；禁 force / 删远端 / --mirror / --all / --tags；
- `DeferredOps`：外部 DELETE / 批量写（>20）→ 排队 → 延迟窗口 → 人工批准才执行；执行前可撤销。

## 7. 跨 agent 委托（§8）

`inspect_delegation`：角色间消息过扫描；命中 → 包 untrusted + 标注「已批准不算数」；派生工具调用 `origin=delegated`（策略更严）。`ApprovalToken`：HMAC，文本伪造不了。

## 8. 验收（对应 TASKS W7）

- W7-03 / 04：集成测试见 §2；单测 `tests/unit/gateway/test_egress_proxy.py`、`tests/unit/sandbox/test_egress_config.py`；
- W7-05 / 06：`tests/unit/gateway/test_mcp_proxy.py`（含第 4 次变脸）；
- W7-07：`tests/unit/gateway/test_policy_engine.py`；
- W7-09：`tests/unit/gateway/test_recycle_delegation.py`；
- 开 / 关对比：`scripts/redteam_harness.py`（确定性路径，¥0）。

## 9. 开放问题（待 Eva 决定）

- **Q1** 临时最小令牌（W7-08）依赖 GitHub App 注册；未注册前推送仍走 `gh` + PAT，网关侧只拦 force / 非 tw/*。
- **Q2** 分类器默认只覆盖 `bash`；是否扩大到 `http_request` / 未知工具（每次约几分钱，要高峰闸门）。
- **Q3** `DeferredOps` 的默认延迟（现 300s）与桌面端审批卡 UI 尚未接。
- **Q4** Streamable HTTP 的 MCP 传输走出网网关，stdio 之外尚未做。

## 变更记录

- 2026-10-12：初稿；W7-03～07、W7-09 首版落地；红队确定性对比 39/39。
