# Spec 002：沙箱运行时

- 状态：草稿｜负责人：Eva｜目标周：W1｜依赖：无
- 相关文档：04-detailed-design.md 第 2.5、3.6、7.2 节

## 1. 背景

Agent 会在仓库里执行不可信的代码（测试、安装脚本、依赖钩子）。所有执行必须发生在隔离沙箱里，而且评测需要大量并发、可复现的干净环境。本地开发和评测默认用 Docker；后续可接 E2B 协议的云沙箱。

## 2. 目标

1. `Sandbox` 协议（异步）：执行命令、读写文件、快照、恢复、关闭。
2. `DockerSandbox` 实现：基于镜像创建容器、挂载/复制仓库、资源限制、默认断网。
3. 网络策略：`none`（默认）、`allowlist`（经出网代理，W1 只预留接口）。
4. 工作区快照：影子提交 `refs/tw/ckpt/<label>`。
5. 沙箱池与并发上限，供评测 Runner 使用。

## 3. 非目标

- 不实现 E2B（只保留接口和一个"未实现"类）。
- 不实现凭证注入代理（spec 014 安全网关）。
- 不支持 Windows 容器。

## 4. 接口

```python
class ExecResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    truncated: bool = False


class SandboxSpec(BaseModel):
    image: str  # 例如 "tw-task-<id>:latest" 或 "python:3.12-slim"
    workdir: str = "/workspace/repo"
    cpus: float = 2.0
    memory_mb: int = 4096
    disk_mb: int | None = None
    network: Literal["none", "allowlist"] = "none"
    allowlist: list[str] = []
    env: dict[str, str] = {}  # 不允许放真实密钥（校验占位符）
    user: str = "1000:1000"  # 非 root
    max_output_bytes: int = 200_000


class Sandbox(Protocol):
    id: str
    spec: SandboxSpec

    async def exec(
        self, cmd: str, *, timeout_s: int = 120, cwd: str | None = None, env: dict[str, str] | None = None
    ) -> ExecResult: ...
    async def read_file(self, path: str) -> bytes: ...
    async def write_file(self, path: str, data: bytes, mode: int = 0o644) -> None: ...
    async def copy_in(self, host_path: Path, sandbox_path: str) -> None: ...
    async def snapshot(self, label: str) -> str: ...  # 返回影子引用名
    async def restore(self, ref: str) -> None: ...
    async def diff(self, base: str) -> str: ...  # git diff base..工作区（含未跟踪文件）
    async def close(self) -> None: ...


class SandboxProvider(Protocol):
    async def create(self, spec: SandboxSpec) -> Sandbox: ...


class SandboxPool:
    def __init__(self, provider: SandboxProvider, max_concurrency: int): ...
    async def acquire(self, spec: SandboxSpec) -> AsyncContextManager[Sandbox]: ...
```

## 5. 行为细节

1. **创建**：`docker run -d` 等价操作（用 Docker SDK for Python），`--network none`（network=none 时），`--cpus`、`--memory`、`--pids-limit 512`、`--security-opt no-new-privileges`、`--cap-drop ALL`、非 root 用户；**不挂载宿主目录**，仓库用 `copy_in`（tar 流）。
2. **执行**：`docker exec` 运行 `bash -lc '<cmd>'`；超时后杀掉整个进程组并返回 `timed_out=True`；stdout/stderr 超过 `max_output_bytes` 时保留头尾各一半，中间插入 `...[省略 N 字节]...`，`truncated=True`。
3. **路径安全**：`read_file`/`write_file` 只允许 `workdir` 和 `/tmp`、`/workspace/.tw` 下的路径；拒绝 `..` 逃逸和符号链接逃逸。
4. **快照**：在 `workdir` 里执行 `git add -A && git commit --no-verify -m "tw ckpt <label>"` 到临时索引，并更新 `refs/tw/ckpt/<label>`，**不移动当前分支**；`restore` 用 `git checkout <ref> -- .` 并清理未跟踪文件。
5. **diff**：包含新增文件，排除任何 `.tw/` 目录。TriWitness 的工作目录统一为沙箱内 `/workspace/.tw/`（在 `/workspace/repo` 之外，放 `NOTES.md` 与 `outputs/`）；仓库内若出现 `.tw/` 也一律排除（ADR-0001 #7）。
6. **环境变量校验**：`env` 中键名包含 `KEY|TOKEN|SECRET|PASSWORD` 的，值必须以 `tw-placeholder` 开头，否则拒绝创建（防止误把真实密钥放进沙箱）。
7. **清理**：`close` 删除容器；进程退出时用 atexit + 标签 `tw.managed=true` 清理残留容器；`tw sandbox gc` 命令手动清理。
8. **并发**：`SandboxPool` 用信号量控制并发；默认 `max_concurrency = CPU 核数 / 2`。

## 6. 验收标准

- [ ] AC1：`network="none"` 时，沙箱内 `curl https://example.com` 失败，`pip download requests` 失败（集成测试）。
- [ ] AC2：`exec("sleep 10", timeout_s=1)` 在 3 秒内返回且 `timed_out=True`，容器内没有残留 sleep 进程。
- [ ] AC3：输出 1MB 的命令返回 `truncated=True`，返回大小 ≤ `max_output_bytes` + 100。
- [ ] AC4：`read_file("../../etc/passwd")` 和指向工作区外的符号链接都被拒绝。
- [ ] AC5：修改文件 → `snapshot("s1")` → 再修改 → `restore(ref)` 后内容回到 s1；当前分支 HEAD 不变。
- [ ] AC6：`diff()` 包含新增文件，不包含 `.tw/NOTES.md`。
- [ ] AC7：`env={"GITHUB_TOKEN": "ghp_xxx"}` 创建失败；`{"GITHUB_TOKEN": "tw-placeholder-1"}` 成功。
- [ ] AC8：容器以非 root 运行（`id -u` 不为 0）。
- [ ] AC9：并发 8 个沙箱各跑一次 `pytest --version`，全部成功且结束后无残留容器。

## 7. 测试计划

- 单测：路径校验、输出截断、env 校验（不需要 Docker 的纯函数部分）。
- 集成（`-m integration`）：上述 AC1–AC9。CI 上用 GitHub Actions 的 Docker。

## 8. 评测影响

评测的可复现性依赖：固定镜像 tag、资源限制一致、默认断网。镜像 digest 写入 Trajectory。

## 9. 开放问题

- 国内网络下拉基础镜像慢 → 文档里给出镜像加速配置；任务镜像预构建并缓存。
- 需要联网安装依赖的任务 → 在镜像构建阶段装好，运行阶段断网；确需联网走 allowlist（spec 014）。
- 是否默认使用 gVisor（runsc）？→ 作为可选项，在文档里说明如何开启。

## 10. AI 实施提示

- 使用 `docker` Python SDK（`docker` 包），用 `asyncio.to_thread` 包装阻塞调用。
- 不要用 `shell=True` 在宿主机执行任何拼接的命令。
- 集成测试使用 `python:3.12-slim` 镜像，测试结束必须清理容器。

## 11. 变更记录

- 2026-10-10：初稿
- 2026-10-10：按 ADR-0001（W1 接口与路径）与 ADR-0002（预算与模型策略）修订：`.tw/` 统一为沙箱 /workspace/.tw/（ADR-0001 #7）。
