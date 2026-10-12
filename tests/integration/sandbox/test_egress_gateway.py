"""spec 014 §3–§4 集成测试（W7-03 / W7-04）：network=allowlist 的 internal 网络 + 网关 sidecar。需要 Docker。

本 box：`sg docker -c "uv run pytest -m integration tests/integration/sandbox/test_egress_gateway.py"`；
Docker 自定义网络需要 iptables-legacy 的 DOCKER-USER ACCEPT 规则（见 sandbox/egress.py）。
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from pathlib import Path

import pytest

from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.docker import DockerSandbox, DockerSandboxBackend

pytestmark = pytest.mark.integration

SECRET = "ghp_ITEST" + uuid.uuid4().hex
PH = "tw-placeholder-echo"
ECHO = r"""
import hashlib, http.server
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        a = self.headers.get("Authorization", "")
        body = ("sha256=" + hashlib.sha256(a.encode()).hexdigest() + " path=" + self.path).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
http.server.HTTPServer(("0.0.0.0", 8080), H).serve_forever()
"""


@pytest.fixture(scope="module")
def env(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    import docker

    try:
        client = docker.from_env(timeout=30)
        client.ping()
    except Exception as e:  # pragma: no cover
        pytest.skip(f"Docker 不可用：{e}")
    net = client.networks.create(f"tw-itest-up-{uuid.uuid4().hex[:6]}", labels={"tw.managed": "true"})
    echo = client.containers.run("python:3.12-slim", ["python", "-c", ECHO], detach=True, network=net.name,
                                 labels={"tw.managed": "true"}, name=f"tw-echo-{uuid.uuid4().hex[:6]}")  # fmt: skip
    backend = DockerSandboxBackend(home=tmp_path_factory.mktemp("twhome"), gateway_extra_networks=[str(net.name)])
    yield backend, echo.name
    echo.remove(force=True)
    net.remove()


def _fake_ip_dns() -> bool:
    import ipaddress
    import socket

    try:
        return ipaddress.ip_address(socket.gethostbyname("pypi.org")) in ipaddress.ip_network("198.18.0.0/15")
    except OSError:
        return False


PY_GET = (
    "python - <<'EOF'\nimport urllib.request, sys\n"
    "req = urllib.request.Request(sys.argv[1] if len(sys.argv) > 1 else {url!r}, headers={hdr})\n"
    "try:\n    r = urllib.request.urlopen(req, timeout=20); print('STATUS', r.status); print(r.read(300).decode())\n"
    "except Exception as e:\n    print('ERR', type(e).__name__, e)\nEOF"
)


DIRECT = """python - <<'EOF'
import socket
s = socket.socket(); s.settimeout(5)
try:
    s.connect(("1.1.1.1", 443)); print("DIRECT_OK")
except OSError as e:
    print("DIRECT_FAIL", e)
EOF"""
DNS = """python - <<'EOF'
import socket
for h in ["c2VjcmV0.example.com", "pypi.org", "tw-gw"]:
    try:
        print(h, socket.gethostbyname(h))
    except OSError:
        print(h, "NXDOMAIN")
EOF"""


def get(url: str, hdr: dict[str, str] | None = None) -> str:
    return PY_GET.format(url=url, hdr=repr(hdr or {}))


async def test_allowlist_network_end_to_end(env, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    backend, echo_name = env
    monkeypatch.setenv("TW_ITEST_ECHO_TOKEN", SECRET)
    if _fake_ip_dns():  # 本 box 的 DNS 是 fake-IP（198.18.0.0/15），按 spec 014 §3.4 声明
        monkeypatch.setenv("TW_EGRESS_TREAT_AS_PUBLIC", "198.18.0.0/15")
    spec = SandboxSpec(
        memory_mb=512, cpus=1, network="allowlist", allowlist=["profile:pypi"], allow_private=[echo_name],
        env={"ECHO_TOKEN": PH},
        credentials=[{"name": "echo", "host": echo_name, "placeholder": PH, "secret_env": "TW_ITEST_ECHO_TOKEN",
                      "methods": ["GET"], "path_prefix": "/api"}],
    )  # fmt: skip
    sb = await backend.create(spec)
    assert isinstance(sb, DockerSandbox) and sb.gateway is not None
    try:
        # 1. 白名单内（经网关 CONNECT）：通
        r = await sb.exec(get("https://pypi.org/simple/pip/"), timeout_s=60)
        assert "STATUS 200" in r.stdout, r.stdout + r.stderr
        # 2. 白名单外：网关 403
        r = await sb.exec(get("https://example.com/"), timeout_s=60)
        assert "ERR" in r.stdout and "403" in r.stdout, r.stdout
        # 3. 绕过代理直连 IP：网络层不可达
        r = await sb.exec(DIRECT)
        assert "DIRECT_FAIL" in r.stdout, r.stdout
        # 4. DNS 外泄：外部名字解析不了（网关容器名可以）
        r = await sb.exec(DNS)
        assert "c2VjcmV0.example.com NXDOMAIN" in r.stdout and "pypi.org NXDOMAIN" in r.stdout, r.stdout
        assert "tw-gw NXDOMAIN" not in r.stdout
        # 5. 元数据地址：拒绝
        r = await sb.exec(get("http://169.254.169.254/latest/meta-data/"), timeout_s=30)
        assert "403" in r.stdout, r.stdout
        # 6. 凭证注入：沙箱只有占位符，上游收到真实值（只回 sha256，不回显）
        r = await sb.exec(get(f"http://{echo_name}:8080/api/x", {"Authorization": f"Bearer {PH}"}), timeout_s=30)
        want = hashlib.sha256(f"Bearer {SECRET}".encode()).hexdigest()
        assert f"sha256={want}" in r.stdout, r.stdout
        r = await sb.exec(get(f"http://{echo_name}:8080/other", {"Authorization": f"Bearer {PH}"}), timeout_s=30)
        assert "403" in r.stdout, r.stdout
        # 7. 沙箱里读不到真实密钥
        r = await sb.exec("env; cat /proc/1/environ | tr '\\0' '\\n'; echo $ECHO_TOKEN", timeout_s=30)
        assert SECRET not in r.stdout and PH in r.stdout
        audit = await asyncio.to_thread(sb.gateway.audit)
        assert audit and SECRET not in str(audit)
        reasons = {a.get("reason") for a in audit if a.get("kind") == "deny"}
        assert {"not_allowlisted", "ip_literal", "placeholder_misroute"} <= reasons, reasons
        assert any(a.get("injected") == "echo" for a in audit)
    finally:
        gw_name = sb.gateway.container.name if sb.gateway and sb.gateway.container else None
        net = sb.gateway.net_name if sb.gateway else None
        await sb.close()
    import docker

    c = docker.from_env()
    assert not c.containers.list(all=True, filters={"name": str(gw_name)}) and not c.networks.list(names=[str(net)])
    assert list(Path(backend._home, "gateway").glob("*.audit.jsonl"))  # type: ignore[arg-type]
    assert os.environ.get("TW_ITEST_ECHO_TOKEN") == SECRET
