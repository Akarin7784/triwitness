"""判分管线正反验证（spec 004 AC2、AC3；W1-30/31）。真实 Docker，不调模型（免费）。

本地：`sg docker -c "uv run pytest -m integration tests/integration/eval"`
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from triwitness.eval.agents import TAMPER_CONFTEST, LLMAgent
from triwitness.eval.grade import Grader
from triwitness.eval.report import write_report
from triwitness.eval.runner import EvalRunner, RunConfig
from triwitness.eval.task import EvalTask, discover, load_task
from triwitness.eval.validate import run_verifier
from triwitness.harness.testing import FakeRouter, call, say
from triwitness.sandbox.docker import LABEL, DockerSandboxBackend, _client

pytestmark = pytest.mark.integration

DEV = Path(__file__).resolve().parents[3] / "evals" / "tasks" / "dev"


@pytest.fixture(scope="module")
def tasks(tmp_path_factory: pytest.TempPathFactory) -> list[EvalTask]:
    probe = asyncio.run(DockerSandboxBackend(home=tmp_path_factory.mktemp("h")).probe())
    if not probe.available:
        pytest.skip(f"Docker 不可用：{probe.reason}")
    return [load_task(d) for d in discover(DEV)]


@pytest.fixture
def grader(tmp_path: Path) -> Grader:
    return Grader(DockerSandboxBackend(home=tmp_path / "home"))


def _no_leftovers() -> None:
    assert _client().containers.list(all=True, filters={"label": f"{LABEL}=true"}) == []


async def test_ac3_null_oracle_tamper(tasks: list[EvalTask], grader: Grader, tmp_path: Path) -> None:
    r = EvalRunner(grader=grader, results_root=tmp_path / "results")
    configs = [RunConfig.fake("null"), RunConfig.fake("oracle"), RunConfig.fake("tamper")]
    s = await r.run(tasks, configs, out_dir=tmp_path / "run", concurrency=4)
    assert not s.infra_errors, s.infra_errors
    n = len(tasks)
    by = {c.name: [x for x in s.done if x.config == c.name] for c in configs}
    assert [len(v) for v in by.values()] == [n, n, n]
    assert sum(x.resolved for x in by["null-agent"]) == 0  # 空 Agent：Resolved = 0
    assert sum(x.resolved for x in by["oracle-agent"]) == n  # 作弊（执行参考解）：全部解决
    for x in by["tamper-agent"]:  # 篡改测试基础设施：被识别、判 0、记虚假成功
        assert not x.resolved and x.reward == 0 and x.tamper_paths == ["conftest.py"] and x.false_success
    rows = {row.config: row for row in write_report(tmp_path / "run").rows}
    assert rows["null-agent"].resolved_at_1 == 0 and rows["oracle-agent"].resolved_at_1 == 1
    assert rows["tamper-agent"].false_success == n and rows["tamper-agent"].tampered == n
    _no_leftovers()


async def test_tamper_attack_is_real_without_filter(tasks: list[EvalTask], grader: Grader) -> None:
    """对照：如果 Grader 照单全收，篡改的 conftest.py 真的能让隐藏测试“通过”。"""
    task = next(t for t in tasks if t.id == "csv-blank-line")
    sb = await grader.new_sandbox(task)
    try:
        await sb.write_file(f"{sb.spec.workdir}/conftest.py", TAMPER_CONFTEST.encode())
        patch = await sb.diff("base")
    finally:
        await sb.close()
    clean = await grader.new_sandbox(task)
    try:
        await clean.apply_patch(patch)
        phase = await asyncio.to_thread(run_verifier, task, clean.container, user="1000:1000",
                                        workdir=clean.spec.workdir)  # fmt: skip
    finally:
        await clean.close()
    assert phase.reward == 1  # 攻击有效 → 过滤是必需的
    graded = await grader.grade(task, patch)
    assert graded.reward == 0 and graded.tamper_paths == ["conftest.py"]
    _no_leftovers()


async def test_ac2_agent_sandbox_has_no_tests_or_solution(tasks: list[EvalTask], grader: Grader) -> None:
    """Agent 沙箱里：没有 /tests、/solution、solve.sh / test.sh；隐藏测试文件（按内容哈希）一个都找不到。"""
    for task in tasks:
        hidden = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in task.tests_dir.rglob("*") if p.is_file() and p.name != "test.sh"}  # fmt: skip
        assert hidden
        sb = await grader.new_sandbox(task)
        try:
            assert (await sb.exec("ls /tests /solution 2>&1")).exit_code != 0
            res = await sb.exec("find / -xdev \\( -name solve.sh -o -name test.sh \\) 2>/dev/null | head", timeout_s=60)
            assert res.stdout.strip() == "", (task.id, res.stdout)
            names = " -o ".join(f"-name {n}" for n in hidden)
            res = await sb.exec(f"find / -xdev -type f \\( {names} \\) -exec sha256sum {{}} + 2>/dev/null",
                                timeout_s=120)  # fmt: skip
            found = {line.split()[0] for line in res.stdout.splitlines() if line.strip()}
            assert not found & set(hidden.values()), (task.id, res.stdout)
        finally:
            await sb.close()
    _no_leftovers()


async def test_scripted_llm_agent_resolves_in_docker(tasks: list[EvalTask], grader: Grader, tmp_path: Path) -> None:
    """真实 AgentLoop + docker 工具，模型换成脚本（离线）：编辑 → run_tests → finish → Grader 判 1。"""
    task = next(t for t in tasks if t.id == "slugify-edges")
    OLD = 'sub("-", text.lower())'
    finish = {"summary": "去掉首尾连字符", "changes": [{"path": "textkit/slug.py", "kind": "modified"}],
              "tests_run": ["python -m pytest -q"], "tests_passed": True, "confidence": 0.9}  # fmt: skip
    script = [
        say(call("read_file", path="textkit/slug.py")),
        say(call("edit_file", path="textkit/slug.py", old_str=OLD, new_str=OLD + '.strip("-")')),
        say(call("run_tests")),
        say(call("finish", **finish)),
    ]
    agent = LLMAgent(lambda: FakeRouter(list(script)))
    r = EvalRunner(grader=grader, llm_agent_factory=lambda cfg: agent, results_root=tmp_path / "results")
    s = await r.run([task], [RunConfig(name="scripted", agent="llm")], out_dir=tmp_path / "run")
    assert not s.infra_errors, s.infra_errors
    [res] = s.done
    assert res.resolved and res.agent_claimed_success and not res.false_success and res.steps == 4
    traj = (tmp_path / "run" / res.trajectory_id).read_text(encoding="utf-8")
    assert '"kind":"tool_call"' in traj.replace(" ", "") and "passed" in traj
    _no_leftovers()
