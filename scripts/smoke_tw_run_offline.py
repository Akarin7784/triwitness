"""离线可用性检查（W3-14 后续）：`tw run` 默认流程端到端，FakeRouter 驱动，¥0。

默认 harness = repro-first、默认验证 = deterministic；模拟用户在审批卡上点“允许一次”
（submit_repro 跑模型给的命令需要审批）。
用法：uv run python scripts/smoke_tw_run_offline.py
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from triwitness.core.events import ApprovalRequestedPayload
from triwitness.harness.approvals import ApprovalDecision
from triwitness.harness.local_run import run_local
from triwitness.harness.testing import FakeRouter, call, say
from triwitness.sandbox.local import LocalSandboxBackend

REPRO = "tests/tw_repro/test_issue_1.py"
PY = f'"{sys.executable}" -m pytest -q -p no:cacheprovider'
FILES = {
    "calc.py": "def add(a, b):\n    return a - b\n",
    "tests/__init__.py": "",
    "tests/test_calc.py": "from calc import add\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n",
}


def make_repo(root: Path) -> None:
    for path, text in FILES.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")
    git = ["git", "-c", "user.email=tw@example.com", "-c", "user.name=tw"]
    for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "init"]):
        subprocess.run([*git, *args], cwd=root, check=True)


async def main() -> int:
    approvals: list[str] = []

    async def approver(req: ApprovalRequestedPayload) -> ApprovalDecision:
        approvals.append(req.action)
        return ApprovalDecision(decision="allow", scope="once")

    tmp = Path(tempfile.mkdtemp(prefix="tw-smoke-"))
    root, home = tmp / "repo", tmp / "home"
    root.mkdir()
    make_repo(root)
    repro_test = "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    fin = {"summary": "add 改为加法", "changes": [{"path": "calc.py", "kind": "modified"}], "tests_run": ["pytest"],
           "tests_passed": True, "confidence": 0.9}  # fmt: skip
    script = [
        say(call("read_file", path="calc.py")),
        say(call("write_file", path=REPRO, content=repro_test)),
        say(call("submit_repro", path=REPRO, cmd=f"{PY} {REPRO}")),
        # 注意：同长度改动（a - b → a + b）在同一秒内会让 pytest 读到旧 .pyc（mtime+size 相同）→ 已知问题，见 W3-14 后续
        say(call("edit_file", path="calc.py", old_str="return a - b", new_str="return int(a) + int(b)")),
        say(call("run_tests")),
        say(call("finish", **fin)),
    ]
    out = await run_local(root, "add(1, 2) 返回 -1，应为 3", router=FakeRouter(script), backend="none",
                          backends=[LocalSandboxBackend(home=home)], home=home, test_command=PY,
                          verify="deterministic", approver=approver)  # fmt: skip
    r = out.result
    ev = json.loads((out.run_dir / "evidence.json").read_text(encoding="utf-8"))
    events = [json.loads(x) for x in (out.run_dir / "trajectory.jsonl").read_text(encoding="utf-8").splitlines()]
    harness = next(e["payload"]["harness"] for e in events if e["kind"] == "task_started")
    print(f"harness {harness} | status {r.status} | repro {r.repro_status} | approvals {len(approvals)}")
    print(f"verdict {ev.get('verdict')} | risk {ev.get('risk_level')} | pr.md {(out.run_dir / 'pr.md').exists()}")
    ok = (harness, r.status, r.repro_status, ev.get("verdict")) == ("repro-first", "done", "reproduced", "pass")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
