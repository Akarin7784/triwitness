"""全局测试约束：单测永远走回放，不真调模型。"""

import os

import pytest


@pytest.fixture(autouse=True)
def _force_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TW_LLM_MODE", "replay")
    # 单测进程里不应该看到真实密钥
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert os.environ.get("TW_LLM_MODE") == "replay"
