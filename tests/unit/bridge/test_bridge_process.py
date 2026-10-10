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


def test_subprocess_unrestricted_attachments_mode_events(tmp_path: Path) -> None:
    """勇士模式 + 附件 + 用户说明：mode_changed（risk=high）→ 任务结束 auto_revert；附件留档。"""
    home = tmp_path / "home"
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "TW_DEMO_DELAY_S": "0",
           "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}  # fmt: skip
    env.pop("TW_HOME", None)
    env.pop("CI", None)  # 桌面端交互运行的路径；CI 环境变量本身会让勇士模式被拒
    note = tmp_path / "note.md"
    note.write_text("附件内容", encoding="utf-8")
    guide = tmp_path / "guide.md"
    guide.write_text("回答简洁", encoding="utf-8")
    args = ["--permission-mode", "unrestricted", "--confirm-unrestricted", "我了解风险", "--attach", str(note),
            "--guidance-file", str(guide)]  # fmt: skip
    p = subprocess.run(
        [sys.executable, "-m", "triwitness", "run", "--repo", str(tmp_path / "verses"), "--demo", "--jsonl", *args],
        input="", capture_output=True, env=env, text=True, encoding="utf-8", timeout=60,
    )  # fmt: skip
    assert p.returncode == 0, p.stderr
    seen = [json.loads(x) for x in p.stdout.splitlines() if x.strip()]
    modes = [x["payload"] for x in seen if x.get("kind") == "mode_changed"]
    assert [m["to_mode"] for m in modes][-1] != "unrestricted" and modes[0]["to_mode"] == "unrestricted"
    assert modes[0]["risk"] == "high" and modes[-1]["by"] == "auto_revert"
    assert not any(x.get("kind") == "approval_requested" for x in seen)
    res = seen[-1]
    assert res["bridge"] == "result"
    assert (Path(res["run_dir"]) / "attachments" / "note.md").read_text(encoding="utf-8") == "附件内容"
