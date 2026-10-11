"""`tw run --repo <路径> --issue "..."`（W1-33）：在本地仓库上以 Executor 单角色修一个问题。

select_backend（auto：docker → none）→ 创建沙箱（none：git worktree，分支 tw/<run_id>；docker：copy_in）
→ 权限引擎把关每个工具调用（非交互：ask 视为 deny）→ run_task
→ （verify ≠ off）VERIFYING：从同一后端新建一次性沙箱复跑复现 / 回归 + 静态检查（+ Verifier 模型）
→ 产出 patch.diff、finish.json、cost.md、trajectory.jsonl、evidence.json、pr.md。
none 后端结束时把改动提交到分支 tw/<run_id>（用户仓库工作区与当前分支不动），由用户决定是否合并。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from triwitness.config import tw_home
from triwitness.core.ids import new_run_id, new_task_id
from triwitness.core.models import Budget
from triwitness.cost.report import render_cost_markdown
from triwitness.harness.approvals import Approver, PermissionGate
from triwitness.harness.config import HarnessConfig
from triwitness.harness.inputs import archive_attachments, compose_task
from triwitness.harness.loop import RouterLike
from triwitness.harness.resume import ResumeState
from triwitness.harness.run import TaskResult, run_task
from triwitness.permissions.config import SessionOverrides, load_policy
from triwitness.permissions.engine import PermissionEngine
from triwitness.permissions.mode import ModeController
from triwitness.permissions.reviewer import Reviewer
from triwitness.sandbox.base import SandboxBackend, SandboxSpec, select_backend
from triwitness.telemetry.trajectory import TrajectoryEvent, TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools
from triwitness.verify.pipeline import EphemeralBackend, VerifyOptions

BackendPref = Literal["auto", "docker", "none"]
VerifyPref = Literal["off", "deterministic", "model"]


@dataclass
class LocalRunOutcome:
    result: TaskResult
    backend: str
    run_dir: Path
    branch: str | None  # none 后端：保留改动的分支
    repo: str | None = None  # 本地仓库路径（开 PR 用）


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
    verify: VerifyPref = "off",
    on_event: Callable[[TrajectoryEvent], None] | None = None,
    session: SessionOverrides | None = None,
    attachments: list[Path] | None = None,
    guidance: str | None = None,
    reviewer: Reviewer | None = None,
    recorder: TrajectoryRecorder | None = None,
    resume: ResumeState | None = None,
) -> LocalRunOutcome:
    repo = repo.resolve()
    home = home or tw_home()
    choice = await select_backend(backend, backends or _backends(home))
    # 对话轮（harness/chat.py）转成任务时传入已建好的 recorder：同一个 run、同一条轨迹
    run_id = recorder.run_id if recorder is not None else new_run_id()
    spec = SandboxSpec(repo=repo, run_id=run_id, network="none")
    sb = await choice.backend.create(spec)
    run_dir = home / "runs" / run_id
    rec = recorder or TrajectoryRecorder(new_task_id(), run_id, run_dir=run_dir)
    if on_event is not None and recorder is None:  # 桌面端桥接（tw run --jsonl）：事件写盘后同步推出去
        rec.subscribe(on_event)
    branch: str | None = None
    result: TaskResult | None = None
    composed = compose_task(issue, guidance=guidance, attachments=attachments)
    if attachments:
        archive_attachments(attachments, run_dir)
    modes: ModeController | None = None
    try:
        policy = load_policy(repo, backend=choice.backend.name, interactive=approver is not None, home=home,
                             session=session)  # fmt: skip
        if session is not None and (session.mode is not None or session.unrestricted is not None):
            base = load_policy(repo, backend=choice.backend.name, interactive=approver is not None, home=home)
            modes = ModeController(base_mode=base.mode, backend=choice.backend.name, interactive=approver is not None)
            changed = modes.adopt(policy.mode, task_id=rec.task_id, reason="本次任务设置")
            if changed is not None:  # 桌面端横幅以这条事件为准（勇士模式 risk=high）
                rec.emit(changed)
        engine = PermissionEngine(policy, workspace=sb.spec.workdir)
        gate = PermissionGate(engine, rec, approver=approver, repo_for_always=repo, reviewer=reviewer)
        shell = getattr(getattr(sb, "shell", None), "kind", "bash")
        registry = ToolRegistry(default_tools(shell=shell, names=(harness or HarnessConfig.default()).tools), gate=gate)
        tw_dir = str(getattr(sb, "tw_dir", "/workspace/.tw"))
        agents_md = repo / "AGENTS.md"
        opts = None
        if verify != "off":
            opts = VerifyOptions(backend=EphemeralBackend(choice.backend), spec=SandboxSpec(repo=repo, network="none"),
                                 mode=verify, router=router if verify == "model" else None)  # type: ignore[arg-type]  # fmt: skip
        result = await run_task(
            recorder=rec,
            router=router,
            registry=registry,
            sandbox=sb,
            issue_title=title or issue.strip().splitlines()[0][:80],
            task_prompt=composed.prompt,
            repo=repo.name,
            budget=budget or Budget.for_run(),
            config_hash="tw-run",
            test_command=test_command,
            agents_md=agents_md.read_text(encoding="utf-8")[:4000] if agents_md.is_file() else None,
            config=harness,
            tw_dir=tw_dir,
            category="dogfood",
            verify=opts,
            stream=on_event is not None,  # 桌面端：写流式增量（model_delta / reasoning_delta）
            resume=resume,
            progress_dir=run_dir,  # 每步存续跑进度（harness/resume.py）
        )
    finally:
        if modes is not None and (back := modes.on_task_finished(rec.task_id)) is not None:
            rec.emit(back)
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
    if result.verification is not None:
        (run_dir / "evidence.json").write_text(result.verification.evidence.model_dump_json(indent=2), encoding="utf-8")
        (run_dir / "pr.md").write_text(result.verification.pr_body, encoding="utf-8")
    if result.finish is not None:
        (run_dir / "finish.json").write_text(result.finish.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps({"status": result.status, "backend": choice.backend.name,
                                                      "branch": branch, "repo": str(repo.resolve()),
                                                      "steps": result.outcome.steps,
                                                      "verdict": result.verification.evidence.verdict
                                                      if result.verification else None,
                                                      "reason": result.outcome.reason}, ensure_ascii=False,
                                                     indent=2), encoding="utf-8")  # fmt: skip
    return LocalRunOutcome(result=result, backend=choice.backend.name, run_dir=run_dir, branch=branch,
                           repo=str(repo.resolve()))  # fmt: skip


__all__ = ["LocalRunOutcome", "run_local"]
