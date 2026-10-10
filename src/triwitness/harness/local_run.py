"""`tw run --repo <路径> --issue "..."`（W1-33）：在本地仓库上以 Executor 单角色修一个问题。

select_backend（auto：docker → none）→ 创建沙箱（none：git worktree，分支 tw/<run_id>；docker：copy_in）
→ 权限引擎把关每个工具调用（非交互：ask 视为 deny）→ run_task
→ 产出 patch.diff、finish.json、cost.md、trajectory.jsonl。
none 后端结束时把改动提交到分支 tw/<run_id>（用户仓库工作区与当前分支不动），由用户决定是否合并。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from triwitness.config import tw_home
from triwitness.core.ids import new_run_id, new_task_id
from triwitness.core.models import Budget
from triwitness.cost.report import render_cost_markdown
from triwitness.harness.approvals import Approver, PermissionGate
from triwitness.harness.config import HarnessConfig
from triwitness.harness.loop import RouterLike
from triwitness.harness.run import TaskResult, run_task
from triwitness.permissions.config import load_policy
from triwitness.permissions.engine import PermissionEngine
from triwitness.sandbox.base import SandboxBackend, SandboxSpec, select_backend
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools

BackendPref = Literal["auto", "docker", "none"]


@dataclass
class LocalRunOutcome:
    result: TaskResult
    backend: str
    run_dir: Path
    branch: str | None  # none 后端：保留改动的分支


def _backends(home: Path) -> list[SandboxBackend]:
    from triwitness.sandbox.docker import DockerSandboxBackend
    from triwitness.sandbox.local import LocalSandboxBackend

    return [DockerSandboxBackend(home=home), LocalSandboxBackend(home=home)]


async def run_local(
    repo: Path,
    issue: str,
    *,
    router: RouterLike,
    title: str | None = None,
    backend: BackendPref = "auto",
    test_command: str | None = None,
    home: Path | None = None,
    backends: list[SandboxBackend] | None = None,
    approver: Approver | None = None,
    budget: Budget | None = None,
    harness: HarnessConfig | None = None,
) -> LocalRunOutcome:
    repo = repo.resolve()
    home = home or tw_home()
    choice = await select_backend(backend, backends or _backends(home))
    run_id = new_run_id()
    spec = SandboxSpec(repo=repo, run_id=run_id, network="none")
    sb = await choice.backend.create(spec)
    run_dir = home / "runs" / run_id
    rec = TrajectoryRecorder(new_task_id(), run_id, run_dir=run_dir)
    branch: str | None = None
    result: TaskResult | None = None
    try:
        policy = load_policy(repo, backend=choice.backend.name, interactive=approver is not None, home=home)
        engine = PermissionEngine(policy, workspace=sb.spec.workdir)
        gate = PermissionGate(engine, rec, approver=approver, repo_for_always=repo)
        shell = getattr(getattr(sb, "shell", None), "kind", "bash")
        registry = ToolRegistry(default_tools(shell=shell, names=(harness or HarnessConfig.load()).tools), gate=gate)
        tw_dir = str(getattr(sb, "tw_dir", "/workspace/.tw"))
        agents_md = repo / "AGENTS.md"
        result = await run_task(
            recorder=rec,
            router=router,
            registry=registry,
            sandbox=sb,
            issue_title=title or issue.strip().splitlines()[0][:80],
            task_prompt=issue,
            repo=repo.name,
            budget=budget or Budget.for_run(),
            config_hash="tw-run",
            test_command=test_command,
            agents_md=agents_md.read_text(encoding="utf-8")[:4000] if agents_md.is_file() else None,
            config=harness,
            tw_dir=tw_dir,
            category="dogfood",
        )
    finally:
        finish = getattr(sb, "finish", None)
        if finish is not None:  # none 后端：有改动则提交到 tw/<run_id> 分支保留，没有就连分支一起丢弃
            changed = result is not None and bool(result.diff.strip())
            await finish("keep" if changed else "discard")
            branch = f"tw/{run_id}" if changed else None
        else:
            await sb.close()
    assert result is not None
    (run_dir / "patch.diff").write_text(result.diff, encoding="utf-8")
    (run_dir / "cost.md").write_text(render_cost_markdown(result.cost), encoding="utf-8")
    if result.finish is not None:
        (run_dir / "finish.json").write_text(result.finish.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps({"status": result.status, "backend": choice.backend.name,
                                                      "branch": branch, "steps": result.outcome.steps,
                                                      "reason": result.outcome.reason}, ensure_ascii=False,
                                                     indent=2), encoding="utf-8")  # fmt: skip
    return LocalRunOutcome(result=result, backend=choice.backend.name, run_dir=run_dir, branch=branch)


__all__ = ["LocalRunOutcome", "run_local"]
