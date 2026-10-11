"""W5-04/05/06（spec 012 §4–§6）：PACKAGING → (AWAIT_PR_APPROVAL) → PR_OPENED → CI_WATCH ⇄ EXECUTING。

真实 none 后端 + FakeRouter + 假 Publisher；另有一条用真 GitHubPublisher（本地 bare 远端 + 假 GitHub API）。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

from triwitness.core.models import Budget
from triwitness.github.ci import CheckRun, CiResult
from triwitness.github.publish import GitHubPublisher, PrRef, pr_action
from triwitness.harness.approvals import ApprovalDecision
from triwitness.harness.config import CiWatchConfig, GithubConfig, HarnessConfig
from triwitness.harness.run import TaskResult, run_task
from triwitness.harness.testing import FakeRouter, call, say
from triwitness.llm.types import Message
from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools
from triwitness.verify.testing import make_repo

PY = f'"{Path(sys.executable).as_posix()}" -m pytest -q -p no:cacheprovider'
REPRO = "tests/tw_repro/test_issue_1.py"
WRITE_REPRO = call("write_file", path=REPRO, content="from calc import add\n\n\ndef test_issue():\n"
                   "    assert add(1, 2) == 3\n")  # fmt: skip
RIGHT = call("edit_file", path="calc.py", old_str="a - b", new_str="a + b")
DOC = call("edit_file", path="calc.py", old_str="def add(a, b):", new_str="def add(a, b):  # noqa")


def finish(summary: str = "add 改成加法。复现测试通过") -> Message:
    return say(call("finish", summary=summary, changes=[{"path": "calc.py", "kind": "modified"}],
                    tests_run=[f"pytest {REPRO}"], tests_passed=True, confidence=0.9,
                    repro={"path": REPRO, "cmd": f"{PY} {REPRO}"}))  # fmt: skip


class FakePublisher:
    def __init__(self, ci: list[str] | None = None) -> None:
        self.opened: list[tuple[str, str, bool]] = []
        self.pushed: list[int] = []
        self.ci_q = list(ci or ["success"])
        self.watched: list[str] = []

    async def open(self, *, title: str, body: str, draft: bool) -> PrRef:
        self.opened.append((title, body, draft))
        return PrRef("https://github.com/o/r/pull/7", 7, "o/r", "tw/exec1", "sha0", draft, True, False)

    async def push(self, n: int) -> str:
        self.pushed.append(n)
        return f"sha{n}"

    async def ci(self, sha: str, cfg: CiWatchConfig) -> CiResult:
        self.watched.append(sha)
        st = self.ci_q.pop(0)
        fail = st == "failure"
        return CiResult(st, sha, [CheckRun("test", "completed", "failure" if fail else "success", job_id=1)],  # type: ignore[arg-type]
                        logs={"test": "E   assert add(2, 0) == 2"} if fail else {})  # fmt: skip


@pytest.fixture
def env(tmp_path: Path) -> tuple[LocalSandboxBackend, Path]:
    repo = make_repo(tmp_path, {"calc.py": "def add(a, b):\n    return a - b\n", "tests/__init__.py": "",
                                "tests/tw_repro/__init__.py": ""})  # fmt: skip
    return LocalSandboxBackend(home=tmp_path / "home"), repo


def cfg(**policy: str) -> HarnessConfig:
    c = HarnessConfig.load("harness/orchestrated-1m.yaml")
    c.orchestration.planner.enabled = False
    c.orchestration.reviewer.enabled = False
    gh = GithubConfig()
    gh.pr_policy.update(policy)  # type: ignore[arg-type]
    c.github = gh
    return c


async def go(env: tuple, script: list[Message], pub: Any, config: HarnessConfig, *, approver: Any = None,
             mode: str = "background") -> tuple[TaskResult, TrajectoryRecorder]:  # type: ignore[type-arg]  # fmt: skip
    backend, repo = env
    sb = await backend.create(SandboxSpec(repo=repo, run_id="exec1"))
    rec = TrajectoryRecorder("t_p", "r_p", run_dir=repo.parent / "run")
    router = FakeRouter(script)
    LAST["router"] = router
    try:
        res = await run_task(recorder=rec, router=router, registry=ToolRegistry(default_tools()),
                             sandbox=sb, issue_title="add 是减法", task_prompt="add(1, 2) 应该是 3", repo="o/r",
                             budget=Budget(), config_hash="c", test_command=PY, tw_dir=str(sb.tw_dir),  # type: ignore[attr-defined]
                             config=config, mode=mode, approver=approver, publisher=pub)  # type: ignore[arg-type]  # fmt: skip
    finally:
        await sb.finish("discard")  # type: ignore[attr-defined]
    return res, rec


def states(rec: TrajectoryRecorder) -> list[str]:
    return [str(e.payload["to"]) for e in rec.events if e.kind == "state_change"]


def kinds(rec: TrajectoryRecorder, kind: str) -> list[dict[str, Any]]:
    return [e.payload for e in rec.events if e.kind == kind]


BASE = [say(WRITE_REPRO), say(RIGHT), finish()]
LAST: dict[str, Any] = {}


def test_pr_action_by_risk() -> None:
    gh = GithubConfig()
    assert [pr_action(r, gh) for r in ("L0", "L1", "L2", "L3")] == ["confirm", "confirm", "draft", "none"]
    assert pr_action(None, gh) == "draft"  # 未知按 L2
    gh.pr_policy["L0"] = "auto"
    assert pr_action("L0", gh) == "auto"


async def test_l3_policy_does_not_open_pr(env: tuple) -> None:  # type: ignore[type-arg]
    pub = FakePublisher()
    res, rec = await go(env, BASE, pub, cfg(L2="none"))
    assert res.status == "done" and res.pr is None and not pub.opened
    assert states(rec)[-2:] == ["packaging", "done"]
    assert "不开 PR" in kinds(rec, "state_change")[-1]["display"]


async def test_auto_opens_pr_and_watches_ci(env: tuple) -> None:  # type: ignore[type-arg]
    pub = FakePublisher(["success"])
    res, rec = await go(env, BASE, pub, cfg(L2="auto"))
    assert states(rec)[-4:] == ["packaging", "pr_opened", "ci_watch", "done"]
    assert res.pr is not None and res.pr.number == 7 and res.ci is not None and res.ci.state == "success"
    title, body, draft = pub.opened[0]
    assert title == "[TriWitness] add 改成加法" and not draft and "执行者自述" in body
    assert not kinds(rec, "approval_requested")
    assert (rec.run_dir / "artifacts" / "pr.json").is_file() or any(  # type: ignore[operator]
        e.kind == "artifact" for e in rec.events
    )


async def test_confirm_without_channel_keeps_branch_no_pr(env: tuple) -> None:  # type: ignore[type-arg]
    pub = FakePublisher()
    res, rec = await go(env, BASE, pub, cfg(L2="confirm"))
    assert res.status == "done" and not pub.opened
    assert states(rec)[-3:] == ["packaging", "await_pr_approval", "done"]
    req = kinds(rec, "approval_requested")[0]
    assert req["tool"] == "OpenPR" and req["risk"] == "L2"
    assert "需要确认" in kinds(rec, "state_change")[-1]["display"]


async def test_draft_after_approval_and_reject(env: tuple, tmp_path: Path) -> None:  # type: ignore[type-arg]
    async def allow(req: Any) -> ApprovalDecision:
        return ApprovalDecision(decision="allow")

    pub = FakePublisher()
    res, rec = await go(env, BASE, pub, cfg(), approver=allow)  # 默认：未知风险按 L2 → draft
    assert pub.opened[0][2] is True and res.pr is not None and res.pr.draft
    assert kinds(rec, "approval_resolved")[-1]["decision"] == "allow"

    async def deny(req: Any) -> ApprovalDecision:
        return ApprovalDecision(decision="deny", comment="先别开")

    pub2 = FakePublisher()
    res2, rec2 = await go(env, BASE, pub2, cfg(), approver=deny)
    assert not pub2.opened and res2.pr is None and "被拒绝" in kinds(rec2, "state_change")[-1]["display"]


async def test_ci_failure_triggers_fix_round_then_push(env: tuple) -> None:  # type: ignore[type-arg]
    pub = FakePublisher(["failure", "success"])
    script = [*BASE, say(DOC), finish("补上修复")]
    res, rec = await go(env, script, pub, cfg(L2="auto"))
    assert states(rec)[-8:] == ["packaging", "pr_opened", "ci_watch", "executing", "packaging", "pr_opened",
                                "ci_watch", "done"]  # fmt: skip
    assert pub.pushed == [1] and pub.watched == ["sha0", "sha1"] and res.ci is not None and res.ci.state == "success"
    fix_req = LAST["router"].requests[-2]  # CI 返工那一轮的第一个请求：带 CI 失败日志（不可信块）
    text = "\n".join(m.content or "" for m in fix_req.messages)
    assert '<untrusted source="ci-log:test">' in text and "assert add(2, 0) == 2" in text
    assert "noqa" in res.diff


async def test_ci_still_failing_after_max_rounds(env: tuple) -> None:  # type: ignore[type-arg]
    c = cfg(L2="auto")
    c.github.ci.max_fix_rounds = 0
    pub = FakePublisher(["failure"])
    res, rec = await go(env, BASE, pub, c)
    assert res.status == "done" and not pub.pushed
    assert "CI 仍失败" in kinds(rec, "state_change")[-1]["display"]


async def test_eval_never_publishes(env: tuple) -> None:  # type: ignore[type-arg]
    pub = FakePublisher()
    _, rec = await go(env, BASE, pub, cfg(L2="auto"), mode="eval")
    assert not pub.opened and "pr_opened" not in states(rec)


def _git(cwd: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True).stdout.strip()


async def test_github_publisher_pushes_branch_and_opens_once(env: tuple, tmp_path: Path) -> None:  # type: ignore[type-arg]
    backend, repo = env
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    _git(repo, "remote", "add", "origin", "https://github.com/acme/demo.git")
    _git(repo, "push", "-q", str(bare), "HEAD:main")
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.method == "GET":
            return httpx.Response(200, json=[])
        body = json.loads(req.content)
        assert body["head"] == "tw/pub1" and body["draft"] is True
        return httpx.Response(201, json={"html_url": "https://github.com/acme/demo/pull/9", "number": 9})

    home = tmp_path / "home"
    sb = await backend.create(SandboxSpec(repo=repo, run_id="pub1"))
    try:
        await sb.write_file(f"{sb.spec.workdir}/calc.py", b"def add(a, b):\n    return a + b\n")
        pub = GitHubPublisher(sandbox=sb, repo_path=repo, run_id="r_01M4NM3Y9RJZZNKAF4EFQH0MJZ", home=home,  # type: ignore[arg-type]
                              env={"GITHUB_TOKEN": "ghp_" + "f" * 36}, push_url=str(bare),
                              http_client=httpx.Client(transport=httpx.MockTransport(handler)))  # fmt: skip
        (home / "runs" / "r_01M4NM3Y9RJZZNKAF4EFQH0MJZ").mkdir(parents=True)
        ref = await pub.open(title="t", body="b", draft=True)
        assert ref.number == 9 and ref.created and not ref.reused
        assert _git(bare, "rev-parse", "refs/heads/tw/pub1") == ref.sha
        again = await pub.open(title="t", body="b", draft=True)  # 幂等：不再推送 / 开 PR
        assert again.reused and len([r for r in seen if r.method == "POST"]) == 1
        await sb.write_file(f"{sb.spec.workdir}/calc.py", b"def add(a, b):\n    return b + a\n")
        sha = await pub.push(1)
        assert _git(bare, "rev-parse", "refs/heads/tw/pub1") == sha != ref.sha
    finally:
        await sb.finish("discard")  # type: ignore[attr-defined]
