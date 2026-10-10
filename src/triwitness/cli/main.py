"""`tw` 命令行入口（W1-04 骨架：只有 --version）。"""

import typer

from triwitness import __version__

app = typer.Typer(add_completion=False, no_args_is_help=True, help="TriWitness（三证）")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"triwitness {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="显示版本"
    ),
) -> None:
    """TriWitness 命令行。"""


@app.command()
def doctor() -> None:
    """环境自检（占位；W2-02 实现，只检查不调用 API）。"""
    typer.echo("tw doctor：尚未实现（W2-02）")
