"""外部任务的时间预算 → 步数 / 墙钟上限（W5-13 第三轮；不依赖 harbor，Windows 上也跑）。"""

from __future__ import annotations

import json
from pathlib import Path

from triwitness.integrations.harbor_sandbox import external_limits, external_task_prompt, task_time_budget


def _trial(tmp_path: Path, agent: dict | None = None, toml: str = "[agent]\ntimeout_sec = 750.0\n", **top) -> Path:  # type: ignore[no-untyped-def]
    task = tmp_path / "overfull-hbox"
    task.mkdir()
    (task / "task.toml").write_text(toml, encoding="utf-8")
    trial = tmp_path / "jobs" / "rep0" / "overfull-hbox__x"
    (trial / "agent").mkdir(parents=True)
    cfg = {"task": {"path": str(task)}, "agent": {"name": "tw", "kwargs": {}, **(agent or {})}, **top}
    (trial / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return trial


def test_reads_task_timeout_from_trial_dir(tmp_path: Path) -> None:
    assert task_time_budget(_trial(tmp_path)) == 750.0


def test_override_multiplier_and_cap(tmp_path: Path) -> None:
    t = _trial(tmp_path, agent={"override_timeout_sec": 1000, "max_timeout_sec": 1500}, timeout_multiplier=2)
    assert task_time_budget(t) == 1500.0


def test_missing_or_broken_returns_none(tmp_path: Path) -> None:
    assert task_time_budget(tmp_path / "nope") is None
    assert task_time_budget(_trial(tmp_path, toml="[verifier]\ntimeout_sec = 1\n")) is None


def test_limits_from_time_budget() -> None:
    assert external_limits(None) == (100, None)  # 读不到预算：原默认 100 步、墙钟不变
    assert external_limits(750) == (150, 675)  # overfull-hbox
    assert external_limits(900) == (180, 810)  # TB2 大多数题
    assert external_limits(1200) == (200, 1080)  # 夹在 200 步
    assert external_limits(300) == (100, 240)  # 短题：步数不低于 100，墙钟留 60 秒


def test_prompt_mentions_time_limit_and_build_artifacts() -> None:
    out = external_task_prompt("Write /app/polyglot/main.py.c", time_budget_s=900)
    assert "限时约 900 秒" in out and "放后台" in out and "可执行文件" in out
    assert "限时" not in external_task_prompt("x")
    assert external_task_prompt("x", "", None) == "x"


def _agent_cls(monkeypatch):  # type: ignore[no-untyped-def]
    """harbor 不是依赖：塞一个最小的 BaseAgent 桩再导入 harbor_agent。"""
    import importlib
    import sys
    import types

    class BaseAgent:
        def __init__(self, logs_dir: Path, **kwargs: object) -> None:
            self.logs_dir = logs_dir

    base = types.ModuleType("harbor.agents.base")
    base.BaseAgent = BaseAgent  # type: ignore[attr-defined]
    for name, mod in (("harbor", types.ModuleType("harbor")), ("harbor.agents", types.ModuleType("harbor.agents")),
                      ("harbor.agents.base", base)):  # fmt: skip
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.delitem(sys.modules, "triwitness.integrations.harbor_agent", raising=False)
    return importlib.import_module("triwitness.integrations.harbor_agent").TriWitnessAgent


def test_agent_budget_and_guard_from_kwargs(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    cls = _agent_cls(monkeypatch)
    trial = _trial(tmp_path)
    a = cls(logs_dir=trial / "agent")
    budget, secs = a.resolve_budget()
    assert secs == 750.0 and (budget.max_turns, budget.max_wall_seconds) == (150, 675)
    cfg = a.harness_config()
    assert cfg.timeout_guard.enabled and cfg.timeout_guard.action == "block"
    b = cls(logs_dir=trial / "agent", time_budget="none", max_turns="120", timeout_guard="off")
    budget, secs = b.resolve_budget()
    assert secs is None and budget.max_turns == 120 and budget.max_wall_seconds == 1800  # 墙钟保持原默认
    assert b.harness_config().timeout_guard.enabled is False
    c = cls(logs_dir=trial / "agent", time_budget="600", timeout_guard="warn")
    assert c.resolve_budget()[0].max_wall_seconds == 540 and c.harness_config().timeout_guard.action == "warn"
