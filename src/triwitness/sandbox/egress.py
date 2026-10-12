"""network=allowlist 的 Docker 落地（spec 014 §3，W7-03 / W7-04）：internal 网络 + 网关 sidecar。

拓扑（参考 Eclipse Enclave 的默认 Docker 后端：每个会话一个过滤网关 sidecar）：

    沙箱容器 ──(tw-net-<id>, internal=True)── 网关容器 tw-gw ──(bridge)── 外网

- internal 网络没有默认路由：沙箱直连任何 IP 都是 “Network is unreachable”；
- 沙箱的 DNS 上游设成 127.0.0.1（Docker 内置 DNS 只回答同网络容器名，外部名字无处可转），DNS 外泄不通；
- 沙箱里只有 `HTTP(S)_PROXY=http://tw-gw:3128` 和 `tw-placeholder-*`；网关进程按白名单放行、按规则注入凭证；
- 网关容器只有标准库：把 `gateway/egress_proxy.py` 和生成的 config.json 拷进去，非 root、cap_drop ALL；
- 真实密钥：按规则的 secret_env 从宿主环境读，只作为网关容器的环境变量；缺失就不注入（请求会被拒绝）。

本 box 上的注意：Docker 自定义网络需要 iptables-legacy 的 `DOCKER-USER -j ACCEPT` 规则（旧 FORWARD DROP 会把
自定义网桥的流量全丢，重启后失效），否则网关自己也出不了网。`tw sandbox doctor` 之外，这里创建失败时会提示。
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tarfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from docker.errors import DockerException, ImageNotFound, NotFound

from triwitness.core.errors import SandboxError
from triwitness.sandbox.base import SandboxSpec

GW_ALIAS = "tw-gw"
GW_PORT = 3128
GW_IMAGE = "python:3.12-slim"
GW_USER = "65534:65534"
LABEL = "tw.managed"
PROXY_URL = f"http://{GW_ALIAS}:{GW_PORT}"


def proxy_env() -> dict[str, str]:
    return {k: PROXY_URL for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY")} | {
        "NO_PROXY": "",
        "no_proxy": "",
        "PIP_PROXY": PROXY_URL,
    }


def load_profiles(path: Path | None = None) -> dict[str, list[str]]:
    from triwitness.config import config_dir

    p = path or config_dir() / "policies" / "egress.yaml"
    if not p.is_file():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {str(k): [str(x) for x in (v or {}).get("allow", [])] for k, v in (data.get("profiles") or {}).items()}


def expand_allowlist(items: list[str], profiles: dict[str, list[str]] | None = None) -> list[str]:
    """`profile:pypi` 展开成该档的域名；其余原样。去重保序。"""
    prof = load_profiles() if profiles is None else profiles
    out: list[str] = []
    for it in items:
        if it.startswith("profile:"):
            name = it.split(":", 1)[1]
            if name not in prof:
                raise SandboxError(f"未知出网档位 {name}（configs/policies/egress.yaml）")
            out += prof[name]
        else:
            out.append(it)
    return list(dict.fromkeys(out))


def treat_as_public(environ: dict[str, str] | None = None) -> list[str]:
    """fake-IP 网段：egress.yaml 的 treat_as_public + 环境变量 TW_EGRESS_TREAT_AS_PUBLIC（逗号分隔）。"""
    from triwitness.config import config_dir

    env = os.environ if environ is None else environ
    out: list[str] = []
    p = config_dir() / "policies" / "egress.yaml"
    if p.is_file():
        out += [str(x) for x in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("treat_as_public") or []]
    out += [x.strip() for x in env.get("TW_EGRESS_TREAT_AS_PUBLIC", "").split(",") if x.strip()]
    return list(dict.fromkeys(out))


def gateway_config(spec: SandboxSpec, profiles: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """网关的 config.json（纯函数，便于测试）。服务绑定的上游主机自动加进白名单。"""
    allow = expand_allowlist(spec.allowlist, profiles)
    for r in spec.credentials:
        allow.append(str(r["host"]))
        up = str(r.get("upstream") or "")
        if up:
            allow.append(up.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0])
    return {"allow": list(dict.fromkeys(allow)), "allow_private": list(spec.allow_private),
            "credentials": [dict(r) for r in spec.credentials], "audit_path": "/gw/audit.jsonl",
            "treat_as_public": treat_as_public()}  # fmt: skip


def gateway_secrets(spec: SandboxSpec, environ: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ if environ is None else environ
    out = {}
    for r in spec.credentials:
        name = str(r.get("secret_env") or "")
        if name and env.get(name):
            out[name] = env[name]
    return out


def check_placeholders(spec: SandboxSpec) -> None:
    """沙箱 env 里出现的占位符必须都有对应规则（否则说明配置漏了，请求会被拒，提前报错更好排查）。"""
    known = {str(r.get("placeholder")) for r in spec.credentials}
    for k, v in spec.env.items():
        if v.startswith("tw-placeholder") and spec.credentials and v not in known:
            raise SandboxError(f"沙箱 env {k} 的占位符 {v} 没有对应的凭证规则")


def proxy_source(module_file: Path) -> bytes:
    """网关源码：源码运行时就是模块文件；PyInstaller 冻结包里用 build_core.py 单独带的那份。"""
    from triwitness.config import resource_root

    for p in (module_file.with_suffix(".py"), resource_root() / "triwitness" / "gateway" / "egress_proxy.py"):
        if p.is_file():
            return p.read_bytes()
    raise SandboxError("找不到出网网关源码 egress_proxy.py（打包时漏了 --add-data？）")


def sandbox_network_kwargs(net_name: str) -> dict[str, Any]:
    return {"network_mode": net_name, "dns": ["127.0.0.1"], "environment": proxy_env()}


def _tar(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    uid, gid = (int(x) for x in GW_USER.split(":"))
    with tarfile.open(fileobj=buf, mode="w") as tf:
        d = tarfile.TarInfo("gw")
        d.type, d.mode, d.uid, d.gid, d.mtime = tarfile.DIRTYPE, 0o755, uid, gid, int(time.time())
        tf.addfile(d)
        for name, data in files.items():
            ti = tarfile.TarInfo(f"gw/{name}")
            ti.size, ti.mode, ti.uid, ti.gid, ti.mtime = len(data), 0o644, uid, gid, int(time.time())
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


@dataclass
class EgressGateway:
    """一个沙箱会话的 internal 网络 + 网关容器。"""

    client: Any
    net_name: str
    network: Any = None
    container: Any = None
    audit_dir: Path | None = None
    extra_networks: list[str] = field(default_factory=list)

    @classmethod
    def start(cls, client: Any, spec: SandboxSpec, *, extra_networks: list[str] | None = None,
              audit_dir: Path | None = None, environ: dict[str, str] | None = None) -> EgressGateway:  # fmt: skip
        """同步（在线程里调用）。失败时清理已建的资源。"""
        check_placeholders(spec)
        gw = cls(client, f"tw-net-{uuid.uuid4().hex[:10]}", audit_dir=audit_dir,
                 extra_networks=list(extra_networks or []))  # fmt: skip
        try:
            gw._start(spec, environ)
        except Exception:
            gw.close()
            raise
        return gw

    def _start(self, spec: SandboxSpec, environ: dict[str, str] | None) -> None:
        from triwitness.gateway import egress_proxy

        c = self.client
        self.network = c.networks.create(self.net_name, driver="bridge", internal=True, labels={LABEL: "true"})
        try:
            c.images.get(GW_IMAGE)
        except ImageNotFound:
            c.images.pull(GW_IMAGE)
        cfg = json.dumps(gateway_config(spec), ensure_ascii=False).encode()
        src = proxy_source(Path(egress_proxy.__file__))
        self.container = c.containers.create(
            GW_IMAGE,
            command=[
                "python",
                "-u",
                "/gw/egress_proxy.py",
                "--config",
                "/gw/config.json",
                "--listen",
                f"0.0.0.0:{GW_PORT}",
            ],
            user=GW_USER,
            detach=True,
            init=True,
            labels={LABEL: "true", "tw.role": "egress-gateway"},
            environment=gateway_secrets(spec, environ),
            network="bridge",
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            pids_limit=256,
            mem_limit="256m",
            name=f"tw-gw-{uuid.uuid4().hex[:10]}",
        )
        self.container.put_archive("/", _tar({"egress_proxy.py": src, "config.json": cfg}))
        self.network.connect(self.container, aliases=[GW_ALIAS])
        for n in self.extra_networks:
            c.networks.get(n).connect(self.container)
        self.container.start()
        self._wait_ready()

    def _wait_ready(self, timeout_s: float = 20) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.container.reload()
            if self.container.status == "exited":
                logs = self.container.logs().decode("utf-8", "replace")[-800:]
                raise SandboxError(f"出网网关启动失败：{logs}")
            if b"listening" in self.container.logs():
                return
            time.sleep(0.2)
        raise SandboxError("出网网关 20 秒内没有就绪")

    def audit(self) -> list[dict[str, Any]]:
        """取回网关审计（JSONL）。"""
        if self.container is None:
            return []
        try:
            stream, _ = self.container.get_archive("/gw/audit.jsonl")
        except (NotFound, DockerException):
            return []
        raw = b"".join(stream)
        with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
            m = tf.getmembers()[0]
            f = tf.extractfile(m)
            text = f.read().decode("utf-8") if f else ""
        out = []
        for line in text.splitlines():
            with contextlib.suppress(json.JSONDecodeError):
                out.append(json.loads(line))
        return out

    def close(self) -> None:
        if self.container is not None:
            if self.audit_dir is not None:
                with contextlib.suppress(Exception):
                    self.audit_dir.mkdir(parents=True, exist_ok=True)
                    (self.audit_dir / f"{self.net_name}.audit.jsonl").write_text(
                        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in self.audit()), encoding="utf-8"
                    )
            with contextlib.suppress(NotFound, DockerException):
                self.container.remove(force=True)
            self.container = None
        if self.network is not None:
            with contextlib.suppress(NotFound, DockerException):
                self.network.remove()
            self.network = None


__all__ = [
    "GW_ALIAS",
    "PROXY_URL",
    "EgressGateway",
    "check_placeholders",
    "expand_allowlist",
    "gateway_config",
    "gateway_secrets",
    "load_profiles",
    "proxy_env",
    "sandbox_network_kwargs",
]
