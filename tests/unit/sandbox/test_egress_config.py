"""spec 014 §3（W7-03）：allowlist 网络的纯函数部分（不需要 Docker）。"""

from __future__ import annotations

import pytest

from triwitness.core.errors import SandboxError
from triwitness.gateway.egress_proxy import is_forbidden_ip
from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.docker import container_kwargs
from triwitness.sandbox.egress import (
    PROXY_URL,
    check_placeholders,
    expand_allowlist,
    gateway_config,
    gateway_secrets,
    load_profiles,
    proxy_env,
    sandbox_network_kwargs,
)

RULE = {"name": "gh", "host": "api.github.com", "placeholder": "tw-placeholder-gh", "secret_env": "GH_TOKEN",
        "upstream": "https://uploads.github.com/x"}  # fmt: skip


def test_profiles_and_expand() -> None:
    prof = load_profiles()
    assert "pypi.org" in prof["pypi"]
    assert expand_allowlist(["profile:pypi", "pypi.org", "x.org"]) == [*prof["pypi"], "x.org"]
    with pytest.raises(SandboxError):
        expand_allowlist(["profile:nope"])


def test_gateway_config_adds_binding_hosts_and_secrets_stay_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TW_EGRESS_TREAT_AS_PUBLIC", "198.18.0.0/15")
    spec = SandboxSpec(network="allowlist", allowlist=["profile:pypi"], credentials=[RULE],
                       env={"GITHUB_TOKEN": "tw-placeholder-gh"})  # fmt: skip
    cfg = gateway_config(spec)
    assert {"api.github.com", "uploads.github.com", "pypi.org"} <= set(cfg["allow"])
    assert cfg["treat_as_public"] == ["198.18.0.0/15"]
    assert gateway_secrets(spec, {"GH_TOKEN": "real", "OTHER_TOKEN": "x"}) == {"GH_TOKEN": "real"}
    assert "real" not in str(cfg)
    check_placeholders(spec)
    with pytest.raises(SandboxError):
        check_placeholders(spec.model_copy(update={"env": {"X_TOKEN": "tw-placeholder-unknown"}}))


def test_sandbox_kwargs_force_gateway() -> None:
    kw = container_kwargs(SandboxSpec(network="allowlist", allowlist=["pypi.org"], block_code_hosts=True))
    kw.update(sandbox_network_kwargs("tw-net-abc"))
    assert kw["network_mode"] == "tw-net-abc" and kw["dns"] == ["127.0.0.1"]
    assert kw["environment"]["HTTPS_PROXY"] == PROXY_URL and proxy_env()["NO_PROXY"] == ""


def test_fake_ip_ranges_never_cover_metadata() -> None:
    assert is_forbidden_ip("198.18.0.1") and not is_forbidden_ip("198.18.0.1", ["198.18.0.0/15"])
    assert is_forbidden_ip("169.254.169.254", ["0.0.0.0/0"]) and is_forbidden_ip("127.0.0.1", ["0.0.0.0/0"])
