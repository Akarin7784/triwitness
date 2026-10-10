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
    repo: Annotated[Path, typer.Option(help="本地 git 仓库路径")],
    issue: Annotated[str, typer.Option(help="问题描述（Issue 正文）")],
    title: Annotated[str | None, typer.Option(help="标题（默认取描述第一行）")] = None,
    backend: Annotated[str, typer.Option(help="auto / docker / none")] = "auto",
    test_cmd: Annotated[str | None, typer.Option(help="run_tests 使用的测试命令")] = None,
    live: Annotated[bool, typer.Option("--live", help="真实调用模型（录制到回放缓存）；默认只回放")] = False,
    allow_peak: Annotated[bool, typer.Option("--allow-peak", help="允许高峰时段（2× 价）")] = False,
) -> None:
    """以 Executor 单角色修复本地仓库中的一个问题，输出 diff、FinishReport 与成本账单。"""
    import asyncio
    import os

    from triwitness.core.errors import TriWitnessError
    from triwitness.harness.local_run import run_local
    from triwitness.llm.router import Router

    if backend not in ("auto", "docker", "none"):
        raise typer.BadParameter("只能是 auto / docker / none")
    if live:
        os.environ["TW_LLM_MODE"] = "record"
    elif os.environ.get("TW_LLM_MODE", "replay").strip().lower() != "replay":
        raise typer.BadParameter("TW_LLM_MODE 不是 replay：真实调用请显式加 --live")
    try:
        out = asyncio.run(run_local(repo, issue, router=Router.deepseek_default(allow_peak=allow_peak), title=title,
                                    backend=backend, test_command=test_cmd))  # type: ignore[arg-type]  # fmt: skip
    except TriWitnessError as e:
        typer.echo(f"未完成：{e}", err=True)
        raise typer.Exit(2) from None
    r = out.result
    typer.echo(f"状态 {r.status}｜后端 {out.backend}｜{r.outcome.steps} 步｜¥{r.cost.total_cny:.4f}")
    if r.outcome.reason:
        typer.echo(f"原因：{r.outcome.reason}")
    if out.branch:
        typer.echo(f"改动在分支 {out.branch}（工作区未动）")
    typer.echo(f"产物：{out.run_dir}（patch.diff / finish.json / cost.md / trajectory.jsonl）")


eval_app = typer.Typer(add_completion=False, no_args_is_help=True, help="评测")
app.add_typer(eval_app, name="eval")


@eval_app.command("estimate")
def eval_estimate(
    tasks: int = typer.Option(10, help="任务数"),
    configs: int = typer.Option(1, help="配置数"),
    attempts: int = typer.Option(1, help="每配置尝试次数"),
    avg_input: int = typer.Option(2_000_000, help="每任务平均输入 token（含缓存命中）"),
    avg_output: int = typer.Option(30_000, help="每任务平均输出 token"),
    hit_rate: float = typer.Option(0.9, help="缓存命中率"),
) -> None:
    """估算一次评测的花费（空闲价 / 高峰价），并显示当前闸门状态。不调用 API。"""
    from datetime import UTC, datetime

    from triwitness.llm.gate import estimate_run
    from triwitness.llm.pricing import is_peak, next_off_peak, to_shanghai

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
    suite: Annotated[str, typer.Option(help="evals/tasks/<suite>")] = "dev",
    config: Annotated[list[Path] | None, typer.Option(help="RunConfig YAML（llm Agent），可多次")] = None,
    agent: Annotated[list[str] | None, typer.Option(help="免费假 Agent：null / oracle / tamper，可多次")] = None,
    attempts: Annotated[int | None, typer.Option(help="覆盖配置里的 attempts")] = None,
    concurrency: Annotated[int, typer.Option(help="并发 attempt 数")] = 4,
    limit: Annotated[int | None, typer.Option(help="只跑前 N 个任务")] = None,
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
    from triwitness.eval.task import discover, load_task
    from triwitness.harness.loop import HarnessConfig
    from triwitness.llm.gate import PeakGate

    configs = [RunConfig.load(p) for p in config or []]
    for a in agent or []:
        if a not in ("null", "oracle", "tamper"):
            raise typer.BadParameter("--agent 只能是 null / oracle / tamper（llm 用 --config）")
        configs.append(RunConfig.fake(a))  # type: ignore[arg-type]
    if not configs:
        raise typer.BadParameter("至少给一个 --config 或 --agent")
    tasks = [load_task(d) for d in discover(Path("evals/tasks") / suite)]
    if not tasks:
        raise typer.BadParameter(f"evals/tasks/{suite} 下没有任务")
    if live:
        os.environ["TW_LLM_MODE"] = "record"  # 真调并写入回放缓存，之后可离线复现

    def llm_factory(cfg: RunConfig) -> LLMAgent:
        from triwitness.llm.router import Router

        harness = HarnessConfig.load(cfg.harness.removeprefix("configs/")) if cfg.harness else None
        return LLMAgent(lambda: Router.deepseek_default(allow_peak=allow_peak), harness=harness,
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


@eval_app.command("report")
def eval_report(run_dir: Annotated[Path, typer.Argument(help="evals/results/<时间戳>")]) -> None:
    """从 result.json 重新生成 report.json / report.md。"""
    from triwitness.eval.report import render_markdown, write_report

    typer.echo(render_markdown(write_report(run_dir)))


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
