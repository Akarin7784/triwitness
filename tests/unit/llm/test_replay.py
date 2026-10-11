import json
import re

import pytest

from triwitness.core.errors import TriWitnessError
from triwitness.llm import cases
from triwitness.llm.client import LLMClient
from triwitness.llm.replay import ReplayMiss, ReplayStore, current_mode, request_key, scrub

from .helpers import FIXTURES, CannedTransport, ExplodingTransport, client_with, replay_client


async def test_all_recorded_cases_replay_offline() -> None:
    ExplodingTransport.calls = 0
    c = replay_client()
    seen = []
    for req in (cases.text_nonthinking(), cases.tool_single_nonthinking()):
        seen.append(await c.complete(req, cases.MODEL))
    first = await c.complete(cases.tool_multiturn_thinking_1(), cases.MODEL)
    second = await c.complete(cases.tool_multiturn_thinking_2(first), cases.MODEL)
    warm1 = await c.complete(cases.cache_prefix(cases.CACHE_Q1), cases.MODEL)
    warm2 = await c.complete(cases.cache_prefix(cases.CACHE_Q2), cases.MODEL)
    assert ExplodingTransport.calls == 0
    assert all(r.source == "replay" for r in [*seen, first, second, warm1, warm2])
    assert seen[0].message.content and "2" in seen[0].message.content
    assert seen[1].message.tool_calls and seen[1].message.tool_calls[0].name == "get_weather"
    assert second.message.content and not second.message.tool_calls
    # 稳定前缀：第二次请求命中缓存（实测 3328/3523）
    assert warm1.usage.cache_hit_tokens == 0
    assert warm2.usage.cache_hit_rate > 0.9
    assert warm2.cost_cny < warm1.cost_cny / 5


async def test_replay_miss_never_hits_network() -> None:
    ExplodingTransport.calls = 0
    c = replay_client()
    req = cases.text_nonthinking().model_copy(update={"max_output_tokens": 17})
    with pytest.raises(ReplayMiss):
        await c.complete(req, cases.MODEL)
    assert ExplodingTransport.calls == 0


def test_default_mode_is_replay() -> None:
    assert current_mode() == "replay"


def test_deepseek_factory_in_replay_has_no_http() -> None:
    c = LLMClient.deepseek()
    assert c.transport.inner is None and c.ledger is None


def test_key_is_canonical_and_order_independent() -> None:
    assert request_key("deepseek", {"a": 1, "b": [1, 2]}) == request_key("deepseek", {"b": [1, 2], "a": 1})
    assert request_key("deepseek", {"a": 1}) != request_key("deepseek", {"a": 2})


def test_fixtures_have_no_secrets_and_valid_keys() -> None:
    files = sorted(FIXTURES.glob("*.json"))
    assert len(files) >= 4
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert not re.search(r"sk-[A-Za-z0-9]{16,}|Bearer\s|authorization", text, re.I), p.name
        data = json.loads(text)
        assert data["key"] == request_key("deepseek", data["request"]), p.name
        assert data["request"]["model"] == "deepseek-flash"


def test_scrub_removes_auth() -> None:
    out = scrub({"headers": {"Authorization": "Bearer x"}, "msg": "key sk-abcdefghijklmnopqrstu", "n": 1})
    assert out == {"msg": "key [REDACTED]", "n": 1}


def test_put_refuses_secret(tmp_path) -> None:
    store = ReplayStore("deepseek", [tmp_path], write_dir=tmp_path)
    # scrub 会先清掉，直接构造绕过 scrub 的情形：键名不在黑名单但值像密钥
    p = store.put("k", {"x": "sk-abcdefghijklmnopqrstuvwxyz"}, {"ok": True})
    assert "[REDACTED]" in p.read_text(encoding="utf-8")
    with pytest.raises(TriWitnessError):
        ReplayStore("deepseek", [], write_dir=None).put("k", {}, {})


async def test_record_mode_writes_then_reuses(tmp_path) -> None:
    raw = json.loads((FIXTURES / "text_nonthinking.json").read_text(encoding="utf-8"))["response"]
    inner = CannedTransport(raw)
    c, rr = client_with(inner, "record", tmp_path)
    r1 = await c.complete(cases.text_nonthinking(), cases.MODEL)
    r2 = await c.complete(cases.text_nonthinking(), cases.MODEL)
    assert (r1.source, r2.source, inner.calls, rr.network_calls) == ("live", "replay", 1, 1)
    assert len(list((tmp_path / "cache").glob("*.json"))) == 1


async def test_live_mode_bypasses_cache_but_records(tmp_path) -> None:
    raw = json.loads((FIXTURES / "text_nonthinking.json").read_text(encoding="utf-8"))["response"]
    inner = CannedTransport(raw)
    c, _ = client_with(inner, "live", tmp_path)
    await c.complete(cases.text_nonthinking(), cases.MODEL)
    await c.complete(cases.text_nonthinking(), cases.MODEL)
    assert inner.calls == 2  # 不读缓存：重复尝试各自真采样
    assert len(list((tmp_path / "cache").glob("*.json"))) == 1  # 但会录下来，之后可离线回放


async def test_record_mode_cache_hit_costs_nothing(tmp_path) -> None:
    """0.3.2：本地缓存命中没联网也没计费 → 实付 0（和账本一致），名义价照算。"""
    from triwitness.cost.ledger import GlobalLedger

    raw = json.loads((FIXTURES / "text_nonthinking.json").read_text(encoding="utf-8"))["response"]
    c, _ = client_with(CannedTransport(raw), "record", tmp_path)
    c.ledger = GlobalLedger(tmp_path / "ledger.sqlite")
    r1 = await c.complete(cases.text_nonthinking(), cases.MODEL, category="reviewer")
    r2 = await c.complete(cases.text_nonthinking(), cases.MODEL, category="reviewer")
    assert r1.cost_cny > 0 and not r1.cached
    assert r2.cached and r2.cost_cny == 0.0 and r2.nominal_cost_cny == r1.cost_cny
    assert c.ledger.spent() == r1.cost_cny + r2.cost_cny
    assert c.ledger.spent("reviewer") == r1.cost_cny


async def test_replay_mode_keeps_nominal_cost() -> None:
    """replay（测试 / 离线评测）沿用名义价，成本报告可比。"""
    r = await replay_client().complete(cases.text_nonthinking(), cases.MODEL)
    assert r.cached and r.cost_cny == r.nominal_cost_cny > 0
