import httpx
import pytest

from triwitness.core.errors import ConfigError, ConstraintViolation, LLMUnavailable, ModelNotAllowed
from triwitness.core.models import Role
from triwitness.llm import cases
from triwitness.llm.client import LLMClient
from triwitness.llm.deepseek import DeepSeekAdapter
from triwitness.llm.http import HttpTransport
from triwitness.llm.replay import RecordReplayTransport, ReplayStore
from triwitness.llm.router import RoleRoute, Router, VendorPolicy
from triwitness.llm.types import LLMRequest, LLMResponse, Message, Usage

from .helpers import replay_client


class FakeClient:
    """按模型名返回或抛错；记录调用。"""

    def __init__(self, fail: set[str] | None = None, exc: type[Exception] = LLMUnavailable) -> None:
        self.fail = fail or set()
        self.exc = exc
        self.calls: list[tuple[str, LLMRequest]] = []

    async def complete(self, req, model, *, guard=None, category="dev", task_id=None) -> LLMResponse:
        self.calls.append((model, req))
        if model in self.fail:
            raise self.exc(f"{model} down")
        return LLMResponse(
            message=Message(role="assistant", content=model),
            usage=Usage(),
            served_model=model.split("/")[-1],
            finish_reason="stop",
            raw={},
            model=model,
        )


def _req(role: Role = "executor") -> LLMRequest:
    return LLMRequest(role=role, messages=[Message(role="user", content="hi")])


# ---------------------------------------------------------------- 默认配置（单厂商）


def test_default_config_routes() -> None:
    r = Router.from_config({"deepseek": FakeClient()})
    assert r.vendor_policy == "single_vendor"
    ex, rv, sm = r.route_for("executor"), r.route_for("reviewer"), r.route_for("summarizer")
    assert (ex.model, ex.thinking, ex.effort) == ("deepseek/deepseek-flash", True, "high")
    assert (rv.effort, rv.variant) == ("max", "adversarial")
    assert sm.thinking is False
    assert all("v4-pro" not in x.model for x in r.routes.values())


async def test_route_params_applied_and_annotated() -> None:
    fc = FakeClient()
    r = Router.from_config({"deepseek": fc})
    resp = await r.complete(_req("reviewer"))
    sent = fc.calls[0][1]
    assert (sent.thinking, sent.effort) == (True, "max")
    assert (resp.role, resp.variant, resp.vendor_policy) == ("reviewer", "adversarial", "single_vendor")
    # 调用方显式给的 effort 不被覆盖
    await r.complete(_req("executor").model_copy(update={"effort": "low"}))
    assert fc.calls[1][1].effort == "low"


async def test_single_vendor_allows_same_vendor_review() -> None:
    fc = FakeClient()
    r = Router.from_config({"deepseek": fc})
    resp = await r.complete(_req("reviewer"), executor_vendor="deepseek")
    assert resp.model == "deepseek/deepseek-flash"


async def test_router_end_to_end_offline_with_replay() -> None:
    r = Router(
        {"summarizer": RoleRoute(model="deepseek/deepseek-flash", thinking=False)}, {"deepseek": replay_client()}
    )
    req = cases.text_nonthinking().model_copy(update={"role": "summarizer"})
    resp = await r.complete(req)
    assert resp.source == "replay" and resp.role == "summarizer" and resp.cost_cny > 0


def test_unknown_role_and_bad_prefix() -> None:
    r = Router({"executor": RoleRoute(model="deepseek/deepseek-flash")}, {})
    with pytest.raises(ConfigError):
        r.route_for("planner")
    with pytest.raises(ConfigError):
        Router({"executor": RoleRoute(model="deepseek-flash")}, {})
    with pytest.raises(ConfigError):
        Router.from_config({}, {"vendor_policy": "nope", "roles": {}})


# ---------------------------------------------------------------- 回退与 eval 模式


def _fallback_router(fc: FakeClient, policy: VendorPolicy = "single_vendor") -> Router:
    routes: dict[Role, RoleRoute] = {
        "executor": RoleRoute(model="deepseek/deepseek-flash", fallback=["zhipu/glm-5.3", "qwen/qwen3.8-max"]),
        "reviewer": RoleRoute(model="zhipu/glm-5.3", fallback=["deepseek/deepseek-flash", "qwen/qwen3.8-max"]),
        "verifier": RoleRoute(model="deepseek/deepseek-flash", fallback=["deepseek/deepseek-v4.1-flash"]),
    }
    return Router(routes, {"deepseek": fc, "zhipu": fc, "qwen": fc}, vendor_policy=policy)


async def test_background_falls_back_and_marks_degraded() -> None:
    fc = FakeClient(fail={"deepseek/deepseek-flash"})
    resp = await _fallback_router(fc).complete(_req())
    assert resp.model == "zhipu/glm-5.3" and resp.fallback_from == "deepseek/deepseek-flash"
    assert "fallback:deepseek/deepseek-flash->zhipu/glm-5.3" in resp.degraded


async def test_eval_mode_never_falls_back() -> None:
    fc = FakeClient(fail={"deepseek/deepseek-flash"})
    with pytest.raises(LLMUnavailable):
        await _fallback_router(fc).complete(_req(), mode="eval")
    assert [m for m, _ in fc.calls] == ["deepseek/deepseek-flash"]


async def test_all_fail_raises() -> None:
    fc = FakeClient(fail={"deepseek/deepseek-flash", "zhipu/glm-5.3", "qwen/qwen3.8-max"})
    with pytest.raises(LLMUnavailable, match="回退链全部失败"):
        await _fallback_router(fc).complete(_req())


async def test_non_availability_errors_do_not_fall_back() -> None:
    fc = FakeClient(fail={"deepseek/deepseek-flash"}, exc=ModelNotAllowed)
    with pytest.raises(ModelNotAllowed):
        await _fallback_router(fc).complete(_req())
    assert len(fc.calls) == 1


async def test_ac7_eval_mode_429_retries_then_raises_without_fallback(tmp_path) -> None:
    hits = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        hits["n"] += 1
        assert "authorization" in {k.lower() for k in request.headers}
        return httpx.Response(429, json={"error": "rate limited"})

    async def no_sleep(_: float) -> None:
        return None

    http = HttpTransport(
        "https://api.deepseek.com",
        "TW_TEST_KEY",
        sleep=no_sleep,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    rr = RecordReplayTransport(ReplayStore("deepseek", [tmp_path]), http, mode="live")
    import os

    os.environ["TW_TEST_KEY"] = "tw-placeholder-test"
    try:
        from .helpers import SAT_OFFPEAK

        ds = LLMClient(DeepSeekAdapter(), rr, now=lambda: SAT_OFFPEAK)
        backup = FakeClient()
        r = Router(
            {"executor": RoleRoute(model="deepseek/deepseek-flash", fallback=["zhipu/glm-5.3"])},
            {"deepseek": ds, "zhipu": backup},
        )
        with pytest.raises(LLMUnavailable):
            await r.complete(_req(), mode="eval")
        assert hits["n"] == 3  # 首次 + 退避重试 2 次
        assert backup.calls == []
    finally:
        del os.environ["TW_TEST_KEY"]


# ---------------------------------------------------------------- cross_vendor（资金到位后启用；现在用 FakeClient 测）


async def test_cross_vendor_reviewer_skips_executor_vendor() -> None:
    fc = FakeClient()
    r = _fallback_router(fc, "cross_vendor")
    resp = await r.complete(_req("reviewer"), executor_vendor="zhipu")
    assert resp.model == "deepseek/deepseek-flash" and resp.vendor_policy == "cross_vendor"


async def test_cross_vendor_unsatisfiable_raises() -> None:
    r = _fallback_router(FakeClient(), "cross_vendor")
    with pytest.raises(ConstraintViolation):
        await r.complete(_req("verifier"), executor_vendor="deepseek")


async def test_cross_vendor_does_not_constrain_executor() -> None:
    fc = FakeClient()
    resp = await _fallback_router(fc, "cross_vendor").complete(_req("executor"), executor_vendor="deepseek")
    assert resp.model == "deepseek/deepseek-flash"


def test_deepseek_default_factory_is_offline() -> None:
    r = Router.deepseek_default()
    client = r.clients["deepseek"]
    assert isinstance(client, LLMClient) and client.transport.inner is None


async def test_runconfig_executor_override_nonthinking() -> None:
    """W2-25：RunConfig.executor 之前被忽略（dev 非思考对照会悄悄跑成思考 high）。"""
    fake = FakeClient()
    router = Router.from_config({"deepseek": fake})
    router.override_executor({"model": "deepseek-flash", "thinking": False})
    await router.complete(_req("executor"), mode="eval")
    req = fake.calls[-1][1]
    assert req.thinking is False and req.effort is None
    assert router.route_for("reviewer").thinking is True  # 其他角色不受影响


def test_runconfig_executor_override_rejects_pro_and_unknown() -> None:
    router = Router.from_config({"deepseek": FakeClient()})
    with pytest.raises(ConfigError):
        router.override_executor({"model": "deepseek-v4-pro"})
    with pytest.raises(ConfigError):
        router.override_executor({"temperature": 0.2})


def test_deepseek_default_applies_runconfig_executor() -> None:
    """CLI `tw eval run` 把 RunConfig.executor 传给 deepseek_default（configs/runs/baseline-deepseek-nothink.yaml）。"""
    r = Router.deepseek_default(executor={"model": "deepseek-flash", "thinking": False})
    route = r.route_for("executor")
    assert route.thinking is False and route.effort is None
    assert Router.deepseek_default().route_for("executor").thinking is True
