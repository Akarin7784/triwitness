import pytest

from triwitness.core.errors import ModelNotAllowed
from triwitness.llm.adapter import ModelAdapter, ModelPolicy, split_model_id
from triwitness.llm.deepseek import DeepSeekAdapter
from triwitness.llm.fake import FakeAdapter
from triwitness.llm.types import LLMRequest, Message, ToolCallSpec


def test_fake_adapter_satisfies_protocol() -> None:
    fake = FakeAdapter([Message(role="assistant", content="hi")])
    adapter: ModelAdapter = fake
    payload = adapter.build_request(
        "deepseek-flash", LLMRequest(role="executor", messages=[Message(role="user", content="x")])
    )
    resp = adapter.parse_response(fake.next_raw(payload))
    assert resp.message.content == "hi" and resp.usage.cache_hit_rate == pytest.approx(0.9)
    assert fake.requests and fake.requests[0]["model"] == "deepseek-flash"


def test_deepseek_adapter_satisfies_protocol() -> None:
    adapter: ModelAdapter = DeepSeekAdapter()
    assert adapter.capabilities("deepseek-flash").reasoning_passback_with_tools


def test_vendor_enum_keeps_future_vendors() -> None:
    from typing import get_args

    from triwitness.core.models import Vendor

    assert set(get_args(Vendor)) == {"deepseek", "qwen", "zhipu"}


def test_split_model_id() -> None:
    assert split_model_id("deepseek/deepseek-flash") == ("deepseek", "deepseek-flash")
    assert split_model_id("deepseek-flash") == (None, "deepseek-flash")


@pytest.mark.parametrize("model", ["deepseek-v4-pro", "deepseek/deepseek-v4-pro", "deepseek-v4-pro-0813"])
def test_v4_pro_always_rejected(model: str) -> None:
    with pytest.raises(ModelNotAllowed):
        ModelPolicy.from_config().check(model)
    # 即使配置误把它放进白名单也拒绝
    with pytest.raises(ModelNotAllowed):
        ModelPolicy(["deepseek-v4-pro", "deepseek-v4-pro-0813"]).check(model)


def test_whitelist() -> None:
    p = ModelPolicy.from_config()
    assert p.check("deepseek/deepseek-flash") == "deepseek-flash"
    assert p.check("deepseek-v4.1-flash") == "deepseek-v4.1-flash"
    with pytest.raises(ModelNotAllowed):
        p.check("qwen3.8-max")


def test_tool_call_arguments_kept_verbatim() -> None:
    c = ToolCallSpec(id="1", name="f", arguments='{"b": 1, "a": 2}')
    assert c.arguments == '{"b": 1, "a": 2}'
