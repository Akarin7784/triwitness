"""`tw` 命令行入口（W1-04 骨架：只有 --version）。"""

from pathlib import Path
from typing import Annotated

import typer

from triwitness import __version__

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
def doctor() -> None:
    """环境自检（占位；W2-02 实现，只检查不调用 API）。"""
    typer.echo("tw doctor：尚未实现（W2-02）")


@app.command("run")
def run_cmd(
    repo: Annotated[Path, typer.Option(help="本地 git 仓库路径（--demo：不存在或为空时写入演示仓库）")],
    issue: Annotated[str, typer.Option(help="问题描述（Issue 正文）；--demo 可省略")] = "",
    title: Annotated[str | None, typer.Option(help="标题（默认取描述第一行）")] = None,
    backend: Annotated[str, typer.Option(help="auto / docker / none")] = "auto",
    test_cmd: Annotated[str | None, typer.Option(help="run_tests 使用的测试命令")] = None,
    live: Annotated[bool, typer.Option("--live", help="真实调用模型（录制到回放缓存）；默认只回放")] = False,
    allow_peak: Annotated[bool, typer.Option("--allow-peak", help="允许高峰时段（2× 价）")] = False,
    verify: Annotated[str, typer.Option(help="off / deterministic（默认，不调模型）/ model（加 Verifier 模型）")] = (
        "deterministic"
    ),
    jsonl: Annotated[
        bool, typer.Option("--jsonl", help="桌面端桥接：stdout 逐行输出 tw-bridge/1，stdin 收审批 / 取消")
    ] = False,
    demo: Annotated[bool, typer.Option("--demo", help="演示适配器：脚本化模型 + 演示仓库，¥0、不联网")] = False,
) -> None:
    """以 Executor 单角色修复本地仓库中的一个问题，输出 diff、FinishReport 与成本账单。"""
    import asyncio
    import os

    from triwitness.config import tw_home
    from triwitness.core.errors import TriWitnessError
    from triwitness.harness.local_run import run_local

    if backend not in ("auto", "docker", "none"):
        raise typer.BadParameter("只能是 auto / docker / none")
    if verify not in ("off", "deterministic", "model"):
        raise typer.BadParameter("--verify 只能是 off / deterministic / model")
    if demo:
        from triwitness.bridge import demo as demo_mod

        if live:
            raise typer.BadParameter("--demo 与 --live 不能同时用")
        repo = demo_mod.ensure_repo(repo)
        issue = issue.strip() or demo_mod.ISSUE
        backend, test_cmd = "none", test_cmd or demo_mod.test_command()
        router = demo_mod.DemoRouter(delay_s=float(os.environ.get("TW_DEMO_DELAY_S", "0.9")))
        if verify == "model":
            verify = "deterministic"  # 演示不调 Verifier 模型
    else:
        from triwitness.llm.router import Router

        if not issue.strip():
            raise typer.BadParameter("--issue 不能为空")
        if live:
            os.environ["TW_LLM_MODE"] = "record"
        elif os.environ.get("TW_LLM_MODE", "replay").strip().lower() != "replay":
            raise typer.BadParameter("TW_LLM_MODE 不是 replay：真实调用请显式加 --live")
        router = Router.deepseek_default(allow_peak=allow_peak)
    mode = "demo" if demo else "live" if live else "replay"

    if jsonl:
        from triwitness.bridge.stdio import Bridge, stdin_queue, stdout_writer

        home = tw_home()

        def start(approver, on_event):  # type: ignore[no-untyped-def]
            return run_local(repo, issue, router=router, title=title, backend=backend,  # type: ignore[arg-type]
                             test_command=test_cmd, verify=verify, approver=approver, on_event=on_event,  # type: ignore[arg-type]
                             home=home)  # fmt: skip

        async def main() -> int:
            bridge = Bridge(stdout_writer(), mode=mode, home=home)
            return await bridge.run(start, stdin_queue(asyncio.get_running_loop()))

        raise typer.Exit(asyncio.run(main()))

    try:
        out = asyncio.run(run_local(repo, issue, router=router, title=title,
                                    backend=backend, test_command=test_cmd, verify=verify))  # type: ignore[arg-type]  # fmt: skip
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
    typer.echo(f"产物：{out.run_dir}（patch.diff / finish.json / cost.md / trajectory.jsonl / evidence.json / pr.md）")


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
    suite: Annotated[str, typer.Option(help="evals/suites/<suite>.yaml（dev / test / dev-smoke）")] = "dev",
    allow_test: Annotated[bool, typer.Option("--allow-test", help="test 集只用于出报告，跑它必须显式确认")] = False,
    config: Annotated[list[Path] | None, typer.Option(help="RunConfig YAML（llm Agent），可多次")] = None,
    agent: Annotated[list[str] | None, typer.Option(help="免费假 Agent：null / oracle / tamper，可多次")] = None,
    attempts: Annotated[int | None, typer.Option(help="覆盖配置里的 attempts")] = None,
    concurrency: Annotated[int, typer.Option(help="并发 attempt 数")] = 4,
    limit: Annotated[int | None, typer.Option(help="只跑前 N 个任务")] = None,
    task: Annotated[list[str] | None, typer.Option(help="只跑这些任务（id 或通配，如 swe-*），可多次")] = None,
    out: Annotated[Path | None, typer.Option(help="结果目录；指定已有目录即续跑")] = None,
    live: Annotated[bool, typer.Option("--live", help="真实调用模型（录制到回放缓存）；默认只回放、不联网")] = False,
    allow_peak: Annotated[bool, typer.Option("--allow-peak", help="允许高峰时段（2× 价，报告标注）")] = False,
    max_total_cny: Annotated[float, typer.Option(help="预估总额上限，超过不开始")] = 50.0,
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
    live: bool = typer.Option(False, "--live", help="model 档真实调用 Verifier（过高峰闸门与预估上限）"),
    allow_peak: bool = typer.Option(False, "--allow-peak", help="允许高峰时段"),
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


budget_app = typer.Typer(add_completion=False, help="预算看板（本地账本）")
app.add_typer(budget_app, name="budget")


@budget_app.callback(invoke_without_command=True)
def budget_show(
    ctx: typer.Context,
    md: Annotated[bool, typer.Option("--md", help="输出 Markdown（每周预算检查用）")] = False,
) -> None:
    """已花 / 信封 / 剩余、燃烧速度与耗尽日期、缓存命中率。只读本地账本，不联网。"""
    if ctx.invoked_subcommand is not None:
        return
    from triwitness.cost.dashboard import budget_view, render_budget_markdown
    from triwitness.cost.ledger import GlobalLedger

    text = render_budget_markdown(budget_view(GlobalLedger()))
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


sandbox_app = typer.Typer(add_completion=False, no_args_is_help=True, help="沙箱")
app.add_typer(sandbox_app, name="sandbox")


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
