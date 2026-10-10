"""沙箱环境自检与引导安装（UI-19 / W2-02 的检测部分）。

- `detect()`：docker 是否安装 / 守护进程是否在跑；Windows 上 WSL 与 winget 是否可用。只读，不联网，不调 API。
- `install_plan()`：给出 Windows 上的安装命令（winget Docker.DockerDesktop / `wsl --install`），
  通过 PowerShell `Start-Process -Verb RunAs` 触发 UAC 提权；调用方必须先得到用户明确确认才执行。
所有外部命令都经由可注入的 `Runner`，测试离线跑。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Literal

from triwitness.config import load_config

Runner = Callable[[list[str], float], "tuple[int, bytes]"]
Which = Callable[[str], "str | None"]
State = Literal["ok", "stopped", "missing", "n/a", "unknown"]
Target = Literal["docker", "wsl"]


def _default_run(cmd: list[str], timeout: float) -> tuple[int, bytes]:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=flags, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e).encode()
    return p.returncode, p.stdout + p.stderr


def decode(raw: bytes) -> str:
    """wsl.exe 在 Windows 上输出 UTF-16LE；其他命令是 UTF-8 / GBK。"""
    if raw[:2] == b"\xff\xfe" or (len(raw) % 2 == 0 and b"\x00" in raw):
        return raw.decode("utf-16-le", errors="replace").lstrip("\ufeff").replace("\x00", "")
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


@dataclass
class Component:
    state: State
    detail: str = ""
    version: str | None = None


@dataclass
class DoctorReport:
    platform: str
    docker: Component
    wsl: Component
    winget: Component
    recommended: list[Target] = field(default_factory=list)
    sandbox_ready: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def detect(*, platform: str | None = None, which: Which = shutil.which, run: Runner = _default_run) -> DoctorReport:
    plat = platform or sys.platform
    win = plat.startswith("win")
    docker: Component
    if which("docker") is None:
        docker = Component("missing", "未找到 docker 命令")
    else:
        rc, out = run(["docker", "info", "--format", "{{.ServerVersion}}"], 15)
        text = decode(out).strip()
        if rc == 0 and text:
            docker = Component("ok", "Docker 守护进程在运行", text.splitlines()[0][:40])
        else:
            docker = Component("stopped", "已安装，但守护进程未运行（请启动 Docker Desktop）")
    if not win:
        wsl = Component("n/a", "仅 Windows 需要")
        winget = Component("n/a", "仅 Windows 使用")
    else:
        if which("wsl") is None:
            wsl = Component("missing", "未找到 wsl.exe")
        else:
            rc, out = run(["wsl", "--status"], 15)
            text = decode(out)
            if rc == 0:
                ver = next((ln.split(":", 1)[-1].split("：", 1)[-1].strip() for ln in text.splitlines()
                            if "版本" in ln or "Version" in ln), None)  # fmt: skip
                wsl = Component("ok", "WSL 已启用", ver or None)
            else:
                wsl = Component("missing", "WSL 未启用（需要 wsl --install 并重启）")
        winget = Component("ok", "winget 可用") if which("winget") else Component("missing", "未找到 winget")
    rec: list[Target] = []
    if win and wsl.state == "missing":
        rec.append("wsl")
    if docker.state == "missing":
        rec.append("docker")
    return DoctorReport(plat, docker, wsl, winget, rec, sandbox_ready=docker.state == "ok")


@dataclass
class InstallPlan:
    target: Target
    supported: bool
    command: list[str]  # 实际执行（含提权包装）
    display: str  # 给用户看的命令
    needs_elevation: bool
    reboot_hint: bool
    note: str
    fallback_urls: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def elevated(cmd: list[str]) -> list[str]:
    """PowerShell Start-Process -Verb RunAs：弹出 UAC，等待结束并把退出码带回来。"""
    exe, args = cmd[0], " ".join(cmd[1:])
    script = (f"$p = Start-Process -FilePath {_ps_quote(exe)} -ArgumentList {_ps_quote(args)} "
              "-Verb RunAs -Wait -PassThru; exit $p.ExitCode")  # fmt: skip
    return ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]


def install_plan(target: Target, *, platform: str | None = None, report: DoctorReport | None = None) -> InstallPlan:
    plat = platform or sys.platform
    cfg = load_config("sandbox_install.yaml")
    if target == "docker":
        d = cfg.get("docker_desktop", {})
        urls = [f["url"] for f in d.get("fallback", []) if f.get("enabled", True)]
        if not plat.startswith("win"):
            mac = "macOS：从 Docker 官网下载 Docker Desktop"
            linux = "Linux：用发行版包管理器安装 docker（如 apt install docker.io），并把当前用户加入 docker 组"
            hint = mac if plat == "darwin" else linux
            return InstallPlan("docker", False, [], "", False, False, hint, urls)
        if report is not None and report.winget.state != "ok":
            return InstallPlan("docker", False, [], "", True, False, "未找到 winget：请从下面的地址手动下载安装", urls)
        inner = ["winget", "install", "-e", "--id", str(d.get("winget_id", "Docker.DockerDesktop")),
                 "--accept-package-agreements", "--accept-source-agreements"]  # fmt: skip
        return InstallPlan("docker", True, elevated(inner), " ".join(inner), True, True,
                           "安装后需要注销或重启，再启动 Docker Desktop", urls)  # fmt: skip
    w = cfg.get("wsl", {})
    urls = [f["url"] for f in w.get("fallback", []) if f.get("enabled", True)]
    if not plat.startswith("win"):
        return InstallPlan("wsl", False, [], "", False, False, "仅 Windows 需要 WSL2", urls)
    inner = ["wsl", "--install", "--no-distribution"]
    return InstallPlan("wsl", True, elevated(inner), " ".join(inner), True, True, "完成后需要重启 Windows", urls)


def run_install(plan: InstallPlan, *, run: Runner = _default_run, timeout: float = 1800) -> tuple[int, str]:
    if not plan.supported or not plan.command:
        raise ValueError("该平台不支持一键安装")
    rc, out = run(plan.command, timeout)
    return rc, decode(out)[-2000:]
