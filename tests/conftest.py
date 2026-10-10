"""全局测试约束：单测永远走回放，不真调模型。"""

import os

import pytest


@pytest.fixture(autouse=True)
def _force_replay(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    monkeypatch.setenv("TW_LLM_MODE", "replay")
    # 账本、llm 缓存都写到临时目录，绝不碰真实 ~/.triwitness
    monkeypatch.setenv("TW_HOME", str(tmp_path_factory.mktemp("tw_home")))
    monkeypatch.delenv("TW_KILL_SWITCH", raising=False)
    # 单测进程里不应该看到真实密钥
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert os.environ.get("TW_LLM_MODE") == "replay"
