"""W5-06：CI 状态归并、日志精简、轮询（假客户端，不联网）。"""

from __future__ import annotations

import json
import subprocess
from typing import Any

import httpx

from triwitness.github.ci import (
    CheckRun,
    CiResult,
    GhCiClient,
    TokenCiClient,
    ci_feedback,
    condense_log,
    summarize,
    watch,
)

RUNS = {
    "check_runs": [
        {"name": "test (3.12)", "status": "completed", "conclusion": "failure",
         "details_url": "https://github.com/o/r/actions/runs/111/job/222"},
        {"name": "lint", "status": "completed", "conclusion": "success",
         "details_url": "https://github.com/o/r/actions/runs/111/job/223"},
    ]
}  # fmt: skip


def cr(status: str = "completed", conclusion: str | None = "success", name: str = "t") -> CheckRun:
    return CheckRun(name=name, status=status, conclusion=conclusion, job_id=1)


def test_summarize_states() -> None:
    assert summarize([]) == "none"
    assert summarize([cr(), cr("in_progress", None)]) == "pending"
    assert summarize([cr(), cr(conclusion="failure")]) == "failure"
    assert summarize([cr(conclusion="timed_out")]) == "failure"
    assert summarize([cr(), cr(conclusion="skipped"), cr(conclusion="cancelled")]) == "success"


def test_condense_keeps_errors_and_tail_and_strips_noise() -> None:
    noise = [f"2026-10-11T14:00:{i % 60:02d}.1234567Z collecting item {i}" for i in range(500)]
    log = "\n".join([*noise[:200], "2026-10-11T14:01:00.0Z E   assert add(2, 0) == 2", "\x1b[31mFAILED\x1b[0m t.py",
                     *noise[200:]])  # fmt: skip
    out = condense_log(log, 3000)
    assert "E   assert add(2, 0) == 2" in out and "FAILED t.py" in out
    assert "\x1b[" not in out and "2026-10-11T" not in out
    assert "collecting item 499" in out and "collecting item 100\n" not in out
    assert len(out) <= 3000


async def test_watch_polls_until_done_then_fetches_failed_logs() -> None:
    seq = [[], [cr("queued", None)], [cr(conclusion="failure", name="test"), cr(name="lint")]]
    slept: list[float] = []
    now = [0.0]

    class C:
        def check_runs(self, repo: str, sha: str) -> list[CheckRun]:
            return seq.pop(0) if len(seq) > 1 else seq[0]

        def job_log(self, repo: str, check: CheckRun) -> str:
            return "line\nE   AssertionError: boom\nmore"

    async def sleep(s: float) -> None:
        slept.append(s)
        now[0] += s

    res = await watch(C(), "o/r", "abc", poll_s=5, sleep=sleep, clock=lambda: now[0])
    assert res.state == "failure" and [c.name for c in res.failed] == ["test"]
    assert "AssertionError: boom" in res.logs["test"] and slept == [5, 5]
    fb = ci_feedback(res)
    assert '<untrusted source="ci-log:test">' in fb and "不要删除或跳过测试" in fb


async def test_watch_no_checks_after_grace_and_timeout() -> None:
    now = [0.0]

    async def sleep(s: float) -> None:
        now[0] += s

    class Empty:
        def check_runs(self, repo: str, sha: str) -> list[CheckRun]:
            return []

        def job_log(self, repo: str, check: CheckRun) -> str:
            return ""

    res = await watch(Empty(), "o/r", "abc", poll_s=30, no_checks_grace_s=60, sleep=sleep, clock=lambda: now[0])
    assert res.state == "none" and res.display() == "仓库没有配置 CI 检查"

    class Stuck(Empty):
        def check_runs(self, repo: str, sha: str) -> list[CheckRun]:
            return [cr("in_progress", None)]

    now[0] = 0.0
    res = await watch(Stuck(), "o/r", "abc", poll_s=30, timeout_s=90, sleep=sleep, clock=lambda: now[0])
    assert res.state == "timeout"


def test_gh_client_parses_check_runs_and_falls_back_to_full_log() -> None:
    calls: list[list[str]] = []

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:2] == ["gh", "api"]:
            return subprocess.CompletedProcess(args, 0, json.dumps(RUNS), "")
        if "--log-failed" in args:
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0, "test\tstep\tE   boom ghp_" + "a" * 30, "")

    c = GhCiClient(runner)
    runs = c.check_runs("o/r", "abc")
    assert runs[0].failing and runs[0].job_id == 222 and runs[0].run_id == 111 and not runs[1].failing
    assert calls[0] == ["gh", "api", "repos/o/r/commits/abc/check-runs?per_page=100"]
    log = c.job_log("o/r", runs[0])
    assert "boom" in log and "ghp_" not in log and calls[-1][-1] == "--log"


def test_token_client_uses_rest_and_redacts() -> None:
    seen: list[httpx.Request] = []
    tok = "github_pat_" + "x" * 40

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path.endswith("/check-runs"):
            return httpx.Response(200, json=RUNS)
        return httpx.Response(200, text=f"E   failed with {tok}")

    c = TokenCiClient(tok, httpx.Client(transport=httpx.MockTransport(handler)))
    runs = c.check_runs("o/r", "abc")
    assert len(runs) == 2 and seen[0].headers["Authorization"] == f"Bearer {tok}"
    assert tok not in c.job_log("o/r", runs[0]) and seen[-1].url.path == "/repos/o/r/actions/jobs/222/logs"


def test_result_json_and_display() -> None:
    r = CiResult("failure", "abc", [cr(conclusion="failure", name="a"), cr(name="b")])
    d: dict[str, Any] = r.to_json()
    assert d["failed"] == ["a"] and r.display() == "CI 失败：a"
