"""`tw run --repo <路径> --issue "..."`（W1-33）：在本地仓库上以 Executor 单角色修一个问题。

select_backend（auto：docker → none）→ 创建沙箱（none：git worktree，分支 tw/<run_id>；docker：copy_in）
→ 权限引擎把关每个工具调用（非交互：ask 视为 deny）→ run_task
→ （verify ≠ off）VERIFYING：从同一后端新建一次性沙箱复跑复现 / 回归 + 静态检查（+ Verifier 模型）
→ 产出 patch.diff、finish.json、cost.md、trajectory.jsonl、evidence.json、pr.md。
none 后端结束时把改动提交到分支 tw/<run_id>（用户仓库工作区与当前分支不动），由用户决定是否合并。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from triwitness.config import tw_home
from triwitness.core.errors import TriWitnessError
from triwitness.core.ids import new_run_id, new_task_id
from triwitness.core.models import Budget
from triwitness.cost.report import render_cost_markdown
from triwitness.harness.approvals import Approver, PermissionGate
from triwitness.harness.config import HarnessConfig
from triwitness.harness.inputs import archive_attachments, compose_task
from triwitness.harness.loop import RouterLike
from triwitness.harness.resume import ResumeState
from triwitness.harness.run import TaskResult, run_task
from triwitness.memory.context import MemoryContext, open_memory
from triwitness.permissions.config import SessionOverrides, load_policy
from triwitness.permissions.engine import PermissionEngine
from triwitness.permissions.mode import ModeController
from triwitness.permissions.reviewer import Reviewer
from triwitness.sandbox.base import SandboxBackend, SandboxSpec, select_backend
from triwitness.telemetry.trajectory import TrajectoryEvent, TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools
from triwitness.verify.pipeline import EphemeralBackend, VerifyOptions

log = logging.getLogger(__name__)
AGENTS_MD_READ_MAX = 200_000  # 只防超大文件；实际注入长度由 run_task 按 allocation.prefix 的余量决定

BackendPref = Literal["auto", "docker", "none"]
VerifyPref = Literal["off", "deterministic", "model"]


@dataclass(frozen=True)
class PublishOptions:
    """`tw run --open-pr`：收尾时按风险决定开 PR、盯 CI（W5，spec 012）。
    只支持 none 后端（改动在 tw/<run_id> 分支）。"""

    remote: str = "origin"
    base: str | None = None
    watch_ci: bool | None = None  # None = 用 harness 的 github.ci.watch


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
    publish: PublishOptions | None = None,
    memory: bool | None = None,
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
    store = _open_store(home)  # W4-15：任务与事件写 SQLite（TW_HOME/tw.db）；打不开只记日志
    if store is not None:
        for ev in list(rec.events):  # 对话轮已写的事件（同一个 run）
            store.observe(ev)
        rec.subscribe(store.observe)
    branch: str | None = None
    result: TaskResult | None = None
    mem: MemoryContext | None = None
    hcfg = harness or HarnessConfig.default()
    # 附件按 harness 的任务分配内联，避免进 ContextManager 后再被头尾截断
    composed = compose_task(issue, guidance=guidance, attachments=attachments,
                            max_chars=hcfg.context.chars(hcfg.context.allocation.task))  # fmt: skip
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
        gate = PermissionGate(engine, rec, approver=approver, repo_for_always=repo, reviewer=reviewer,
                              hitl=hcfg.orchestration.hitl)  # fmt: skip
        shell = getattr(getattr(sb, "shell", None), "kind", "bash")
        registry = ToolRegistry(default_tools(shell=shell, names=hcfg.tools), gate=gate)
        tw_dir = str(getattr(sb, "tw_dir", "/workspace/.tw"))
        agents_md = repo / "AGENTS.md"
        opts = None
        if verify != "off":
            opts = VerifyOptions(backend=EphemeralBackend(choice.backend), spec=SandboxSpec(repo=repo, network="none"),
                                 mode=verify, router=router if verify == "model" else None)  # type: ignore[arg-type]  # fmt: skip
        publisher = None
        if publish is not None:
            if hasattr(sb, "commit_branch"):
                from triwitness.github.publish import GitHubPublisher

                publisher = GitHubPublisher(sandbox=sb, repo_path=repo, run_id=run_id, home=home,  # type: ignore[arg-type]
                                            remote=publish.remote, base=publish.base)  # fmt: skip
                if publish.watch_ci is not None:
                    hcfg = hcfg.model_copy(update={"github": hcfg.github.model_copy(update={
                        "ci": hcfg.github.ci.model_copy(update={"watch": publish.watch_ci})})})  # fmt: skip
            else:
                log.warning("--open-pr 只支持 none 后端（%s 后端不开 PR，改动照常保留）", choice.backend.name)
        # W6：交互运行默认读本仓库的记忆（有才读）；--no-memory 关闭。这里只读，结束后只记 Skill 监控
        mem = open_memory(str(repo), home=home, mode="background", category="dogfood", override=memory)
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
            # 长度由 run_task 按 allocation.prefix 的余量截（不再写死 4000 字符）；这里只防超大文件
            agents_md=agents_md.read_text(encoding="utf-8")[:AGENTS_MD_READ_MAX] if agents_md.is_file() else None,
            config=hcfg,
            tw_dir=tw_dir,
            category="dogfood",
            verify=opts,
            stream=on_event is not None,  # 桌面端：写流式增量（model_delta / reasoning_delta）
            resume=resume,
            progress_dir=run_dir,  # 每步存续跑进度（harness/resume.py）
            approver=approver,  # 计划确认（spec 010 §8）与权限审批共用同一通道
            publisher=publisher,
            memory=mem,
        )
    finally:
        if store is not None:
            store.close()
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
                                                      "reason": result.outcome.reason,
                                                      "pr": result.pr.url if result.pr else None,
                                                      "ci": result.ci.state if result.ci else None},
                                                     ensure_ascii=False,
                                                     indent=2), encoding="utf-8")  # fmt: skip
    if mem is not None and mem.skills and result.verification is not None:
        _observe_skills(repo, home, mem, run_id, result.verification.evidence.verdict == "pass", run_dir)
    return LocalRunOutcome(result=result, backend=choice.backend.name, run_dir=run_dir, branch=branch,
                           repo=str(repo.resolve()))  # fmt: skip


def _observe_skills(repo: Path, home: Path, mem: MemoryContext, run_id: str, solved: bool, run_dir: Path) -> None:
    """Skill 监控（spec 013 §5.4）：记结果、退化的自动回滚。失败只记日志，不影响本次 run 的结果。"""
    from triwitness.memory.monitor import observe_run
    from triwitness.memory.store import MemoryStore

    try:
        store = MemoryStore.for_repo(str(repo), home)
        for h, new in observe_run(store.root, mem.skills, run_id=run_id, solved=solved,
                                  trajectory=run_dir / "trajectory.jsonl", commit=store.commit):  # fmt: skip
            log.warning("Skill 监控自动回滚：%s → %s", h.line(), f"v{new}" if new else "已移除")
    except (OSError, ValueError, TriWitnessError) as e:
        log.warning("Skill 监控写入失败（不影响本次结果）：%s", e)


def _open_store(home: Path):  # type: ignore[no-untyped-def]
    from triwitness.store.sqlite import TaskStore

    try:
        return TaskStore(home / "tw.db")
    except Exception as e:  # 任务库是辅助记录，打不开不影响任务
        log.warning("打不开任务库 %s：%s", home / "tw.db", e)
        return None


__all__ = ["LocalRunOutcome", "PublishOptions", "run_local"]
