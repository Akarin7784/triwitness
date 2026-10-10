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


eval_app = typer.Typer(add_completion=False, no_args_is_help=True, help="评测（W1-31 起完善）")
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
