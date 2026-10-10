"""本机自托管 Langfuse 的辅助脚本（W2-18，spec 005 AC4）。不需要 Langfuse 账号：用 LANGFUSE_INIT_* 无头初始化。

    python scripts/langfuse_local.py env          # 生成 deploy/langfuse/.env（随机口令与项目密钥，0600，不打印）
    docker compose -f deploy/langfuse/docker-compose.yml --env-file deploy/langfuse/.env up -d
    uv run python scripts/langfuse_local.py smoke    # golden 轨迹 → OTLP → Langfuse；用公开 API 校验 trace 树
    uv run --with playwright python scripts/langfuse_local.py screenshot   # 无头 Chrome 截图到 docs/images/

真实任务接入：`export TW_OTLP_ENDPOINT=http://127.0.0.1:3000/api/public/otel` 与
`OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <base64(pk:sk)>"`
（`env` 子命令会把这两行写进 .env 供 source；密钥不进仓库）。
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "deploy" / "langfuse" / ".env"
GOLDEN = ROOT / "evals" / "fixtures" / "events" / "recorded.jsonl"
SHOT = ROOT / "docs" / "images" / "langfuse-trace-tree.png"


def read_env() -> dict[str, str]:
    if not ENV.exists():
        raise SystemExit(f"缺少 {ENV}：先运行 `python scripts/langfuse_local.py env`")
    out = {}
    for ln in ENV.read_text().splitlines():
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            out[k.removeprefix("export ").strip()] = v.strip().strip('"')
    return out


def cmd_env() -> None:
    if ENV.exists():
        print(f"{ENV} 已存在，不覆盖")
        return
    h = lambda n: secrets.token_hex(n)  # noqa: E731
    pg, minio = h(16), h(16)
    pk, sk = f"pk-lf-{h(16)}", f"sk-lf-{h(16)}"
    port = os.environ.get("LANGFUSE_PORT", "3000")
    auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()
    lines = {
        "LANGFUSE_PORT": port, "NEXTAUTH_URL": f"http://localhost:{port}",
        "SALT": h(16), "ENCRYPTION_KEY": h(32), "NEXTAUTH_SECRET": h(32),
        "POSTGRES_PASSWORD": pg, "DATABASE_URL": f"postgresql://postgres:{pg}@postgres:5432/postgres",
        "CLICKHOUSE_PASSWORD": h(16), "REDIS_AUTH": h(16), "MINIO_ROOT_PASSWORD": minio,
        "LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY": minio, "LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY": minio,
        "LANGFUSE_S3_BATCH_EXPORT_SECRET_ACCESS_KEY": minio,
        "LANGFUSE_INIT_ORG_ID": "triwitness", "LANGFUSE_INIT_ORG_NAME": "TriWitness",
        "LANGFUSE_INIT_PROJECT_ID": "triwitness-local", "LANGFUSE_INIT_PROJECT_NAME": "triwitness-local",
        "LANGFUSE_INIT_PROJECT_PUBLIC_KEY": pk, "LANGFUSE_INIT_PROJECT_SECRET_KEY": sk,
        "LANGFUSE_INIT_USER_EMAIL": "local@triwitness.invalid", "LANGFUSE_INIT_USER_NAME": "local",
        "LANGFUSE_INIT_USER_PASSWORD": h(12),
        # 供 `set -a; source deploy/langfuse/.env` 后直接让 tw 导出 trace
        "TW_OTLP_ENDPOINT": f"http://127.0.0.1:{port}/api/public/otel",
        "OTEL_EXPORTER_OTLP_HEADERS": f"Authorization=Basic {auth}",
    }  # fmt: skip
    ENV.parent.mkdir(parents=True, exist_ok=True)
    ENV.touch(mode=0o600)
    ENV.write_text(
        "# 本机 Langfuse 口令与密钥（自动生成；不要提交、不要打印）\n" + "".join(f"{k}={v}\n" for k, v in lines.items())
    )
    os.chmod(ENV, 0o600)
    print(f"已生成 {ENV.relative_to(ROOT)}（0600）")


def api(env: dict[str, str], path: str) -> dict:
    base = f"http://127.0.0.1:{env.get('LANGFUSE_PORT', '3000')}"
    auth = base64.b64encode(
        f"{env['LANGFUSE_INIT_PROJECT_PUBLIC_KEY']}:{env['LANGFUSE_INIT_PROJECT_SECRET_KEY']}".encode()
    )
    req = urllib.request.Request(base + path, headers={"Authorization": "Basic " + auth.decode()})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def cmd_smoke() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    from triwitness.telemetry.otel import OtelBridge
    from triwitness.telemetry.trajectory import Trajectory

    env = read_env()
    for _ in range(60):  # 等 web 起来
        try:
            api(env, "/api/public/health")
            break
        except Exception:
            time.sleep(5)
    else:
        raise SystemExit("Langfuse 没有起来（/api/public/health 不通）")
    auth = base64.b64encode(
        f"{env['LANGFUSE_INIT_PROJECT_PUBLIC_KEY']}:{env['LANGFUSE_INIT_PROJECT_SECRET_KEY']}".encode()
    )
    exporter = OTLPSpanExporter(endpoint=f"{env['TW_OTLP_ENDPOINT']}/v1/traces",
                                headers={"Authorization": "Basic " + auth.decode()})  # fmt: skip
    provider = TracerProvider(resource=Resource.create({"service.name": "triwitness"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    bridge = OtelBridge(provider)
    events = Trajectory.read_events(GOLDEN)
    for ev in events:
        bridge.observe(ev)
    provider.shutdown()
    trace_id = None
    obs: list[dict] = []
    for _ in range(40):  # 摄入是异步的（worker → ClickHouse）
        traces = api(env, "/api/public/traces?limit=20").get("data", [])
        hit = [t for t in traces if t.get("name") == "tw.task"]
        if hit:
            trace_id = hit[0]["id"]
            obs = api(env, f"/api/public/traces/{trace_id}").get("observations", [])
            if len(obs) >= 10:
                break
        time.sleep(3)
    if trace_id is None:
        raise SystemExit("Langfuse 里没找到 tw.task trace")
    by_id = {o["id"]: o for o in obs}
    names = sorted(o["name"] for o in obs)
    agent = next(o for o in obs if o["name"] == "invoke_agent executor")
    root = by_id.get(agent.get("parentObservationId") or "")
    children = [o for o in obs if o.get("parentObservationId") == agent["id"]]
    chats = [o for o in children if o["name"].startswith("chat ")]
    tools = [o for o in children if o["name"].startswith("execute_tool ")]
    print(f"trace {trace_id}：{len(obs)} 个 observation；root={root and root['name']}；"
          f"agent 下 chat {len(chats)} 个、execute_tool {len(tools)} 个")  # fmt: skip
    assert root is not None and root["name"] == "tw.task", names
    assert len(chats) == 5 and len(tools) == 6, names
    out = ROOT / "evals" / "fixtures" / "langfuse_trace_tree.json"
    tree = {"trace_name": "tw.task", "children": {"invoke_agent executor": sorted(o["name"] for o in children)}}
    out.write_text(json.dumps(tree, ensure_ascii=False, indent=1) + "\n")
    (ROOT / "deploy" / "langfuse" / ".last_trace").write_text(trace_id)
    print("AC4 树结构校验通过：tw.task → invoke_agent executor → chat / execute_tool")


def cmd_screenshot() -> None:
    from playwright.sync_api import sync_playwright  # pyright: ignore[reportMissingImports]

    env = read_env()
    base = f"http://localhost:{env.get('LANGFUSE_PORT', '3000')}"
    trace_id = (ROOT / "deploy" / "langfuse" / ".last_trace").read_text().strip()
    SHOT.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        pg = b.new_page(viewport={"width": 1600, "height": 1000})
        pg.goto(f"{base}/auth/sign-in")
        pg.fill("input[name=email]", env["LANGFUSE_INIT_USER_EMAIL"])
        pg.fill("input[type=password]", env["LANGFUSE_INIT_USER_PASSWORD"])
        pg.click("button[type=submit]")
        pg.wait_for_url(lambda u: "/auth/" not in u, timeout=60_000)
        pg.goto(f"{base}/project/{env['LANGFUSE_INIT_PROJECT_ID']}/traces/{trace_id}")
        pg.wait_for_timeout(8000)
        pg.screenshot(path=str(SHOT), full_page=False)
        b.close()
    print(f"截图：{SHOT.relative_to(ROOT)}")


if __name__ == "__main__":
    {"env": cmd_env, "smoke": cmd_smoke, "screenshot": cmd_screenshot}[sys.argv[1] if len(sys.argv) > 1 else "smoke"]()
