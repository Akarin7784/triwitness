"""0.3.2 断点续跑：每步存进度 → 停下 → 新 run 从进度继续（FakeRouter / FakeSandbox，¥0）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from triwitness.core.errors import ConfigError
from triwitness.core.models import Budget
from triwitness.harness.config import HarnessConfig
from triwitness.harness.resume import load_resume, resumable, resume_note, run_status
from triwitness.harness.run import TaskResult, run_task
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.sandbox.base import ExecResult
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools

CFG = HarnessConfig.load("harness/repro-first.yaml")
REPRO = "tests/tw_repro/test_issue_3.py"
BUGGY, FIXED = "def add(a, b):\n    return a - b\n", "def add(a, b):\n    return a + b\n"
RUN_ID = "r_01RESUMETEST0000000000000A"
WRITE_REPRO = call(
    "write_file", path=REPRO, content="from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
)
SUBMIT = call("submit_repro", path=REPRO, cmd=f"pytest {REPRO}")
FIX = call("edit_file", path="calc.py", old_str="a - b", new_str="a + b")
FINISH = call("finish", summary="修好 add", changes=[{"path": "calc.py", "kind": "modified"}], tests_run=["pytest"],
              tests_passed=True, confidence=0.9)  # fmt: skip


def handler(cmd: str, sb: FakeSandbox) -> ExecResult:
    code = 0 if sb.files.get("calc.py") == FIXED.encode() else 1
    return ExecResult(exit_code=code, stdout="1 failed" if code else "1 passed", stderr="", duration_ms=1,
                      timed_out=False)  # fmt: skip


Out = tuple[TaskResult, TrajectoryRecorder, FakeSandbox]


async def run(script: list, home: Path, run_id: str, *, files: dict[str, str | bytes] | None = None,  # type: ignore[type-arg]
              resume: Any = None, budget: Budget | None = None) -> Out:  # fmt: skip
    run_dir = home / "runs" / run_id
    rec = TrajectoryRecorder("t_r", run_id, run_dir=run_dir)
    sb = FakeSandbox(files or {"calc.py": BUGGY}, exec_handler=handler)
    res = await run_task(recorder=rec, router=FakeRouter(script), registry=ToolRegistry(default_tools(names=CFG.tools)),
                         sandbox=sb, issue_title="add 是减法", task_prompt="add 是减法，修一下", repo="o/r",
                         budget=budget or Budget(), config_hash="c", issue_number=3, test_command="pytest -q",
                         config=CFG, resume=resume, progress_dir=run_dir)  # fmt: skip
    return res, rec, sb


def stop(run_dir: Path, status: str = "cancelled") -> None:
    """模拟 local_run 收尾（或进程被杀：不写 summary.json）。"""
    if status != "interrupted":
        (run_dir / "summary.json").write_text(json.dumps({"status": status}), encoding="utf-8")


async def test_progress_saved_each_step_then_resume_finishes(tmp_path: Path) -> None:
    # 第一次：复现被接受、源码已改，然后脚本用完（模型不再给工具调用 → stuck）
    idle = [say(text="想一想"), say(text="再想想"), say(text="…")]
    res, _, _ = await run([say(WRITE_REPRO), say(SUBMIT), say(FIX), *idle], tmp_path, RUN_ID)
    assert res.status != "done"
    run_dir = tmp_path / "runs" / RUN_ID
    doc = json.loads((run_dir / "resume" / "resume.json").read_text(encoding="utf-8"))
    assert {f["path"] for f in doc["files"]} == {"calc.py", REPRO}
    assert doc["repro_check"]["status"] == "reproduced" and doc["issue"].startswith("add 是减法")
    stop(run_dir, "interrupted")
    assert run_status(run_dir) == "interrupted" and resumable(run_dir)

    state = load_resume(tmp_path, RUN_ID)
    assert state.files["calc.py"] == FIXED.encode()
    res2, rec2, _ = await run([say(call("run_tests")), say(FINISH)], tmp_path, "r_01RESUMETEST0000000000000B",
                                resume=state)  # fmt: skip
    assert res2.status == "done" and res2.repro_status == "reproduced"
    states = [e.payload["to"] for e in rec2.events if e.kind == "state_change"]
    assert "reproducing" not in states  # 复现沿用，不重来
    labels = [e.payload["label"] for e in rec2.events if e.kind == "checkpoint"]
    assert labels[:2] == ["start", "resumed"]
    assert "calc.py" in res2.diff and REPRO in res2.diff  # diff 以原始代码为基线
    first_user = next(e for e in rec2.events if e.kind == "task_started")
    assert first_user is not None


async def test_resume_without_accepted_repro_holds_source(tmp_path: Path) -> None:
    """没提交复现就改了源码：续跑时只恢复测试侧文件（否则 submit_repro 会拒绝）。"""
    await run([say(WRITE_REPRO), say(FIX), say(text="…"), say(text="…"), say(text="…")], tmp_path, RUN_ID)
    stop(tmp_path / "runs" / RUN_ID, "stuck")
    state = load_resume(tmp_path, RUN_ID)
    assert state.repro_check is None
    _, _, sb = await run([say(SUBMIT), say(FIX), say(call("run_tests")), say(FINISH)], tmp_path,
                         "r_01RESUMETEST0000000000000C", resume=state)  # fmt: skip
    assert sb.files["calc.py"] == FIXED.encode()  # 模型按提示重新改了
    note = resume_note(state, [REPRO], ["calc.py"])
    assert "暂未恢复" in note and "calc.py" in note


def test_load_resume_refuses(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_resume(tmp_path, "../etc")
    run_dir = tmp_path / "runs" / RUN_ID
    run_dir.mkdir(parents=True)
    with pytest.raises(ConfigError, match="没有可续跑的进度"):
        load_resume(tmp_path, RUN_ID)
    stop(run_dir, "done")
    with pytest.raises(ConfigError, match="不需要续跑"):
        load_resume(tmp_path, RUN_ID)
    (run_dir / "summary.json").unlink()
    (run_dir / "owner.pid").write_text(str(os.getpid()))
    assert run_status(run_dir) == "running"
    with pytest.raises(ConfigError, match="还在运行"):
        load_resume(tmp_path, RUN_ID)


def test_load_resume_ignores_paths_outside_repo(tmp_path: Path) -> None:
    root = tmp_path / "runs" / RUN_ID / "resume"
    (root / "files").mkdir(parents=True)
    (root / "files" / "0").write_bytes(b"x")
    (root / "resume.json").write_text(
        json.dumps(
            {
                "format": "tw-resume/1",
                "issue": "i",
                "files": [
                    {"path": "../evil", "blob": "0"},
                    {"path": "/etc/passwd", "blob": "0"},
                    {"path": "ok.py", "blob": "0"},
                ],
            }
        )
    )
    assert list(load_resume(tmp_path, RUN_ID).files) == ["ok.py"]
