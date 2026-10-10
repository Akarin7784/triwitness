"""W2-25：Grader 以 uid 1000 跑 test.sh 时 HOME 必须可写（任务校验用 root，判分用 1000，环境不一致）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from triwitness.eval.suites import discover
from triwitness.eval.task import load_task
from triwitness.eval.validate import run_verifier

DEV = Path(__file__).resolve().parents[3] / "evals" / "tasks" / "dev"


class FakeContainer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def put_archive(self, path: str, data: bytes) -> bool:
        return True

    def exec_run(self, cmd: list[str], **kw: Any) -> tuple[int, bytes]:
        self.calls.append({"cmd": cmd, **kw})
        return 0, b"ok"

    def get_archive(self, path: str) -> Any:
        raise FileNotFoundError(path)


def _task() -> Any:
    return load_task(discover(DEV)[0])


def test_non_root_verifier_gets_writable_home() -> None:
    c = FakeContainer()
    run_verifier(_task(), c, user="1000:1000")
    assert c.calls[-1]["environment"]["HOME"] == "/tmp"


def test_root_verifier_env_untouched() -> None:
    c = FakeContainer()
    run_verifier(_task(), c, user="root")
    assert "HOME" not in c.calls[-1]["environment"]
