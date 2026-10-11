from typer.testing import CliRunner

import triwitness
from triwitness.cli.main import app


def test_version_string() -> None:
    assert triwitness.__version__ == "0.3.1a1"


def test_cli_version() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "triwitness 0.3.1a1" in result.output
