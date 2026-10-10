# Spec 002：沙箱运行时（SandboxBackend）

- 状态：草稿（2026-10-10 按 ADR-0005 重写）｜负责人：Eva｜目标：地基块｜依赖：spec 006（权限）
- 相关文档：docs/architecture.md 第 2.5、3.6、7.2 节；ADR-0001 #7；ADR-0005

## 1. 背景

Agent 会执行不可信代码（测试、安装脚本、依赖钩子）。旧版本 spec 假设所有执行都在 Docker 沙箱里（04 §2.4：DockerSandbox 默认、E2B 可选）。ADR-0005 改为：

- **终端用户默认无沙箱**：`none` 后端 = 本机进程 + git worktree 隔离 + 权限引擎（spec 006）；
- 设置页**一键安装 WSL2 + Docker Desktop**，装好后自动切到 `docker` 后端；
- **开发 / CI / 评测继续用 Docker**（评测强制）。

## 2. 目标

1. `SandboxBackend` 协议 + 能力声明，四个后端：`none`、`docker`、`wsl2`、`remote`（只留桩）。
2. 后端检测与选择（含用户偏好、eval 强制 docker）。
3. 统一的 `Sandbox` 会话接口：执行命令、读写文件、快照、恢复、diff、关闭。
4. `docker` 后端：资源限制、默认断网、非 root、不挂载宿主目录。
5. `none` 后端：worktree、环境变量最小化、进程树管控、Windows 下 Git Bash。
6. 一键安装流程（UI + 后端步骤），可重启续装。
7. 沙箱池（评测并发）。

## 3. 非目标

- `remote`（E2B 协议 / 阿里云 / 火山引擎）只保留接口与 `NotImplementedError` 类。
- 不实现凭证注入代理与出网 allowlist（spec 014 / W7-03）。
- 不支持 Windows 容器；不做 Windows 原生进程沙箱（AppContainer / MXC，见 ADR-0005 §4，推迟）。

## 4. 接口

```python
BackendName = Literal["none", "docker", "wsl2", "remote"]


class Capabilities(BaseModel):
    isolation: Literal["none", "container", "vm", "remote"]
    network_enforced: bool  # 断网 / allowlist 是否由 OS 强制
    clean_env: bool  # 能否新建干净环境（干净复跑证人）
    host_fs_visible: bool  # Agent 能否看到宿主文件系统
    allows_full_access: bool  # 是否允许 full_access 审批模式（none = False）


class ExecResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    truncated: bool = False


class SandboxSpec(BaseModel):
    image: str | None = None  # docker / wsl2 需要；none 忽略
    repo: Path  # 宿主仓库路径（none：worktree 来源；docker：copy_in 来源）
    base_ref: str = "HEAD"
    workdir: str = "/workspace/repo"  # 容器内路径；none 后端下为 worktree 绝对路径
    cpus: float = 2.0
    memory_mb: int = 4096
    disk_mb: int | None = None
    network: Literal["none", "allowlist", "host"] = "none"  # none 后端只能是 host（不可强制）
    allowlist: list[str] = []
    env: dict[str, str] = {}  # 不允许放真实密钥（校验占位符）
    user: str = "1000:1000"  # 非 root（docker）
    max_output_bytes: int = 200_000


class Sandbox(Protocol):
    id: str
    spec: SandboxSpec
    backend: BackendName

    async def exec(
        self, cmd: str, *, timeout_s: int = 120, cwd: str | None = None, env: dict[str, str] | None = None
    ) -> ExecResult: ...
    async def read_file(self, path: str) -> bytes: ...
    async def write_file(self, path: str, data: bytes, mode: int = 0o644) -> None: ...
    async def snapshot(self, label: str) -> str: ...  # 影子引用 refs/tw/ckpt/<label>
    async def restore(self, ref: str) -> None: ...
    async def diff(self, base: str) -> str: ...  # 含未跟踪文件，排除 .tw/
    async def close(self) -> None: ...


class SandboxBackend(Protocol):
    name: BackendName
    capabilities: Capabilities

    async def probe(self) -> Probe: ...  # 是否可用 + 原因（不安装任何东西）
    async def create(self, spec: SandboxSpec) -> Sandbox: ...


class Probe(BaseModel):
    available: bool
    reason: str | None = None  # 例如 "docker 守护进程未运行"、"WSL 未安装"
    version: str | None = None
    fixable_by_installer: bool = False


def select_backend(pref: BackendName | Literal["auto"], *, eval_mode: bool) -> SandboxBackend: ...


class SandboxPool:
    def __init__(self, backend: SandboxBackend, max_concurrency: int): ...
    async def acquire(self, spec: SandboxSpec) -> AsyncContextManager[Sandbox]: ...
```

文件工具（read_file / write_file / edit_file）与 `bash` 都只通过 `Sandbox` 访问；权限引擎（spec 006）在工具层、调用 `Sandbox` **之前**判定。

## 5. 后端

| 后端 | 隔离 | 断网可强制 | 干净环境 | 用途 |
|---|---|---|---|---|
| `none` | 无（worktree + 权限护栏） | 否 | 否（第二个 worktree 近似） | 终端用户默认 |
| `docker` | 容器（可选 gVisor `runsc`） | 是 | 是 | 一键安装后默认；开发 / CI / 评测 |
| `wsl2` | 轻量 VM（专用发行版 `triwitness`） | 部分（发行版内 iptables，需 root） | 是（导入快照） | Docker Desktop 不可用（授权 / 公司策略）时的备选；推迟实现 |
| `remote` | 远端 microVM | 是 | 是 | 只留接口 |

### 5.1 选择逻辑（`select_backend`）

1. `eval_mode=True`：只接受 `docker`（或显式 `--backend wsl2`）；不可用则报错并给出修复建议，**不回退到 none**（开发者开关 `--allow-unsandboxed-eval` 见 spec 006 §11）。
2. 用户在设置里指定了后端：用它；`probe()` 失败时 UI 提示，并询问是否本次改用 `none`。
3. `auto`（默认）：`docker` 可用 → docker；否则 `wsl2` 可用 → wsl2；否则 `none`。
4. 选择结果与 probe 原因写入 `task_started.payload`（可选字段 `backend`、`backend_reason`）。

`probe()` 必须快（< 2 秒）且无副作用：docker 用 SDK `ping()`；wsl2 用 `wsl.exe -l -q` 查发行版；none 检查 git 可用（Windows 还查 Git Bash 路径）。

### 5.2 `docker` 后端（原 DockerSandbox）

1. **创建**：Docker SDK 等价 `docker run -d`；`--network none`（network=none 时）、`--cpus`、`--memory`、`--pids-limit 512`、`--security-opt no-new-privileges`、`--cap-drop ALL`、非 root；**不挂载宿主目录**，仓库用 tar 流 `copy_in`。
2. **执行**：`docker exec` 运行 `bash -lc '<cmd>'`；超时杀进程组并返回 `timed_out=True`；输出超过 `max_output_bytes` 时保留头尾各一半，中间插入 `...[省略 N 字节]...`。
3. **路径安全**：`read_file`/`write_file` 只允许 `workdir`、`/tmp`、`/workspace/.tw`；拒绝 `..` 与符号链接逃逸。
4. **清理**：`close` 删除容器；标签 `tw.managed=true` + atexit 清理；`tw sandbox gc`。
5. 国内网络：文档给出 Docker 镜像加速配置；任务镜像预构建并缓存；运行阶段断网，依赖在镜像构建阶段装好。

### 5.3 `none` 后端（本机）

1. **worktree**：`git worktree add --detach <TW_HOME>/worktrees/<run_id> <base_ref>`，随后在其中 `git switch -c tw/<run_id>`；用户当前目录与分支不变。非 git 目录 → `probe` 返回不可用（原因“需要 git 仓库”）。
2. **结束**：diff 交给 UI；用户选择“应用到当前分支 / 保留分支 / 丢弃”。丢弃时 `git worktree remove --force` 并删除分支。崩溃残留由 `tw sandbox gc` 清理（扫描 `worktrees/` 与 `git worktree list`）。
3. **路径安全**：文件工具只允许 worktree、`additional_directories`；其余交给权限引擎（ask / deny）；受保护路径 `.git/`、`.triwitness/`、`.tw/`。`.tw/` 放在 `<TW_HOME>/runs/<run_id>/.tw/`（不在 worktree 内，对应 ADR-0001 #7）。
4. **环境变量**：子进程只继承白名单（`PATH`、`HOME`/`USERPROFILE`、`LANG`/`LC_*`、`TEMP`/`TMP`、`SYSTEMROOT`、`COMSPEC`、`PATHEXT`、`APPDATA`、`LOCALAPPDATA`、`HTTP(S)_PROXY`、`NO_PROXY`）+ 任务配置显式声明的变量；`*KEY*|*TOKEN*|*SECRET*|*PASSWORD*` 一律剔除。
5. **进程管控**：Windows：每次 `exec` 建 Job Object（`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`、可选内存上限），超时关闭 Job 杀整棵树；POSIX：`start_new_session=True` + `killpg` + `RLIMIT_AS`（可选）。
6. **Shell**：Windows 上 `bash` 工具调用 Git Bash（查找顺序：设置项 → `git --exec-path` 推出的 `<git>/bin/bash.exe` → `%ProgramFiles%\Git\bin\bash.exe`）；不设置 `MSYS_NO_PATHCONV`（保持 Git Bash 默认路径转换），权限引擎按 spec 006 §4.3 规范化路径。找不到 Git Bash 时暴露 `powershell` 工具（pwsh 7 优先，5.1 兜底），不支持 cmd.exe。
7. **网络**：不能强制断网；出网命令由权限规则 ask（spec 006 §9）。
8. **快照**：与 docker 相同的影子提交方案（在 worktree 内执行 git）。

### 5.4 `wsl2` 后端（推迟，P2）

专用发行版（从 rootfs tar `wsl --import triwitness <dir> <tar>`），每任务一个工作目录或从快照导出/导入；断网需在发行版内配置 iptables（以 root 运行 harness 代理进程）；Windows 文件经 `\\wsl$` 访问性能差，仓库一律 copy_in。

### 5.5 `remote` 后端（桩）

`RemoteSandboxBackend.probe()` 返回 `available=False, reason="未实现"`；`create` 抛 `NotImplementedError`。接口对齐 E2B（创建、exec、文件读写、关闭）。

## 6. 快照与 diff（所有后端共用）

1. **快照**：在 workdir 中用临时索引 `GIT_INDEX_FILE` 执行 `git add -A && git commit-tree`，更新 `refs/tw/ckpt/<label>`，**不移动当前分支**；`restore` 用 `git checkout <ref> -- .` 并清理未跟踪文件。
2. **diff**：包含新增文件，排除任何 `.tw/` 目录。

## 7. 一键安装（设置 → 沙箱）

### 7.1 UI 流程

1. **检测卡片**（打开设置页即运行 `tw sandbox doctor --json`）：显示当前后端、Windows 版本、虚拟化是否开启、WSL 状态、Docker 状态、磁盘剩余、winget 是否可用。可用则显示“已启用沙箱”。
2. **说明与同意**：列出将安装的组件（WSL2、Docker Desktop，约 2–3 GB 下载）、需要管理员授权（UAC 弹窗）、**需要重启**、Docker Desktop 授权条款提示（大型企业商用需付费订阅，链接官方条款 <https://docs.docker.com/subscription/desktop-license/>）。按钮：“开始安装” / “暂不”。
3. **进度**：步骤条（检测 → 安装 WSL → 安装 Docker Desktop → 重启 → 启动 Docker → 下载基础镜像 → 自检 → 完成），每步显示状态、耗时、可展开的日志；失败步骤有“重试”和“查看日志”。
4. **重启**：显示“需要重启后继续”，按钮“立即重启” / “稍后”；重启后应用自动打开（或下次手动打开时）继续剩余步骤。
5. **完成**：提示“沙箱已启用”，后端切为 `docker`、模式切为 `auto`；用户可在同页改回 `none`。

最小 UI 文字（全局约定）：卡片只放必要标签，详细说明折叠。

### 7.2 后端步骤（`tw sandbox install --step <name> --json`，逐行输出进度事件）

| 步骤 | 动作 | 管理员 | 幂等判断 |
|---|---|---|---|
| `preflight` | Windows 10 2004（build 19041）+ 或 Windows 11；`Get-CimInstance Win32_Processor` 的 `VirtualizationFirmwareEnabled` 或 Hyper-V 已运行；`wsl --status`；`docker version`；磁盘 ≥ 10 GB；winget 可用 | 否 | 只读 |
| `wsl` | `wsl --install --no-distribution`（参考 <https://learn.microsoft.com/windows/wsl/install>）；已装则 `wsl --update` | 是（UAC，经提权助手进程） | `wsl --status` 成功即跳过 |
| `docker` | `winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements`；winget 失败时提示手动下载（附国内镜像说明） | 是 | 已安装即跳过 |
| `reboot` | 写 `~/.triwitness/installer-state.json`（已完成步骤、时间戳）；注册一次性续装（HKCU `RunOnce` 启动应用并带 `--resume-sandbox-install`）；请求用户重启 | 否 | 状态文件标记 |
| `engine` | 启动 Docker Desktop，轮询 `docker info` 直到就绪（超时 5 分钟） | 否 | `docker info` 成功即跳过 |
| `image` | 拉取 `python:3.12-slim`（显示层进度；支持配置镜像加速） | 否 | 本地已有即跳过 |
| `smoke` | 跑 AC1/AC8 子集：断网容器内 `curl` 失败、`id -u` ≠ 0 | 否 | 每次都跑 |
| `enable` | 写用户设置 `sandbox.backend: docker`、`permissions.mode: auto`；发 `sandbox_enabled` 通知 | 否 | — |

- 提权：桌面端（Tauri / Rust）用 `ShellExecuteExW` + `runas` 启动 `tw sandbox install --step <x> --elevated`，进度经命名管道 / 临时文件回传；非提权步骤直接在普通进程里跑。
- 进度事件格式（与 tw-events/1 分开，不进轨迹）：`{"step":"docker","status":"running|done|failed|skipped","progress":0.42,"message":"…","log_ref":"…"}`。
- 失败不阻塞：任何时刻都可以“暂不安装”，继续用 `none` 后端。
- macOS / Linux：不提供一键安装，检测卡片给出 Docker 安装链接。

## 8. 干净环境复跑证人

- `docker` / `wsl2` / `remote`：Verifier 新建干净沙箱 → 应用 diff → 复跑（04 §4.2）。`verification.clean_env = "verified" | "failed"`。
- `none`：新建第二个 worktree（从 base_ref 检出 + 应用 diff）在本机复跑，记为“本机复跑”证据；`verification.clean_env = "unverified"`、`unverified_reason = "no_sandbox"`；风险等级至少 L2，不得自动合并；证据包与 UI 标注“未在干净环境验证”（ADR-0005 §3.3）。

## 9. 验收标准

docker 后端（集成测试，`-m integration`，CI 用 GitHub Actions 的 Docker）：
- [ ] AC1：`network="none"` 时容器内 `curl https://example.com` 与 `pip download requests` 失败。
- [ ] AC2：`exec("sleep 10", timeout_s=1)` 3 秒内返回且 `timed_out=True`，无残留进程。
- [ ] AC3：输出 1MB 的命令 `truncated=True`，返回大小 ≤ `max_output_bytes` + 100。
- [ ] AC4：`read_file("../../etc/passwd")` 与指向工作区外的符号链接被拒绝。
- [ ] AC5：修改 → `snapshot("s1")` → 再修改 → `restore` 后回到 s1；当前分支 HEAD 不变。
- [ ] AC6：`diff()` 含新增文件，不含 `.tw/NOTES.md`。
- [ ] AC7：`env={"GITHUB_TOKEN": "ghp_xxx"}` 创建失败；`tw-placeholder-1` 成功。
- [ ] AC8：容器内 `id -u` ≠ 0。
- [ ] AC9：并发 8 个沙箱跑 `pytest --version` 全部成功，结束后无残留容器。

none 后端（单测 + 本机集成，CI 的 Linux 与 Windows runner 都跑）：
- [ ] AC10：创建后用户仓库的工作目录、当前分支、`git status` 均不变；worktree 位于 `TW_HOME/worktrees/<run_id>`。
- [ ] AC11：子进程环境中不存在 `DEEPSEEK_API_KEY`（父进程设置了假值）。
- [ ] AC12：超时后整棵进程树被杀（Windows Job Object / POSIX 进程组），无残留。
- [ ] AC13：AC5、AC6 在 none 后端同样通过。
- [ ] AC14：丢弃后 `git worktree list` 无残留，分支已删；`tw sandbox gc` 清理崩溃残留。
- [ ] AC15（Windows）：`bash` 工具走 Git Bash；Git Bash 缺失时工具列表出现 `powershell` 而非 `bash`。

选择与安装：
- [ ] AC16：`select_backend("auto")` 在 docker 可用 / 不可用 / 均不可用时分别返回 docker / wsl2 / none（用假 probe）；`eval_mode=True` 且 docker 不可用时报错不回退。
- [ ] AC17：安装状态机：每步幂等；从 `reboot` 之后的状态文件恢复时跳过已完成步骤（假执行器单测，不真的安装）。

## 10. 测试计划

- 单测：路径校验、输出截断、env 校验与白名单、后端选择、安装状态机（全部假执行器）。
- 集成：docker 后端 AC1–AC9（需要 Docker）；none 后端 AC10–AC14（需要 git）。
- Windows：CI 增加 `windows-latest` job 跑 none 后端与路径规范化（W2 内）；一键安装只做手工验收清单（UI-08 真机验收时一起做）。

## 11. 评测影响

评测只用 docker 后端：固定镜像 tag、资源限制一致、默认断网；镜像 digest 写入 Trajectory。none 后端的运行不进入评测报告。

## 12. 开放问题

- 是否默认使用 gVisor（runsc）？→ 可选项，文档说明。
- Docker Desktop 授权不适用的用户（大型企业）→ 推荐 `wsl2` 后端或 Rancher Desktop / Podman（兼容 Docker API，probe 时接受）。是否在一键安装里提供“装 Rancher Desktop”分支？待定。
- 国内 winget 源慢 → 是否内置镜像下载地址？待定。

## 13. AI 实施提示

- 使用 `docker` Python SDK，用 `asyncio.to_thread` 包装阻塞调用。
- 不要用 `shell=True` 在宿主机执行拼接的命令；none 后端用 `[bash_path, "-lc", cmd]` 形式，权限引擎先判定。
- 集成测试用 `python:3.12-slim`，结束必须清理容器 / worktree。
- 一键安装的真实安装步骤不进 CI；用假执行器测状态机。

## 14. 变更记录

- 2026-10-10：初稿。
- 2026-10-10：按 ADR-0001 / ADR-0002 修订：`.tw/` 统一为沙箱 /workspace/.tw/（ADR-0001 #7）。
- 2026-10-10：按 ADR-0005 重写：`SandboxBackend` 协议 + none / docker / wsl2 / remote 四后端、后端选择、一键安装流程、无沙箱时干净复跑证人记为 unverified。原 `SandboxProvider` 更名为 `SandboxBackend`；`copy_in` 变为 docker 后端内部细节。
