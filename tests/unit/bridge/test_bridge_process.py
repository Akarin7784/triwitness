"""脚本化端到端（UI-10）：真实子进程 `python -m triwitness run --demo --jsonl`，按桌面端的方式读写管道。¥0。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("extra", [[], ["--max-cost", "0.5", "--permission-mode", "ask", "--backend", "none"]])
def test_subprocess_bridge_round_trip(tmp_path: Path, extra: list[str]) -> None:
    home = tmp_path / "home"
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "TW_DEMO_DELAY_S": "0",
           "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}  # fmt: skip
    env.pop("TW_HOME", None)
    p = subprocess.Popen(
        [sys.executable, "-m", "triwitness", "run", "--repo", str(tmp_path / "verses"), "--demo", "--jsonl", *extra],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True,
        encoding="utf-8",
    )  # fmt: skip
    assert p.stdin is not None and p.stdout is not None
    seen: list[dict] = []  # type: ignore[type-arg]
    for raw in p.stdout:
        obj = json.loads(raw)
        seen.append(obj)
        if obj.get("kind") == "approval_requested":
            rid = obj["payload"]["request_id"]
            p.stdin.write(json.dumps({"cmd": "approve", "request_id": rid, "decision": "allow", "scope": "session"}))
            p.stdin.write("\n")
            p.stdin.flush()
        if obj.get("bridge") in ("result", "error"):
            break
    p.stdin.close()
    assert p.wait(timeout=60) == 0, p.stderr.read() if p.stderr else ""
    res = seen[-1]
    assert res["bridge"] == "result" and res["status"] == "done" and res["verdict"] == "pass", res
    resolved = next(x for x in seen if x.get("kind") == "approval_resolved")["payload"]
    assert resolved["scope"] == "session" and resolved["display"] == "已允许（本次任务）"
    assert Path(res["run_dir"]).is_relative_to(home)
