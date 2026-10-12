"""出网网关（spec 014 §3–§4，W7-03 / W7-04）：域名白名单的 HTTP(S) 正向代理 + 按规则注入凭证。

**只依赖标准库**：`sandbox/egress.py` 把这个文件原样拷进网关容器，用 `python egress_proxy.py --config cfg.json` 运行。

部署形态（参考 Eclipse Enclave 的 sidecar 网关）：沙箱只接在 Docker `internal` 网络上（没有默认路由、内置 DNS 不转发外部
查询），网关容器同时接 internal 网络和外网；沙箱里 `HTTP(S)_PROXY=http://tw-gw:3128`。所以：
  - 直连 IP、绕过代理、DNS 外泄在网络层就不通（不靠 HTTPS_PROXY 自觉）；
  - 经代理的请求先查白名单再解析域名（白名单外的域名网关连 DNS 都不查，`<secret>.evil.com` 泄不出去）；
  - 解析结果是私网 / 回环 / 链路本地 / 云元数据地址的一律拒绝（SSRF、DNS rebinding），连接用解析出的那个 IP。

凭证注入（不做 TLS 中间人）：
  - 沙箱里只有 `tw-placeholder-<名>`；要带凭证的服务用明文走网关：`http://<host>/…`（经代理，绝对形式）或
    `http://tw-gw:3128/svc/<名>/…`（服务绑定，反向代理），网关在“域名 + 方法 + 路径前缀”匹配时把请求头里的占位符换成
    真实值，再用 HTTPS 连上游；
  - 占位符出现在不匹配任何规则的请求里 → 拒绝（placeholder_misroute），防止把占位符当探针；
  - CONNECT 隧道里网关看不到内容，不注入；真实密钥只在网关进程的环境变量里；
  - 响应里如果回显了真实值（≤1 MiB 的非流式响应），替换回占位符。
审计：每个请求一行 JSONL（时间、类型、host、端口、方法、去掉查询串的路径、决定、原因、注入规则名、耗时），从不记密钥。
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import ipaddress
import json
import os
import socket
import ssl
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

PLACEHOLDER_PREFIX = "tw-placeholder"
DEFAULT_PORTS = (80, 443)
MAX_HEADER = 64 * 1024
MAX_BODY = 32 * 1024 * 1024
ECHO_SCAN_LIMIT = 1024 * 1024
# 永远拒绝的目标（即使白名单写了）：云元数据
METADATA_HOSTS = frozenset({"metadata.google.internal", "metadata", "instance-data", "metadata.azure.internal"})


# ---------------------------------------------------------------------------------------------- 策略
@dataclass
class CredentialRule:
    """凭证注入规则：域名 + 方法 + 路径前缀都匹配才把 header 里的占位符换成真实值。"""

    name: str
    host: str
    placeholder: str
    secret_env: str
    methods: tuple[str, ...] = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")
    path_prefix: str = "/"
    header: str = "Authorization"
    scheme: str = "bearer"  # bearer：Bearer <值>；raw：整个 header 值就是占位符所在处直接替换
    upstream: str = ""  # 服务绑定的上游基址（https://api.example.com/v1），/svc/<name>/ 用

    def matches(self, host: str, method: str, path: str) -> bool:
        return (
            host_match(host, self.host)
            and method.upper() in {m.upper() for m in self.methods}
            and _path_under(path, self.path_prefix)
        )


@dataclass
class EgressConfig:
    allow: list[str] = field(default_factory=list)
    ports: tuple[int, ...] = DEFAULT_PORTS
    allow_private: list[str] = field(default_factory=list)  # 测试 / 内网服务：显式写出的主机名才允许私网地址
    credentials: list[CredentialRule] = field(default_factory=list)
    audit_path: str = ""
    upstream_tls_verify: bool = True
    # 本机代理的 fake-IP DNS（Clash TUN 等把所有域名解析到 198.18.0.0/15）：这些网段当公网看待。默认空。
    treat_as_public: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EgressConfig:
        rules = [CredentialRule(**{**r, "methods": tuple(r.get("methods") or CredentialRule.methods)})
                 for r in d.get("credentials", [])]  # fmt: skip
        return cls(allow=list(d.get("allow", [])), ports=tuple(d.get("ports", DEFAULT_PORTS)),
                   allow_private=list(d.get("allow_private", [])), credentials=rules,
                   audit_path=str(d.get("audit_path", "")),
                   upstream_tls_verify=bool(d.get("upstream_tls_verify", True)),
                   treat_as_public=list(d.get("treat_as_public", [])))  # fmt: skip

    def to_dict(self) -> dict[str, Any]:
        return {"allow": self.allow, "ports": list(self.ports), "allow_private": self.allow_private,
                "credentials": [r.__dict__ | {"methods": list(r.methods)} for r in self.credentials],
                "audit_path": self.audit_path, "upstream_tls_verify": self.upstream_tls_verify,
                "treat_as_public": self.treat_as_public}  # fmt: skip


def _path_under(path: str, prefix: str) -> bool:
    p = path.split("?", 1)[0]
    if ".." in p.split("/"):
        return False
    return prefix in ("", "/") or p == prefix.rstrip("/") or p.startswith(prefix.rstrip("/") + "/")


def normalize_host(host: str) -> str:
    h = host.strip().lower().rstrip(".")
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    return h


def host_match(host: str, pattern: str) -> bool:
    """`example.com` 只匹配自身；`*.example.com` 匹配子域（不含自身）。不做部分匹配，`evilexample.com` 不算。"""
    h, p = normalize_host(host), normalize_host(pattern)
    if p.startswith("*."):
        return h.endswith(p[1:]) and h != p[2:]
    return h == p


def is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(normalize_host(host))
        return True
    except ValueError:
        return False


def is_forbidden_ip(ip: str, treat_as_public: list[str] | tuple[str, ...] = ()) -> bool:
    """私网 / 回环 / 链路本地（含 169.254.169.254 元数据）/ 组播 / 保留 / 未指定 / CGNAT / IPv4 映射到这些的 IPv6。

    `treat_as_public` 里的网段（fake-IP DNS）除外，但回环和链路本地（元数据）永远拒绝。
    """
    a = ipaddress.ip_address(ip)
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped is not None:
        a = a.ipv4_mapped
    if not (a.is_loopback or a.is_link_local) and any(a in ipaddress.ip_network(n, strict=False)
                                                       for n in treat_as_public):  # fmt: skip
        return False
    cgnat = isinstance(a, ipaddress.IPv4Address) and a in ipaddress.ip_network("100.64.0.0/10")
    return bool(a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved
                or a.is_unspecified or cgnat)  # fmt: skip


@dataclass
class Verdict:
    allow: bool
    reason: str


def check_target(cfg: EgressConfig, host: str, port: int) -> Verdict:
    """解析之前的检查：域名白名单、端口、IP 字面量、元数据主机名。"""
    h = normalize_host(host)
    if not h:
        return Verdict(False, "empty_host")
    if h in METADATA_HOSTS:
        return Verdict(False, "metadata_host")
    if is_ip_literal(h) and not any(host_match(h, p) for p in cfg.allow_private):
        return Verdict(False, "ip_literal")  # 白名单只认域名；直连 IP 一律拒绝
    if port not in cfg.ports and not any(host_match(h, p) for p in cfg.allow_private):
        return Verdict(False, f"port_{port}")
    if not any(host_match(h, p) for p in [*cfg.allow, *cfg.allow_private]):
        return Verdict(False, "not_allowlisted")
    return Verdict(True, "allowlisted")


async def resolve_checked(cfg: EgressConfig, host: str, port: int) -> tuple[str | None, str]:
    """解析并检查每个地址；任何一个落在禁区就整体拒绝（防 rebinding 时混入私网地址）。返回 (ip, 原因)。"""
    h = normalize_host(host)
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(h, port, type=socket.SOCK_STREAM)
    except OSError:
        return None, "dns_fail"
    ips = sorted({str(i[4][0]) for i in infos})
    if not ips:
        return None, "dns_empty"
    private_ok = any(host_match(h, p) for p in cfg.allow_private)
    if not private_ok and any(is_forbidden_ip(ip, cfg.treat_as_public) for ip in ips):
        return None, "resolves_to_private"
    return ips[0], "ok"


def find_placeholders(text: str) -> list[str]:
    out, i = [], 0
    while True:
        i = text.find(PLACEHOLDER_PREFIX, i)
        if i < 0:
            return out
        j = i
        while j < len(text) and (text[j].isalnum() or text[j] in "-_."):
            j += 1
        out.append(text[i:j])
        i = j


def inject(cfg: EgressConfig, host: str, method: str, path: str, headers: list[tuple[str, str]],
           environ: dict[str, str] | None = None) -> tuple[list[tuple[str, str]] | None, str, str]:  # fmt: skip
    """返回 (新 headers / None=拒绝, 原因, 用到的规则名)。只替换规则指定的 header；占位符出现在别处一律拒绝。"""
    env = os.environ if environ is None else environ
    used = ""
    out: list[tuple[str, str]] = []
    for k, v in headers:
        phs = find_placeholders(v)
        if not phs:
            out.append((k, v))
            continue
        rule = next((r for r in cfg.credentials if r.placeholder in phs and r.matches(host, method, path)
                     and r.header.lower() == k.lower()), None)  # fmt: skip
        if rule is None:
            return None, "placeholder_misroute", ""
        secret = env.get(rule.secret_env, "")
        if not secret:
            return None, "secret_missing", rule.name
        out.append((k, v.replace(rule.placeholder, secret)))
        used = rule.name
    return out, "ok", used


# ---------------------------------------------------------------------------------------------- 审计
class Audit:
    def __init__(self, path: str) -> None:
        self.path = path

    def write(self, **rec: Any) -> None:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **rec}
        line = json.dumps(rec, ensure_ascii=False)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        else:
            print(line, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------------------------- 代理
@dataclass
class Request:
    method: str
    target: str
    version: str
    headers: list[tuple[str, str]]

    def header(self, name: str) -> str | None:
        return next((v for k, v in self.headers if k.lower() == name.lower()), None)


async def read_head(reader: asyncio.StreamReader) -> Request | None:
    try:
        raw = await reader.readuntil(b"\r\n\r\n")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        return None
    if len(raw) > MAX_HEADER:
        return None
    lines = raw.decode("latin-1").split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) != 3:
        return None
    headers = []
    for ln in lines[1:]:
        if not ln:
            continue
        k, _, v = ln.partition(":")
        headers.append((k.strip(), v.strip()))
    return Request(parts[0].upper(), parts[1], parts[2], headers)


HOP = {"proxy-connection", "proxy-authorization", "connection", "keep-alive", "te", "trailer", "upgrade"}


class EgressProxy:
    def __init__(self, cfg: EgressConfig, environ: dict[str, str] | None = None) -> None:
        self.cfg = cfg
        self.env = dict(os.environ) if environ is None else environ
        self.audit = Audit(cfg.audit_path)
        self.secrets = {self.env[r.secret_env] for r in cfg.credentials if self.env.get(r.secret_env)}

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        t0 = time.monotonic()
        try:
            req = await read_head(reader)
            if req is None:
                await self._reply(writer, 400, "bad request")
                return
            if req.method == "CONNECT":
                await self._connect(req, reader, writer, t0)
            elif req.target.startswith("/svc/"):
                await self._svc(req, reader, writer, t0)
            elif req.target.startswith("http://"):
                await self._http(req, reader, writer, t0)
            elif req.target == "/healthz":
                await self._reply(writer, 200, "ok")
            else:
                await self._deny(writer, req, "", 0, "unsupported_target", t0)
        except Exception as e:  # 网关自身出错也拒绝（fail closed）
            self.audit.write(kind="error", error=type(e).__name__)
            with contextlib.suppress(Exception):
                await self._reply(writer, 502, "gateway error")
        finally:
            with contextlib.suppress(Exception):
                writer.close()

    async def _reply(self, writer: asyncio.StreamWriter, code: int, msg: str) -> None:
        body = (msg + "\n").encode()
        writer.write(f"HTTP/1.1 {code} {msg}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n"
                     f"X-TW-Gateway: deny\r\n\r\n".encode() + body)  # fmt: skip
        await writer.drain()

    async def _deny(self, writer: asyncio.StreamWriter, req: Request, host: str, port: int, reason: str,
                    t0: float) -> None:  # fmt: skip
        self.audit.write(kind="deny", method=req.method, host=host, port=port, path=_path_only(req.target),
                         reason=reason, ms=round((time.monotonic() - t0) * 1000, 1))  # fmt: skip
        await self._reply(writer, 403, f"blocked by tw gateway: {reason}")

    async def _connect(self, req: Request, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                       t0: float) -> None:  # fmt: skip
        host, _, p = req.target.rpartition(":")
        port = int(p) if p.isdigit() else 443
        v = check_target(self.cfg, host, port)
        if not v.allow:
            await self._deny(writer, req, host, port, v.reason, t0)
            return
        ip, why = await resolve_checked(self.cfg, host, port)
        if ip is None:
            await self._deny(writer, req, host, port, why, t0)
            return
        try:
            ur, uw = await asyncio.wait_for(asyncio.open_connection(ip, port), 15)
        except (OSError, TimeoutError):
            await self._deny(writer, req, host, port, "upstream_unreachable", t0)
            return
        writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        await writer.drain()
        self.audit.write(kind="connect", host=normalize_host(host), port=port, ip=ip, decision="allow",
                         ms=round((time.monotonic() - t0) * 1000, 1))  # fmt: skip
        await _pipe_both(reader, writer, ur, uw)

    async def _body(self, req: Request, reader: asyncio.StreamReader) -> bytes | None:
        if (req.header("Transfer-Encoding") or "").lower().find("chunked") >= 0:
            return None
        n = int(req.header("Content-Length") or 0)
        if n > MAX_BODY:
            return None
        return await reader.readexactly(n) if n else b""

    async def _http(self, req: Request, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                    t0: float) -> None:  # fmt: skip
        u = urlsplit(req.target)
        host = u.hostname or ""
        try:
            port = u.port or 80
        except ValueError:
            await self._deny(writer, req, host, 0, "bad_port", t0)
            return
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        has_rule = any(host_match(host, r.host) for r in self.cfg.credentials)
        upstream_tls = has_rule and port == 80  # 带凭证的服务：沙箱明文到网关，网关 HTTPS 到上游
        await self._forward(req, reader, writer, t0, host, 443 if upstream_tls else port, path, upstream_tls)

    async def _svc(self, req: Request, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                   t0: float) -> None:  # fmt: skip
        name, _, tail = req.target[len("/svc/") :].partition("/")
        rule = next((r for r in self.cfg.credentials if r.name == name and r.upstream), None)
        if rule is None:
            await self._deny(writer, req, "", 0, "unknown_binding", t0)
            return
        base = rule.upstream.rstrip("/")
        scheme, _, rest = base.partition("://")
        hostport, _, bpath = rest.partition("/")
        host, _, p = hostport.partition(":")
        tls = scheme == "https"
        port = int(p) if p else (443 if tls else 80)
        path = ("/" + bpath if bpath else "") + "/" + tail
        await self._forward(req, reader, writer, t0, host, port, path, tls)

    async def _forward(self, req: Request, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, t0: float,
                       host: str, port: int, path: str, tls: bool) -> None:  # fmt: skip
        v = check_target(self.cfg, host, port)
        if not v.allow:
            await self._deny(writer, req, host, port, v.reason, t0)
            return
        headers = [(k, val) for k, val in req.headers if k.lower() not in HOP and k.lower() != "host"]
        new, why, used = inject(self.cfg, host, req.method, path, headers, self.env)
        if new is None:
            await self._deny(writer, req, host, port, why, t0)
            return
        body = await self._body(req, reader)
        if body is None:
            await self._deny(writer, req, host, port, "chunked_or_too_large", t0)
            return
        if find_placeholders(body.decode("latin-1")) and not used:
            await self._deny(writer, req, host, port, "placeholder_in_body", t0)
            return
        ip, why = await resolve_checked(self.cfg, host, port)
        if ip is None:
            await self._deny(writer, req, host, port, why, t0)
            return
        ctx = None
        if tls:
            ctx = ssl.create_default_context()
            if not self.cfg.upstream_tls_verify:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
        try:
            ur, uw = await asyncio.wait_for(
                asyncio.open_connection(ip, port, ssl=ctx, server_hostname=normalize_host(host) if tls else None), 15
            )
        except (OSError, TimeoutError, ssl.SSLError):
            await self._deny(writer, req, host, port, "upstream_unreachable", t0)
            return
        default_port = 443 if tls else 80
        host_hdr = normalize_host(host) if port == default_port else f"{normalize_host(host)}:{port}"
        head = [f"{req.method} {path} HTTP/1.1", f"Host: {host_hdr}", "Connection: close"]
        head += [f"{k}: {val}" for k, val in new]
        if body and not any(k.lower() == "content-length" for k, _ in new):
            head.append(f"Content-Length: {len(body)}")
        uw.write(("\r\n".join(head) + "\r\n\r\n").encode("latin-1") + body)
        await uw.drain()
        n = await self._relay_response(ur, writer)
        with contextlib.suppress(Exception):
            uw.close()
        self.audit.write(kind="http", method=req.method, host=normalize_host(host), port=port, tls=tls,
                         path=_path_only(path), decision="allow", injected=used or None, bytes=n,
                         ms=round((time.monotonic() - t0) * 1000, 1))  # fmt: skip

    async def _relay_response(self, ur: asyncio.StreamReader, writer: asyncio.StreamWriter) -> int:
        """转发响应；前 1 MiB 里回显的真实密钥换成等长的 *（不改 Content-Length）。之后的部分原样流式转发。"""
        buf = bytearray()
        while len(buf) < ECHO_SCAN_LIMIT and (chunk := await ur.read(65536)):
            buf += chunk
        data = bytes(buf)
        for s in self.secrets:
            data = data.replace(s.encode(), b"*" * len(s.encode()))
        writer.write(data)
        await writer.drain()
        total = len(data)
        while chunk := await ur.read(65536):
            total += len(chunk)
            writer.write(chunk)
            await writer.drain()
        return total


def _path_only(target: str) -> str:
    t = target
    if "://" in t:
        t = "/" + t.split("://", 1)[1].partition("/")[2]
    return t.split("?", 1)[0][:200]


async def _pipe(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
    try:
        while chunk := await r.read(65536):
            w.write(chunk)
            await w.drain()
    except (OSError, asyncio.IncompleteReadError):
        pass
    finally:
        with contextlib.suppress(Exception):
            w.close()


async def _pipe_both(cr: asyncio.StreamReader, cw: asyncio.StreamWriter, ur: asyncio.StreamReader,
                     uw: asyncio.StreamWriter) -> None:  # fmt: skip
    await asyncio.gather(_pipe(cr, uw), _pipe(ur, cw))


async def serve(cfg: EgressConfig, host: str = "0.0.0.0", port: int = 3128,
                environ: dict[str, str] | None = None) -> asyncio.Server:  # fmt: skip
    proxy = EgressProxy(cfg, environ)
    return await asyncio.start_server(proxy.handle, host, port, limit=MAX_HEADER)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TriWitness 出网网关")
    ap.add_argument("--config", required=True)
    ap.add_argument("--listen", default="0.0.0.0:3128")
    a = ap.parse_args(argv)
    with open(a.config, encoding="utf-8") as f:
        cfg = EgressConfig.from_dict(json.load(f))
    h, _, p = a.listen.rpartition(":")

    async def run() -> None:
        srv = await serve(cfg, h, int(p))
        print(f"tw-gateway listening on {a.listen}", file=sys.stderr, flush=True)
        async with srv:
            await srv.serve_forever()

    asyncio.run(run())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
