"""`tw run`（W1-33）离线端到端：玩具仓库（parse_rows 空行 IndexError）+ none 后端 + 权限引擎 + 脚本化模型。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from triwitness.harness.config import HarnessConfig
from triwitness.harness.local_run import run_local
from triwitness.harness.testing import FakeRouter, call, say
from triwitness.sandbox.local import LocalSandboxBackend

BUGGY = (
    "def parse_rows(text):\n    rows = []\n    for line in text.splitlines():\n        a, b = line.split(',')\n"
    "        rows.append((a, int(b)))\n    return rows\n"
)
TEST = (
    "from rows import parse_rows\n\n\ndef test_blank():\n"
    "    assert parse_rows('a,1\\n\\nb,2') == [('a', 1), ('b', 2)]\n"
)
OLD = "        a, b = line.split(',')"
NEW = "        if not line.strip():\n            continue\n" + OLD


def git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True,
                          capture_output=True, text=True).stdout  # fmt: skip


@pytest.fixture
def toy(tmp_path: Path) -> Path:
    repo = tmp_path / "toy"
    repo.mkdir()
    (repo / "rows.py").write_bytes(BUGGY.encode())
    (repo / "test_rows.py").write_bytes(TEST.encode())
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    return repo


FIN = {"summary": "跳过空行", "changes": [{"path": "rows.py", "kind": "modified"}], "tests_run": ["pytest"],
       "tests_passed": True, "confidence": 0.9}  # fmt: skip


async def test_tw_run_fixes_toy_repo(toy: Path, tmp_path: Path) -> None:
    script = [
        say(call("read_file", path="rows.py")),
        say(call("edit_file", path="rows.py", old_str=OLD, new_str=NEW)),
        say(call("run_tests")),
        say(call("finish", **FIN)),
    ]
    home = tmp_path / "home"
    out = await run_local(
        toy,
        "parse_rows 遇到空行抛 IndexError",
        router=FakeRouter(script),
        harness=HarnessConfig.load(),  # 脚本按基线 8 工具写；默认 repro-first 另测
        backend="none",
        backends=[LocalSandboxBackend(home=home)],
        home=home,
        test_command=f'"{Path(sys.executable).as_posix()}" -m pytest -q -p no:cacheprovider',
        verify="deterministic",
    )
    assert out.result.status == "done", (out.result.outcome, out.result.outcome.reason)
    ev = json.loads((out.run_dir / "evidence.json").read_text(encoding="utf-8"))
    assert ev["clean_env"] == "unverified" and ev["risk_level"] in ("L2", "L3")  # none 后端：无干净环境
    assert "TriWitness 证据包" in (out.run_dir / "pr.md").read_text(encoding="utf-8")
    assert out.backend == "none" and out.branch and out.branch.startswith("tw/")
    # 用户工作区与当前分支不动；改动在 tw/<run_id> 分支上
    assert (toy / "rows.py").read_text() == BUGGY
    assert git(toy, "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"
    assert git(toy, "status", "--porcelain").strip() == ""
    assert "continue" in git(toy, "show", f"{out.branch}:rows.py")
    assert git(toy, "worktree", "list").count("\n") == 1
    # 产物
    files = {p.name for p in out.run_dir.iterdir()}
    assert {"patch.diff", "cost.md", "finish.json", "summary.json", "trajectory.jsonl"} <= files
    assert "+        if not line.strip():" in (out.run_dir / "patch.diff").read_text()
    assert "合计" in (out.run_dir / "cost.md").read_text(encoding="utf-8")
    assert json.loads((out.run_dir / "summary.json").read_text(encoding="utf-8"))["status"] == "done"
    kinds = [json.loads(x)["kind"] for x in (out.run_dir / "trajectory.jsonl").read_text().splitlines()]
    assert kinds[0] == "task_started" and kinds[-1] == "task_finished"
    assert kinds.count("tool_call") == 4


async def test_tw_run_permission_denies_outside_workspace(toy: Path, tmp_path: Path) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("nope")
    script = [say(call("read_file", path=str(outside))), say(call("finish", **{**FIN, "tests_passed": False}))]
    home = tmp_path / "home"
    out = await run_local(toy, "x", router=FakeRouter(script), harness=HarnessConfig.load(), backend="none",
                          backends=[LocalSandboxBackend(home=home)], home=home)  # fmt: skip
    traj = (out.run_dir / "trajectory.jsonl").read_text(encoding="utf-8")
    assert "nope" not in traj
    assert out.result.status == "failed"
    assert out.branch is None and "tw/" not in git(toy, "branch")
