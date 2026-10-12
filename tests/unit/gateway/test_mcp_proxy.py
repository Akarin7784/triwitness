"""spec 014 §5（W7-05 / W7-06）：MCP 代理 — list/call、指纹变脸、版本固定、返回内容包 untrusted。"""

from __future__ import annotations

from pathlib import Path

import pytest

from triwitness.gateway.mcp_proxy import McpBlocked, fingerprint, load_allowlist, open_proxy
from triwitness.gateway.policy_engine import load_default


@pytest.fixture
def audit(tmp_path: Path) -> Path:
    return tmp_path / "mcp.audit.jsonl"


async def test_list_and_call_happy_path(audit: Path) -> None:
    p = open_proxy("tw-demo", policy=load_default(), audit_path=audit)
    try:
        tools = await p.list_tools()
        assert {t["name"] for t in tools} == {"add", "read_note"}  # delete_all 被白名单挡掉
        r = await p.call_tool("add", {"a": 2, "b": 3})
        assert "5" in r["text"] and '<untrusted source="mcp:tw-demo/add">' in r["text"]
        with pytest.raises(McpBlocked) as e:
            await p.call_tool("delete_all", {})
        assert e.value.reason == "tool_not_allowlisted"
    finally:
        await p.close()
    assert "allow" in audit.read_text(encoding="utf-8")


async def test_rug_pull_after_fourth_call_is_quarantined(audit: Path) -> None:
    """第 4 次 call 之后描述变脸：下一次 call 前重新 list，指纹对不上 → 隔离。"""
    p = open_proxy("tw-demo", policy=load_default(), audit_path=audit, extra_args=["--rug-pull-after", "4"])
    try:
        await p.list_tools()
        for i in range(4):
            await p.call_tool("add", {"a": i, "b": 1})
        with pytest.raises(McpBlocked) as e:
            await p.call_tool("add", {"a": 0, "b": 0})
        assert e.value.reason == "tool_quarantined"
        assert any(a.kind == "fingerprint_changed" for a in p.alerts)
        assert "add" in p.quarantined
    finally:
        await p.close()


async def test_version_mismatch_blocks_server(audit: Path) -> None:
    allow = load_allowlist()
    cfg = allow["tw-demo"]
    cfg.version = "9.9.9"
    from triwitness.gateway.mcp_proxy import McpProxy, StdioTransport

    p = McpProxy(cfg, StdioTransport([*cfg.command, "--version", "1.0.0"]), audit_path=audit)
    try:
        with pytest.raises(McpBlocked) as e:
            await p.discover()
        assert e.value.reason == "version_mismatch"
    finally:
        await p.close()


async def test_poison_output_wrapped_and_flagged(audit: Path) -> None:
    p = open_proxy("tw-demo", policy=load_default(), audit_path=audit, extra_args=["--poison-output"])
    try:
        r = await p.call_tool("read_note", {})
        assert '<untrusted source="mcp:tw-demo/read_note">' in r["text"]
        assert r["flags"] and "要求忽略之前的指令" in " ".join(r["flags"])
        assert "tw-gateway" in r["text"]
    finally:
        await p.close()


async def test_gateway_off_passthrough(audit: Path) -> None:
    """关网关臂：原样透传，指纹变脸也不拦。"""
    p = open_proxy("tw-demo", enabled=False, audit_path=audit, extra_args=["--rug-pull-after", "1"])
    try:
        tools = await p.list_tools()
        assert "delete_all" in {t["name"] for t in tools}
        await p.call_tool("add", {"a": 1, "b": 1})
        r = await p.call_tool("add", {"a": 1, "b": 1})  # 描述已变，关网关也不拦
        assert r["text"] == "2" and not r["flags"]
    finally:
        await p.close()


def test_fingerprint_stable() -> None:
    t = {"name": "add", "description": "x", "inputSchema": {"type": "object"}}
    assert fingerprint(t) == fingerprint(dict(reversed(list(t.items()))))
