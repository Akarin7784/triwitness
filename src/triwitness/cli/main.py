"""`tw` 命令行入口（W1-04 骨架：只有 --version）。"""

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from triwitness import __version__

if TYPE_CHECKING:
    from triwitness.core.models import Budget
    from triwitness.permissions.config import SessionOverrides

app = typer.Typer(add_completion=False, no_args_is_help=True, help="TriWitness（三证）")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"triwitness {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True, help="显示版本"),
) -> None:
    """TriWitness 命令行。"""


@app.command()
def doctor(as_json: Annotated[bool, typer.Option("--json", help="输出 JSON（桌面端用）")] = False) -> None:
    """环境自检：Docker / WSL2 / winget 状态与建议安装项。只读，不联网，不调用 API。"""
    import json

    from triwitness.sandbox.doctor import detect

    r = detect()
    if as_json:
        typer.echo(json.dumps(r.to_dict(), ensure_ascii=False))
        return
    for name, c in (("Docker", r.docker), ("WSL2", r.wsl), ("winget", r.winget)):
        typer.echo(f"{name:7} {c.state:8} {c.detail}{f'（{c.version}）' if c.version else ''}")
    if r.sandbox_ready:
        typer.echo("沙箱就绪")
    elif r.recommended:
        typer.echo(f"建议安装：{' / '.join(r.recommended)}（tw sandbox install <名称> --plan 查看命令）")
    else:
        typer.echo(f"沙箱未就绪：{r.docker.detail}")


@app.command("run")
def run_cmd(
    repo: Annotated[
        Path | None, typer.Option(help="本地 git 仓库路径；--jsonl 对话轮可省略（只聊天，要动手时请用户选仓库）")
    ] = None,
    issue: Annotated[str, typer.Option(help="问题描述（Issue 正文）；--jsonl 时是这一轮的用户消息")] = "",
    title: Annotated[str | None, typer.Option(help="标题（默认取描述第一行）")] = None,
    backend: Annotated[str, typer.Option(help="auto / docker / none")] = "auto",
    test_cmd: Annotated[str | None, typer.Option(help="run_tests 使用的测试命令")] = None,
    live: Annotated[bool, typer.Option("--live", help="真实调用模型（录制到回放缓存）；默认只回放")] = False,
    allow_peak: Annotated[bool, typer.Option("--allow-peak", hidden=True, help="（已移除，忽略）")] = False,
    verify: Annotated[str, typer.Option(help="off / deterministic（默认，不调模型）/ model（加 Verifier 模型）")] = (
        "deterministic"
    ),
    jsonl: Annotated[
        bool, typer.Option("--jsonl", help="桌面端桥接：stdout 逐行输出 tw-bridge/1，stdin 收审批 / 取消")
    ] = False,
    demo: Annotated[
        bool, typer.Option("--demo", hidden=True, help="（仅开发 / 测试）脚本化模型 + 演示仓库；正式版不含")
    ] = False,
    parent_run: Annotated[
        str | None, typer.Option(help="--jsonl 多轮对话：上一轮的 run_id（沿 turn.json 链取历史）")
    ] = None,
    resume: Annotated[
        str | None, typer.Option(help="--jsonl 断点续跑：从这个已停止 / 中断的 run_id 的最近进度继续（需 --repo）")
    ] = None,
    model: Annotated[str, typer.Option(help="Executor 模型（只允许 deepseek-flash）")] = "deepseek-flash",
    harness: Annotated[
        str | None,
        typer.Option(help="harness 配置名（configs/harness/<名>.yaml），如 orchestrated-1m = Planner + Reviewer"),
    ] = None,
    thinking: Annotated[
        str | None, typer.Option(help="思考强度 off / low / medium / high（默认按 configs/models.yaml）")
    ] = None,
    max_cost: Annotated[float | None, typer.Option(hidden=True, help="（0.3.2 起已移除 ¥ 上限，忽略）")] = None,
    permission_mode: Annotated[
        str | None,
        typer.Option(help="本次任务的权限模式 plan / ask / auto_review / full_access（旧值自动迁移）"),
    ] = None,
    confirm_unrestricted: Annotated[
        str | None,
        typer.Option(
            "--confirm-full-access",
            "--confirm-unrestricted",
            help="full_access（完全访问模式）的确认短语；只在 --jsonl 交互运行中有效",
        ),
    ] = None,
    attach: Annotated[
        list[Path] | None, typer.Option(help="附件（可多次）：文本内联进任务描述，图片 / 二进制只列文件名")
    ] = None,
    guidance_file: Annotated[
        Path | None, typer.Option(help="用户说明文件（个人偏好 / 风格 / 项目说明，UTF-8），放在任务描述前")
    ] = None,
    no_input: Annotated[
        bool, typer.Option("--no-input", help="终端里也不弹 y/N 确认：需要确认的操作一律拒绝（脚本 / CI 用）")
    ] = False,
    memory: Annotated[
        bool | None,
        typer.Option("--memory/--no-memory", help="读本仓库的记忆（默认：有就读；评测从不读）"),
    ] = None,
    open_pr: Annotated[
        bool,
        typer.Option("--open-pr", help="完成后按风险等级开 PR（L0/L1 确认后开、L2 确认后开 Draft、L3 不开），并盯 CI"),
    ] = False,
    pr_base: Annotated[str | None, typer.Option(help="--open-pr 的目标分支（默认当前分支或 main）")] = None,
    pr_remote: Annotated[str, typer.Option(help="--open-pr 推送的远端")] = "origin",
    watch_ci: Annotated[
        bool | None, typer.Option("--watch-ci/--no-watch-ci", help="开 PR 后是否等 CI 并在失败时返工（默认看 harness）")
    ] = None,
) -> None:
    """修复本地仓库的一个问题，输出 diff、FinishReport 与成本账单（orchestrated-1m 加 Planner + Reviewer）。"""
    import asyncio
    import os
    import sys

    from triwitness.config import tw_home
    from triwitness.core.errors import TriWitnessError
    from triwitness.harness.local_run import run_local

    if backend not in ("auto", "docker", "none"):
        raise typer.BadParameter("只能是 auto / docker / none")
    if verify not in ("off", "deterministic", "model"):
        raise typer.BadParameter("--verify 只能是 off / deterministic / model")
    if repo is not None:
        repo = repo.expanduser()  # 桌面端可能传 ~/...（Windows 下 shell 不展开）
    elif not jsonl:
        raise typer.BadParameter("--repo 不能为空")
    if parent_run is not None:
        from triwitness.harness.chat import valid_run_id

        if not jsonl or not valid_run_id(parent_run):
            raise typer.BadParameter("--parent-run 只能在 --jsonl 下使用，且必须是 run_id")
    if resume is not None:
        from triwitness.harness.chat import valid_run_id

        if not jsonl or not valid_run_id(resume) or repo is None or demo:
            raise typer.BadParameter("--resume 只能在 --jsonl 下使用，需要 --repo，且必须是 run_id")
        issue = issue or "继续"
    from triwitness.llm.router import executor_override

    try:
        override = executor_override(model, thinking)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from None
    budget, session = _run_overrides(max_cost, permission_mode, confirm_unrestricted, interactive=jsonl)
    files, guidance = _run_inputs(attach, guidance_file)
    publish = None
    if open_pr:
        if demo:
            raise typer.BadParameter("--demo 不能开 PR")
        from triwitness.harness.local_run import PublishOptions

        publish = PublishOptions(remote=pr_remote, base=pr_base, watch_ci=watch_ci)
    hcfg = _harness(harness)
    reviewer = None
    if demo:
        try:
            from triwitness.bridge import demo as demo_mod
        except ImportError:  # 正式版（PyInstaller）不打包演示适配器
            raise typer.BadParameter("正式版不含演示模式") from None

        if live:
            raise typer.BadParameter("--demo 与 --live 不能同时用")
        repo = demo_mod.ensure_repo(repo or tw_home() / "demo" / "verses")
        issue = issue.strip() or demo_mod.ISSUE
        backend, test_cmd = "none", test_cmd or demo_mod.test_command()
        delay = float(os.environ.get("TW_DEMO_DELAY_S", "0.9"))
        router = demo_mod.DemoRouter(delay_s=delay, thinking=override.get("thinking", True),
                                     effort=override.get("effort"))  # fmt: skip
        from triwitness.permissions.reviewer import FakeReviewer

        reviewer = FakeReviewer()  # 演示：规则审核，¥0
        if verify == "model":
            verify = "deterministic"  # 演示不调 Verifier 模型
    else:
        from triwitness.llm.router import Router

        if not issue.strip():
            raise typer.BadParameter("--issue 不能为空")
        if repo is None and not jsonl:
            raise typer.BadParameter("--repo 不能为空")
        if live:
            os.environ["TW_LLM_MODE"] = "record"
        elif os.environ.get("TW_LLM_MODE", "replay").strip().lower() != "replay":
            raise typer.BadParameter("TW_LLM_MODE 不是 replay：真实调用请显式加 --live")
        router = Router.deepseek_default(allow_peak=allow_peak, executor=override or None)
        # auto_review：deepseek-flash 非思考审核；失败 / 不确定退回问用户（只在交互运行：--jsonl 或终端 TTY 中才会用到）
        if jsonl or (not no_input and sys.stdin.isatty()):
            from triwitness.permissions.reviewer import ModelReviewer

            reviewer = ModelReviewer(router)
    mode = "demo" if demo else "live" if live else "replay"

    if jsonl:
        from triwitness.bridge.stdio import Bridge, stdin_queue, stdout_writer

        home = tw_home()

        def work(text, approver, on_event, recorder=None, resume_state=None):  # type: ignore[no-untyped-def]
            fresh = resume_state is None  # 续跑：任务描述里已含当时的用户设置 / 附件，不再叠一遍
            return run_local(repo, text, router=router, title=title, backend=backend,  # type: ignore[arg-type]
                             test_command=test_cmd, verify=verify, approver=approver, on_event=on_event,  # type: ignore[arg-type]
                             home=home, budget=budget, session=session, attachments=files if fresh else None,
                             guidance=guidance if fresh else None, reviewer=reviewer, recorder=recorder,
                             resume=resume_state, harness=hcfg, publish=publish, memory=memory)  # fmt: skip

        def start(approver, on_event):  # type: ignore[no-untyped-def]
            if demo:  # 开发 / 测试用的脚本化任务：不走对话轮
                return work(issue, approver, on_event)
            from triwitness.core.ids import new_run_id, new_task_id
            from triwitness.harness.chat import run_turn
            from triwitness.telemetry.trajectory import TrajectoryRecorder

            run_id = new_run_id()
            run_dir = home / "runs" / run_id
            if resume is not None:  # 先校验（不能续跑就直接报错，不建新 run）
                from triwitness.harness.chat import run_resume
                from triwitness.harness.resume import load_resume

                state = load_resume(home, resume)
                rec = TrajectoryRecorder(new_task_id(), run_id, run_dir=run_dir)
                rec.subscribe(on_event)
                return run_resume(state, rec=rec, run_dir=run_dir, repo=repo,  # type: ignore[arg-type]
                                  work=lambda text, r, s: work(text, approver, on_event, r, s))  # fmt: skip
            rec = TrajectoryRecorder(new_task_id(), run_id, run_dir=run_dir)
            rec.subscribe(on_event)
            return run_turn(issue, router=router, rec=rec, run_dir=run_dir, home=home, repo=repo,
                            parent=parent_run, budget=budget,
                            work=lambda text, r: work(text, approver, on_event, r))  # fmt: skip

        async def main() -> int:
            bridge = Bridge(stdout_writer(), mode=mode, home=home)
            return await bridge.run(start, stdin_queue(asyncio.get_running_loop()))

        raise typer.Exit(asyncio.run(main()))

    tty_approver = None
    if not no_input and sys.stdin.isatty():  # spec 010 §11 Q5：交互终端里 y/N 审批；管道 / CI 仍一律拒绝
        from triwitness.cli.tty import make_tty_approver

        tty_approver = make_tty_approver()
    try:
        out = asyncio.run(run_local(repo, issue, router=router, title=title, backend=backend,  # type: ignore[arg-type]
                                    test_command=test_cmd, verify=verify, budget=budget,  # type: ignore[arg-type]
                                    session=session, attachments=files, guidance=guidance,
                                    reviewer=reviewer, harness=hcfg, approver=tty_approver,
                                    publish=publish, memory=memory))  # fmt: skip
    except TriWitnessError as e:
        typer.echo(f"未完成：{e}", err=True)
        raise typer.Exit(2) from None
    r = out.result
    typer.echo(f"状态 {r.status}｜后端 {out.backend}｜{r.outcome.steps} 步｜¥{r.cost.total_cny:.4f}")
    if r.outcome.reason:
        typer.echo(f"原因：{r.outcome.reason}")
    if out.branch:
        typer.echo(f"改动在分支 {out.branch}（工作区未动）")
    if r.verification is not None:
        ev = r.verification.evidence
        typer.echo(
            f"验证 {ev.verdict}｜风险 {ev.risk_level}（{ev.risk_score} 分）｜复现 {ev.repro_status}｜{ev.clean_env}"
        )
    if r.plan is not None:
        typer.echo(f"计划：风险 {r.plan.estimated_risk}｜{len(r.plan.acceptance_criteria)} 条验收标准（plan.json）")
    if r.review is not None:
        typer.echo(f"评审：{'有阻断问题' if r.review.blocking else '通过'}｜{len(r.review.findings)} 条发现｜"
                   f"返工 {r.review_rounds} 轮｜变体 {r.review.variant}")  # fmt: skip
    if r.pr is not None:
        typer.echo(f"PR：{r.pr.url}{'（Draft）' if r.pr.draft else ''}" + (f"｜{r.ci.display()}" if r.ci else ""))
    typer.echo(f"产物：{out.run_dir}（patch.diff / finish.json / cost.md / trajectory.jsonl / evidence.json / pr.md）")


def _harness(name: str | None):  # type: ignore[no-untyped-def]
    """--harness：configs/harness/<名>.yaml；不给 = 默认（long-context-1m）。"""
    if name is None:
        return None
    from triwitness.core.errors import ConfigError
    from triwitness.harness.config import HarnessConfig

    stem = name.removesuffix(".yaml").rsplit("/", 1)[-1]
    try:
        return HarnessConfig.load(f"harness/{stem}.yaml")
    except (ConfigError, FileNotFoundError, OSError) as e:
        raise typer.BadParameter(f"harness 配置 {stem} 读取失败：{e}") from None


@app.command("tasks")
def tasks_cmd(
    limit: Annotated[int, typer.Option(help="最多列出多少个")] = 20,
    as_json: Annotated[bool, typer.Option("--json", help="输出 JSON")] = False,
) -> None:
    """列出本机任务库（TW_HOME/tw.db）里的任务与最新状态（W4-15；时间为北京时间）。"""
    import json

    from triwitness.config import tw_home
    from triwitness.store.sqlite import TaskStore

    path = tw_home() / "tw.db"
    if not path.exists():
        typer.echo("[]" if as_json else "还没有任务记录")
        return
    with TaskStore(path) as store:
        rows = store.list_tasks(limit)
    if as_json:
        typer.echo(json.dumps([r.to_dict() for r in rows], ensure_ascii=False))
        return
    from datetime import datetime

    from triwitness.llm.pricing import to_shanghai

    for r in rows:
        cost = f"¥{r.cost_cny:.4f}" if r.cost_cny is not None else "—"
        when = f"{to_shanghai(datetime.fromisoformat(r.updated_at)):%m-%d %H:%M}"  # 库里存 UTC，展示北京时间
        typer.echo(f"{when}  {r.task_id}  {r.state:<18} {r.status or '':<12} {cost:>9}  "
                   f"{r.harness or ''}  {(r.title or '')[:40]}")  # fmt: skip


def _run_inputs(attach: list[Path] | None, guidance_file: Path | None) -> "tuple[list[Path], str | None]":
    from triwitness.harness.inputs import MAX_FILES

    files = [p.expanduser() for p in attach or []]
    if len(files) > MAX_FILES:
        raise typer.BadParameter(f"--attach 最多 {MAX_FILES} 个")
    for p in files:
        if not p.is_file():
            raise typer.BadParameter(f"附件不存在：{p}")
    guidance = None
    if guidance_file is not None:
        g = guidance_file.expanduser()
        if not g.is_file():
            raise typer.BadParameter(f"说明文件不存在：{g}")
        guidance = g.read_text(encoding="utf-8")
    return files, guidance


def _run_overrides(
    max_cost: float | None, permission_mode: str | None, confirm: str | None, *, interactive: bool
) -> "tuple[Budget | None, SessionOverrides | None]":
    """桌面端设置 → 本次任务：权限模式走 session 层，勇士模式需要确认短语且只在交互运行中。"""
    from triwitness.core.errors import ConfigError
    from triwitness.permissions.config import MODES, SessionOverrides, UnrestrictedActivation, normalize_mode

    budget = None  # 0.3.2：不再有单任务 ¥ 上限（--max-cost 只为兼容旧桌面端，忽略）
    del max_cost
    session = None
    if permission_mode is not None:
        try:
            permission_mode = normalize_mode(permission_mode)
        except ConfigError:
            raise typer.BadParameter(f"--permission-mode 只能是 {' / '.join(MODES)}") from None
        act = None
        if permission_mode == "full_access":
            if not interactive or confirm is None:
                raise typer.BadParameter("full_access 只能在桌面端交互运行（--jsonl）中、带确认短语开启")
            act = UnrestrictedActivation(acknowledged=True, typed=confirm, scope="task")
        session = SessionOverrides(mode=permission_mode, unrestricted=act)  # type: ignore[arg-type]
    elif confirm is not None:
        raise typer.BadParameter("--confirm-full-access 需与 --permission-mode full_access 一起用")
    return budget, session


DEFAULT_RESULTS_DIR = Path("evals/results")
eval_app = typer.Typer(add_completion=False, no_args_is_help=True, help="评测")
app.add_typer(eval_app, name="eval")


@eval_app.command("estimate-verifier")
def eval_estimate_verifier(
    results: Annotated[list[Path] | None, typer.Option(help="W2 结果目录（复用其中的 patch.diff）；可多次")] = None,
    suite: Annotated[list[str] | None, typer.Option(help="没有结果时按套件参考解估算；可多次")] = None,
    repeats: int = typer.Option(1, help="model 档每个 attempt 判几次（测稳定性）"),
    output_tokens: int = typer.Option(2500, help="每次 Verifier 输出 token（思考档）"),
    peak: bool = typer.Option(False, "--peak", help="按高峰价估算"),
) -> None:
    """W3-14：verifier 三档（none / deterministic / model）只重跑验证阶段的花费预估。不调用 API。"""
    from triwitness.eval.suites import load_suite
    from triwitness.eval.verify_estimate import estimate, render, sizes_from_results, sizes_from_suite

    sizes = [s for r in results or [] for s in sizes_from_results(r)]
    if not sizes:
        names = suite or ["test", "dev"]
        sizes = sizes_from_suite([t.id for n in names for t in load_suite(n).tasks])
    typer.echo(render(estimate(sizes * repeats, output_tokens=output_tokens, peak=peak)))


@eval_app.command("estimate")
def eval_estimate(
    tasks: int = typer.Option(10, help="任务数"),
    configs: int = typer.Option(1, help="配置数"),
    attempts: int = typer.Option(1, help="每配置尝试次数"),
    avg_input: int | None = typer.Option(None, help="每任务平均输入 token（含缓存命中）；默认取历史，否则 W1 先验"),
    avg_output: int | None = typer.Option(None, help="每任务平均输出 token；默认同上"),
    hit_rate: float | None = typer.Option(None, help="缓存命中率；默认取历史实测，没有历史用 0.9"),
    results: Annotated[Path, typer.Option(help="历史结果目录（读 live 的 result.json）")] = DEFAULT_RESULTS_DIR,
    history: bool = typer.Option(True, "--history/--no-history", help="用历史平均用量与实测命中率"),
) -> None:
    """估算一次评测的花费（空闲价 / 高峰价），并显示当前闸门状态。不调用 API。"""
    from datetime import UTC, datetime

    from triwitness.eval.runner import DEFAULT_AVG_INPUT, DEFAULT_AVG_OUTPUT, historical_usage
    from triwitness.llm.gate import estimate_run
    from triwitness.llm.pricing import is_peak, next_off_peak, to_shanghai

    h = historical_usage(results) if history else None
    if h:
        typer.echo(
            f"历史：{h.n} 次 live 任务，平均输入 {h.avg_input_tokens:,} / 输出 {h.avg_output_tokens:,}，"
            f"命中率 {h.cache_hit_rate:.0%}，实际 ¥{h.avg_cost_cny:.4f}/任务"
        )
    else:
        why = "没有历史 live 结果" if history else "未用历史（--no-history）"
        typer.echo(f"{why}：用 W1 先验（输入 800K / 输出 20K / 命中 90%），显式参数优先")
    avg_input = avg_input or (h.avg_input_tokens if h else DEFAULT_AVG_INPUT)
    avg_output = avg_output or (h.avg_output_tokens if h else DEFAULT_AVG_OUTPUT)
    hit_rate = hit_rate if hit_rate is not None else (h.cache_hit_rate if h else 0.9)

    e = estimate_run(
        tasks=tasks,
        configs=configs,
        attempts=attempts,
        avg_input_tokens=avg_input,
        avg_output_tokens=avg_output,
        cache_hit_rate=hit_rate,
    )
    now = datetime.now(UTC)
    typer.echo(f"任务运行数 {e.calls_tasks}｜输入 {e.input_tokens:,}｜输出 {e.output_tokens:,}｜命中率 {hit_rate:.0%}")
    typer.echo(f"空闲价 ¥{e.off_peak_cny:.4f}｜高峰价 ¥{e.peak_cny:.4f}")
    if is_peak(now):
        typer.echo(f"现在（{to_shanghai(now):%m-%d %H:%M}）是高峰：默认拒绝启动，下一个空闲 {next_off_peak(now):%H:%M}")
    else:
        typer.echo(f"现在（{to_shanghai(now):%m-%d %H:%M}）是空闲时段")


@eval_app.command("run")
def eval_run(
    suite: Annotated[str, typer.Option(help="evals/suites/<suite>.yaml（dev / test / dev-smoke / ext …）")] = "dev",
    allow_test: Annotated[bool, typer.Option("--allow-test", help="test 集只用于出报告，跑它必须显式确认")] = False,
    config: Annotated[list[Path] | None, typer.Option(help="RunConfig YAML（llm Agent），可多次")] = None,
    agent: Annotated[list[str] | None, typer.Option(help="免费假 Agent：null / oracle / tamper，可多次")] = None,
    attempts: Annotated[int | None, typer.Option(help="覆盖配置里的 attempts")] = None,
    concurrency: Annotated[int, typer.Option(help="并发 attempt 数")] = 4,
    limit: Annotated[int | None, typer.Option(help="只跑前 N 个任务")] = None,
    task: Annotated[list[str] | None, typer.Option(help="只跑这些任务（id 或通配，如 swe-*），可多次")] = None,
    out: Annotated[Path | None, typer.Option(help="结果目录；指定已有目录即续跑")] = None,
    live: Annotated[bool, typer.Option("--live", help="真实调用模型（录制到回放缓存）；默认只回放、不联网")] = False,
    allow_peak: Annotated[bool, typer.Option("--allow-peak", hidden=True, help="（已移除，忽略）")] = False,
    max_total_cny: Annotated[float, typer.Option(hidden=True, help="（0.3.2 起不再按金额拒绝，忽略）")] = 50.0,
) -> None:
    """跑评测：任务 × 配置 × 尝试 → Grader 判分 → report.md。默认离线（回放 / 假 Agent）。"""
    import asyncio
    import os

    from triwitness.core.errors import TriWitnessError
    from triwitness.eval.agents import LLMAgent
    from triwitness.eval.grade import Grader
    from triwitness.eval.report import render_markdown, write_report
    from triwitness.eval.runner import DEFAULT_RESULTS, EvalRunner, RunConfig, run_stamp
    from triwitness.eval.task import load_task
    from triwitness.harness.config import HarnessConfig
    from triwitness.llm.gate import PeakGate

    configs = [RunConfig.load(p) for p in config or []]
    for a in agent or []:
        if a not in ("null", "oracle", "tamper"):
            raise typer.BadParameter("--agent 只能是 null / oracle / tamper（llm 用 --config）")
        configs.append(RunConfig.fake(a))  # type: ignore[arg-type]
    if not configs:
        raise typer.BadParameter("至少给一个 --config 或 --agent")
    import fnmatch

    from triwitness.eval.suites import REPORT_ONLY, suite_dirs

    if suite in REPORT_ONLY and not allow_test:
        raise typer.BadParameter(f"{suite} 集只用于出报告（不要拿来调参）；确认要跑请加 --allow-test")
    tasks = [load_task(d) for d in suite_dirs(suite)]
    if task:
        tasks = [t for t in tasks if any(fnmatch.fnmatchcase(t.id, pat) for pat in task)]
    if not tasks:
        raise typer.BadParameter(f"套件 {suite} 没有匹配的任务")
    if live:
        os.environ["TW_LLM_MODE"] = "live"  # 每次都真调（尝试之间互不回放），同时写入回放缓存，之后可离线复现

    def llm_factory(cfg: RunConfig) -> LLMAgent:
        from triwitness.llm.router import Router

        harness = HarnessConfig.load(cfg.harness.removeprefix("configs/")) if cfg.harness else None
        return LLMAgent(lambda: Router.deepseek_default(allow_peak=allow_peak, executor=cfg.executor), harness=harness,
                        category=cfg.category, config_hash=cfg.name)  # fmt: skip

    ledger = None
    if live:
        from triwitness.cost.ledger import GlobalLedger

        ledger = GlobalLedger()
    from datetime import UTC, datetime

    out_dir = out or DEFAULT_RESULTS / run_stamp(datetime.now(UTC))
    runner = EvalRunner(grader=Grader(), llm_agent_factory=llm_factory, live=live,
                        gate=PeakGate(allow_peak=allow_peak), ledger=ledger, max_total_cny=max_total_cny)  # fmt: skip
    try:
        summary = asyncio.run(runner.run(tasks, configs, attempts=attempts, concurrency=concurrency, limit=limit,
                                         out_dir=out_dir))  # fmt: skip
    except KeyboardInterrupt:
        typer.echo(f"已中断。续跑：tw eval run ... --out {out_dir}")
        raise typer.Exit(130) from None
    except TriWitnessError as e:  # 高峰闸门 / 预估超限 / 预算预检 / 模式不符：什么都没运行
        typer.echo(f"未开始：{e}", err=True)
        raise typer.Exit(2) from None
    rep = write_report(summary.out_dir)
    typer.echo(render_markdown(rep))
    extra = []
    if summary.skipped_existing:
        extra.append(f"跳过已完成 {summary.skipped_existing}")
    if summary.deferred_peak:
        extra.append(f"高峰暂停 {summary.deferred_peak}（空闲后续跑）")
    if summary.infra_errors:
        extra.append(f"基础设施错误 {len(summary.infra_errors)}（见 errors.json）")
    if summary.estimate_cny:
        extra.append(f"预估 ¥{summary.estimate_cny:.2f}")
    typer.echo(f"结果：{summary.out_dir}" + (f"｜{'｜'.join(extra)}" if extra else ""))


@eval_app.command("reverify")
def eval_reverify(
    results: Annotated[Path, typer.Option(help="已保存的评测结果目录（如 W2 基线），只读")],
    out: Annotated[Path | None, typer.Option(help="输出目录（默认 <results>-reverify）；同目录再跑即续跑")] = None,
    mode: Annotated[list[str] | None, typer.Option(help="none / deterministic / model，可多次；默认三档")] = None,
    config: Annotated[list[str] | None, typer.Option(help="只验证这些原配置，可多次")] = None,
    live: bool = typer.Option(False, "--live", help="model 档真实调用 Verifier（受预估上限约束）"),
    allow_peak: bool = typer.Option(False, "--allow-peak", hidden=True, help="（0.3.2 起已移除高峰闸门，忽略）"),
    max_total_cny: float = typer.Option(
        3.0, help="model 档：保守预估超过此值则不开始；运行中累计花费逼近此值就停止派发（硬上限）"
    ),
    model_repeats: int = typer.Option(1, help="model 档每个补丁独立判几次（测稳定性；多数票，并列取保守）"),
    model_policy: str = typer.Option(
        "thin_pass", help="model 档何时调用模型：thin_pass（默认，只在确定性 pass 且证据薄时）/ always（W3-14 对比）"
    ),
    reuse_deterministic: bool = typer.Option(
        True,
        "--reuse-deterministic/--no-reuse-deterministic",
        help="model 档复用同一输出目录里 deterministic 档的复跑证据（不再重跑沙箱）",
    ),
    regression: bool = typer.Option(True, "--regression/--no-regression", help="是否跑回归对比"),
    concurrency: int = typer.Option(2, help="并发沙箱数"),
    limit: int | None = typer.Option(None, help="只取前 N 个 attempt"),
) -> None:
    """只重跑验证阶段（复用已保存的 diff / FinishReport，不重跑 Executor、不重新判分），出三档对比报告。"""
    import asyncio
    import os

    from triwitness.core.errors import TriWitnessError
    from triwitness.eval.grade import Grader
    from triwitness.eval.report import render_markdown, write_report
    from triwitness.eval.reverify import MODES, load_saved, reverify
    from triwitness.eval.suites import discover_all
    from triwitness.eval.task import load_task
    from triwitness.llm.gate import PeakGate

    modes = tuple(mode or MODES)
    if model_policy not in ("thin_pass", "always"):
        raise typer.BadParameter("--model-policy 只能是 thin_pass / always")
    if any(m not in MODES for m in modes):
        raise typer.BadParameter("--mode 只能是 none / deterministic / model")
    if live:
        os.environ["TW_LLM_MODE"] = "live"
    elif "model" in modes and os.environ.get("TW_LLM_MODE", "replay").strip().lower() != "replay":
        raise typer.BadParameter("TW_LLM_MODE 不是 replay：真实调用请显式加 --live")
    wanted = {s.result.task_id for s in load_saved(results)}
    tasks = {}
    for d in discover_all():
        if d.name in wanted:
            t = load_task(d)
            tasks[t.id] = t

    def router():  # type: ignore[no-untyped-def]
        from triwitness.llm.router import Router

        return Router.deepseek_default(allow_peak=allow_peak)

    dest = out or results.with_name(results.name + "-reverify")
    try:
        s = asyncio.run(reverify(results, dest, tasks=tasks, grader=Grader(), modes=modes,  # type: ignore[arg-type]
                                 router_factory=router, regression=regression, live=live,
                                 gate=PeakGate(allow_peak=allow_peak), max_total_cny=max_total_cny,
                                 concurrency=concurrency, limit=limit, configs=config,
                                 model_repeats=model_repeats, reuse_deterministic=reuse_deterministic,
                                 model_policy=model_policy))  # type: ignore[arg-type]  # fmt: skip
    except TriWitnessError as e:
        typer.echo(f"未开始：{e}", err=True)
        raise typer.Exit(2) from None
    typer.echo(render_markdown(write_report(dest)))
    typer.echo(f"结果：{dest}｜新完成 {s.done}｜跳过 {s.skipped_existing}｜验证错误 {len(s.errors)}"
               f"｜缺任务 {len(s.missing_task)}｜Verifier ¥{s.verifier_cost_cny:.4f}"
               f"｜复用确定性证据 {s.reused_deterministic}｜因上限未派发 {len(s.capped)}")  # fmt: skip


@eval_app.command("report")
def eval_report(run_dir: Annotated[Path, typer.Argument(help="evals/results/<时间戳>")]) -> None:
    """从 result.json 重新生成 report.json / report.md。"""
    from triwitness.eval.report import render_markdown, write_report

    typer.echo(render_markdown(write_report(run_dir)))


budget_app = typer.Typer(add_completion=False, help="用量看板（本地账本，只统计不限制）")
app.add_typer(budget_app, name="usage")
app.add_typer(budget_app, name="budget", hidden=True)  # 0.3.2 前的名字，旧桌面端 / 脚本仍可用


@budget_app.callback(invoke_without_command=True)
def budget_show(
    ctx: typer.Context,
    md: Annotated[bool, typer.Option("--md", help="输出 Markdown")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="输出 JSON（桌面端用量页用）")] = False,
) -> None:
    """已花（按类别 / 周 / 模型）、调用数、缓存命中率。只读本地账本，不联网，不做任何限制。"""
    if ctx.invoked_subcommand is not None:
        return
    from triwitness.cost.dashboard import render_usage_markdown, usage_json, usage_view
    from triwitness.cost.ledger import GlobalLedger

    led = GlobalLedger()
    if as_json:
        import json

        typer.echo(json.dumps(usage_json(usage_view(led), led), ensure_ascii=False))
        return
    text = render_usage_markdown(usage_view(led))
    typer.echo(text if md else text.replace("**", ""))


@budget_app.command("sync")
def budget_sync() -> None:
    """调 DeepSeek /user/balance 与本地账本对账（不调模型、不花钱；key 只放请求头，不打印）。"""
    import asyncio
    from datetime import UTC, datetime

    from triwitness.cost.dashboard import fetch_balance, parse_balance, reconcile
    from triwitness.cost.ledger import GlobalLedger

    led = GlobalLedger()
    b = parse_balance(asyncio.run(fetch_balance()), led.spent())
    typer.echo(f"DeepSeek 余额 {b.currency} {b.total_balance:.2f}（赠送 {b.granted:.2f}｜充值 {b.topped_up:.2f}）")
    typer.echo(f"本地账本累计已花 ¥{b.ledger_spent:.4f}")
    typer.echo(reconcile(led.path.parent / "balance_snapshots.jsonl", b, datetime.now(UTC)))


from triwitness.cli.memory import memory_app  # noqa: E402

app.add_typer(memory_app, name="memory")

sandbox_app = typer.Typer(add_completion=False, no_args_is_help=True, help="沙箱")
app.add_typer(sandbox_app, name="sandbox")


@sandbox_app.command("install")
def sandbox_install(
    target: Annotated[str, typer.Argument(help="docker / wsl")],
    plan: Annotated[bool, typer.Option("--plan", help="只输出安装计划（JSON），不执行")] = False,
    yes: Annotated[bool, typer.Option("--yes", help="用户已确认：执行安装（会弹出 UAC 提权）")] = False,
) -> None:
    """UI-19：Windows 上一键安装 Docker Desktop（winget）或 WSL2（wsl --install）。必须 --yes 才执行。"""
    import json

    from triwitness.sandbox.doctor import detect, install_plan, run_install

    if target not in ("docker", "wsl"):
        raise typer.BadParameter("只能是 docker / wsl")
    p = install_plan(target, report=detect())  # type: ignore[arg-type]
    if plan or not yes:
        typer.echo(json.dumps(p.to_dict(), ensure_ascii=False))
        if not plan:
            typer.echo("未执行：需要用户确认后加 --yes", err=True)
            raise typer.Exit(2)
        return
    if not p.supported:
        typer.echo(json.dumps({"ok": False, "error": p.note, "plan": p.to_dict()}, ensure_ascii=False))
        raise typer.Exit(2)
    rc, tail = run_install(p)
    after = detect()
    typer.echo(json.dumps({"ok": rc == 0, "exit_code": rc, "output": tail, "plan": p.to_dict(),
                           "after": after.to_dict()}, ensure_ascii=False))  # fmt: skip
    raise typer.Exit(0 if rc == 0 else 1)


pr_app = typer.Typer(add_completion=False, no_args_is_help=True, help="GitHub PR（审批后推送分支并开 PR）")
app.add_typer(pr_app, name="pr")
_RunOpt = Annotated[str, typer.Option("--run", help="运行 id（r_…）")]
_PrRepoOpt = Annotated[Path | None, typer.Option("--repo", help="本地仓库路径（默认取任务记录的仓库）")]


@pr_app.command("plan")
def pr_plan(
    run: _RunOpt,
    repo: _PrRepoOpt = None,
    base: Annotated[str | None, typer.Option(help="目标分支（默认：仓库当前分支，否则 main）")] = None,
    remote: Annotated[str, typer.Option(help="远端名")] = "origin",
    as_json: Annotated[bool, typer.Option("--json", help="输出 JSON（审批卡用）")] = True,
) -> None:
    """不联网、不推送：列出将要推送的仓库 / 分支 / 目标分支 / 标题 / 改动文件和鉴权方式（审批卡内容）。"""
    from triwitness.config import tw_home
    from triwitness.github.pr import plan_pr

    del as_json
    _perm_call(lambda: {k: v for k, v in plan_pr(tw_home(), run, repo, remote=remote, base=base).card().items()
                        if k != "ok"})  # fmt: skip


@pr_app.command("open")
def pr_open(
    run: _RunOpt,
    repo: _PrRepoOpt = None,
    yes: Annotated[bool, typer.Option("--yes", help="用户已在审批卡上确认：推送分支并开 PR")] = False,
    base: Annotated[str | None, typer.Option(help="目标分支")] = None,
    title: Annotated[str | None, typer.Option(help="PR 标题（默认取结论摘要）")] = None,
    remote: Annotated[str, typer.Option(help="远端名")] = "origin",
    draft: Annotated[bool, typer.Option("--draft", help="开成草稿 PR")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="输出 JSON")] = True,
) -> None:
    """推送 tw/<run_id> 并开 PR。必须 --yes（审批后）；令牌从环境变量 GITHUB_TOKEN 读，否则用已登录的 gh。"""
    from triwitness.config import tw_home
    from triwitness.github.pr import open_pr, plan_pr, record_pr

    del as_json
    if not yes:
        typer.echo('{"ok": false, "error": "未执行：需要用户在审批卡上确认后加 --yes"}')
        raise typer.Exit(2)

    def go() -> dict[str, object]:
        from triwitness.store.idempotency import SideEffectLog, side_effect_key

        home = tw_home()
        plan = plan_pr(home, run, repo, remote=remote, base=base, title=title)

        def do() -> dict[str, object]:
            res = open_pr(plan, draft=draft)
            record_pr(home, plan, res)
            return {"url": res.url, "number": res.number, "created": res.created}

        def find() -> dict[str, object] | None:  # 上次推送 / 开 PR 做到一半：先看本地记录（open_pr 自己也会先查远端）
            return {"url": plan.existing_url, "number": None, "created": False} if plan.existing_url else None

        # 幂等键（spec 011 §4）：同一个运行只开一次 PR；重试 / 连点不会重复推送、重复开
        with SideEffectLog(home / "tw.db") as log_:
            out = log_.run(side_effect_key(run, "open_pr"), do, find=find)  # type: ignore[arg-type]
        r = out.result
        return {"url": r.get("url"), "number": r.get("number"), "created": bool(r.get("created")) and not out.reused,
                "reused": out.reused, "repo": plan.full_name, "head": plan.head, "base": plan.base,
                "title": plan.title}  # fmt: skip

    _perm_call(go)


diag_app = typer.Typer(add_completion=False, no_args_is_help=True, help="诊断包（日志 + 运行目录，脱敏，只在本机）")
app.add_typer(diag_app, name="diag")


@diag_app.command("export")
def diag_export(
    run: Annotated[list[str] | None, typer.Option("--run", help="运行 id，可重复；默认最近 3 个")] = None,
    recent: Annotated[int, typer.Option(min=0, max=20, help="不指定 --run 时收最近几个运行")] = 3,
    out: Annotated[Path | None, typer.Option(help="zip 路径（默认 $TW_HOME/diagnostics/）")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="输出 JSON")] = True,
) -> None:
    """把 system / 用量 / 日志 / 运行目录打成 zip（密钥脱敏，家目录换成 ~），不联网、不上传。"""
    from triwitness.config import tw_home
    from triwitness.core.errors import ConfigError
    from triwitness.diag.export import export_diagnostics

    del as_json

    def go() -> dict[str, object]:
        try:
            return export_diagnostics(tw_home(), run_ids=run or None, recent=recent, out=out).as_dict()
        except (ValueError, FileNotFoundError) as e:
            raise ConfigError(str(e)) from None

    _perm_call(go)


traj_app = typer.Typer(add_completion=False, no_args_is_help=True, help="轨迹导出（SFT / RLVR / Harbor / HTML）")
app.add_typer(traj_app, name="traj")


@traj_app.command("export")
def traj_export(
    run_dir: Annotated[Path, typer.Argument(help="含 trajectory.jsonl 的运行目录（evals/results/... 或 ~/.triwitness/runs/<id>）")],
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="openai / rlvr / harbor / html / all（默认 all）"),
    ] = "all",
    out: Annotated[Path | None, typer.Option("--out", "-o", help="输出目录（默认 <run_dir>/export）")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="机器可读摘要")] = False,
) -> None:
    """从已有轨迹导出 OpenAI messages / 轨迹+奖励 / Harbor trial / 单文件 HTML（¥0，不调模型）。"""
    from triwitness.core.errors import ConfigError
    from triwitness.eval.traj_export import FORMATS, export_run

    del as_json
    fmts = [f.strip() for f in format.split(",") if f.strip()]
    dest = out or (run_dir / "export")

    def go() -> dict[str, object]:
        try:
            results = export_run(run_dir, dest, formats=fmts)
        except (FileNotFoundError, ValueError) as e:
            raise ConfigError(str(e)) from None
        return {
            "out": str(dest),
            "formats": [{"format": r.format, "path": str(r.path), "bytes": r.bytes} for r in results],
        }

    _perm_call(go)


perm_app = typer.Typer(add_completion=False, no_args_is_help=True, help="权限规则（桌面端规则编辑器）")
app.add_typer(perm_app, name="permissions")
_LayerOpt = Annotated[str, typer.Option(help="user（~/.triwitness/permissions.yaml）/ local（仓库本地）")]
_RepoOpt = Annotated[Path | None, typer.Option(help="仓库路径（local 层需要）")]


def _perm_call(fn):  # type: ignore[no-untyped-def]
    import json

    from triwitness.core.errors import ConfigError

    try:
        out = fn()
    except ConfigError as e:
        typer.echo(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        raise typer.Exit(2) from None
    typer.echo(json.dumps({"ok": True, **out}, ensure_ascii=False))


@perm_app.command("list")
def permissions_list(repo: _RepoOpt = None) -> None:
    """列出用户层（和仓库本地层）规则，JSON。"""
    from triwitness.permissions.user_rules import list_rules

    _perm_call(lambda: {"layers": list_rules(repo=repo.expanduser() if repo else None)})


@perm_app.command("validate")
def permissions_validate(kind: Annotated[str, typer.Option()], rule: Annotated[str, typer.Option()]) -> None:
    """用运行时同一个解析器校验一条规则。"""
    from triwitness.core.errors import ConfigError
    from triwitness.permissions.user_rules import validate

    def go() -> dict[str, object]:
        err = validate(rule, kind)
        if err:
            raise ConfigError(err)
        return {}

    _perm_call(go)


@perm_app.command("add")
def permissions_add(
    kind: Annotated[str, typer.Option()],
    rule: Annotated[str, typer.Option()],
    layer: _LayerOpt = "user",
    repo: _RepoOpt = None,
    replace: Annotated[str | None, typer.Option(help="编辑：先校验新规则，再替换这条旧规则")] = None,
) -> None:
    """添加（或 --replace 编辑）一条规则；写入前校验。"""
    from triwitness.core.errors import ConfigError
    from triwitness.permissions.user_rules import add_rule, remove_rule, validate

    def go() -> dict[str, object]:
        if layer not in ("user", "local"):
            raise ConfigError("--layer 只能是 user / local")
        err = validate(rule, kind)
        if err:
            raise ConfigError(err)
        r = repo.expanduser() if repo else None
        if replace is not None:
            remove_rule(replace, kind, layer=layer, repo=r)  # type: ignore[arg-type]
        return {"path": str(add_rule(rule, kind, layer=layer, repo=r))}  # type: ignore[arg-type]

    _perm_call(go)


@perm_app.command("remove")
def permissions_remove(
    kind: Annotated[str, typer.Option()], rule: Annotated[str, typer.Option()], layer: _LayerOpt = "user",
    repo: _RepoOpt = None,
) -> None:  # fmt: skip
    """删除一条规则。"""
    from triwitness.permissions.user_rules import remove_rule

    _perm_call(lambda: {"removed": remove_rule(rule, kind, layer=layer, repo=repo.expanduser() if repo else None)})  # type: ignore[arg-type]


@sandbox_app.command("gc")
def sandbox_gc(
    backend: str = typer.Option("all", help="all / docker / none"),
) -> None:
    """清理崩溃残留的沙箱：docker 容器（tw.managed=true）与本机 worktree（所属进程已退出）。"""
    import asyncio

    from triwitness.sandbox.pool import gc_all

    if backend not in ("all", "docker", "none"):
        raise typer.BadParameter("只能是 all / docker / none")
    rep = asyncio.run(gc_all(docker=backend in ("all", "docker"), local=backend in ("all", "none")))
    typer.echo(rep.summary())
    for run_id in rep.worktrees:
        typer.echo(f"  - worktree {run_id}")


task_app = typer.Typer(add_completion=False, no_args_is_help=True, help="评测任务")
app.add_typer(task_app, name="task")


@task_app.command("validate")
def task_validate(
    paths: Annotated[list[Path], typer.Argument(help="任务目录（含 task.toml），或包含多个任务的目录")],
    static: Annotated[bool, typer.Option("--static", help="只检查格式，不构建镜像、不跑测试")] = False,
) -> None:
    """检查任务：格式 → 构建镜像 → 原始代码 reward=0 → 应用参考解后 reward=1。"""
    from triwitness.eval.task import TaskFormatError, discover, load_task

    dirs: list[Path] = []
    for p in paths:
        dirs.extend([p] if (p / "task.toml").is_file() else discover(p))
    if not dirs:
        raise typer.BadParameter("没找到 task.toml")
    failed = 0
    for d in dirs:
        try:
            task = load_task(d)
        except TaskFormatError as e:
            failed += 1
            typer.echo(f"✗ {d.name}  {e}")
            continue
        if static:
            typer.echo(f"✓ {task.id}  格式正确")
            continue
        from triwitness.eval.validate import validate_sync

        rep = validate_sync(task)
        if rep.ok:
            cached = "（镜像缓存）" if rep.image_cached else ""
            typer.echo(f"✓ {task.id}  reward 0 → 1  {rep.image}{cached}")
        else:
            failed += 1
            typer.echo(f"✗ {task.id}  " + "；".join(rep.problems))
            bad = rep.with_solution if rep.without_solution.reward == 0 else rep.without_solution
            typer.echo(bad.log_tail)
    if failed:
        raise typer.Exit(1)
