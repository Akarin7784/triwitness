"""spec 011 §4（W4-09）：对外副作用的幂等键——先查后做，做过的不再做。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from triwitness.store.idempotency import SideEffectLog, side_effect_key


def test_key_format() -> None:
    assert side_effect_key("t_1", "open_pr") == "t_1:open_pr:0"
    assert side_effect_key("t_1", "comment", 3) == "t_1:comment:3"
    with pytest.raises(ValueError):
        side_effect_key("t_1", "a:b")


def test_done_is_not_repeated_across_reopen(tmp_path: Path) -> None:
    calls: list[int] = []

    def do() -> dict[str, Any]:
        calls.append(1)
        return {"url": "https://x/pull/1"}

    with SideEffectLog(tmp_path / "tw.db") as log:
        a = log.run("r:open_pr:0", do)
    with SideEffectLog(tmp_path / "tw.db") as log:  # 进程重启后
        b = log.run("r:open_pr:0", do)
        rec = log.get("r:open_pr:0")
    assert (a.how, b.how, b.reused) == ("executed", "recorded", True)
    assert b.result == {"url": "https://x/pull/1"} and len(calls) == 1
    assert rec is not None and rec.status == "done" and rec.attempts == 1


def test_half_done_checks_outside_world_first(tmp_path: Path) -> None:
    """上次记了 started 但进程没了：先 find()，外部已存在就补记 done，不重复执行。"""
    with SideEffectLog(tmp_path / "tw.db") as log:
        log._set("r:open_pr:0", "open_pr", "started", attempt=True)
        out = log.run("r:open_pr:0", lambda: pytest.fail("不应重复执行"), find=lambda: {"url": "u"})  # type: ignore[arg-type,return-value]
        assert (out.how, out.result) == ("found", {"url": "u"})
        assert log.get("r:open_pr:0").status == "done"  # type: ignore[union-attr]


def test_failure_is_recorded_redacted_and_retried(tmp_path: Path) -> None:
    n = {"i": 0}

    def flaky() -> dict[str, Any]:
        n["i"] += 1
        if n["i"] == 1:
            raise RuntimeError("HTTP 502 token=sk-abcdefghijklmnopqrstuvwxyz123456")
        return {"ok": True}

    with SideEffectLog(tmp_path / "tw.db") as log:
        with pytest.raises(RuntimeError):
            log.run("r:push:0", flaky)
        rec = log.get("r:push:0")
        assert rec is not None and rec.status == "failed" and "sk-abcdefghijklmnop" not in (rec.error or "")
        out = log.run("r:push:0", flaky, find=lambda: None)
        assert out.how == "executed" and log.get("r:push:0").attempts == 2  # type: ignore[union-attr]


def test_cli_pr_open_twice_opens_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    import triwitness.github.pr as pr
    from triwitness.cli.main import app

    run = "r_01M4P00000000000000000PR001"
    monkeypatch.setenv("TW_HOME", str(tmp_path / "home"))
    (tmp_path / "home" / "runs" / run).mkdir(parents=True)
    opened: list[str] = []

    class Plan:
        full_name, head, base, title, existing_url = "o/r", f"tw/{run}", "main", "t", None

    def fake_open(plan: Any, **_: Any) -> Any:
        opened.append(plan.head)
        return pr.PrResult("https://github.com/o/r/pull/7", 7, created=True, pushed=True)

    monkeypatch.setattr(pr, "plan_pr", lambda *a, **k: Plan())
    monkeypatch.setattr(pr, "open_pr", fake_open)
    monkeypatch.setattr(pr, "record_pr", lambda *a, **k: None)
    outs = []
    for _ in range(2):
        r = CliRunner().invoke(app, ["pr", "open", "--run", run, "--repo", str(tmp_path), "--yes"])
        assert r.exit_code == 0, r.output
        outs.append(json.loads(r.output.strip().splitlines()[-1]))
    assert opened == [f"tw/{run}"]
    assert outs[0]["created"] is True and outs[0]["reused"] is False
    assert (
        outs[1]["reused"] is True and outs[1]["url"] == "https://github.com/o/r/pull/7" and outs[1]["created"] is False
    )
