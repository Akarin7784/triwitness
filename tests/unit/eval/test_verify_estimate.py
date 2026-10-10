"""W3-14 预估：只算 Verifier 模型调用；none / deterministic 为 0。不调用 API。"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from triwitness.cli.main import app
from triwitness.eval.verify_estimate import AttemptSize, estimate, sizes_from_results


def test_estimate_scales_and_caches_prefix() -> None:
    one = estimate([AttemptSize(task_id="a", source="x", body_chars=15_000)], repair_rate=0)
    many = estimate([AttemptSize(task_id="a", source="x", body_chars=15_000)] * 10, repair_rate=0)
    assert one.prefix_tokens > 0 and one.avg_body_tokens == 5000
    # 第 2 次起稳定前缀命中：10 次 < 10 × 单次
    assert one.expected_cny * 9 < many.expected_cny < one.expected_cny * 10
    assert many.high_cny > many.expected_cny
    assert estimate([AttemptSize(task_id="a", source="x", body_chars=15_000)] * 10, repair_rate=0.5).expected_cny > (
        many.expected_cny
    )


def test_sizes_from_results_skips_empty_diffs(tmp_path: Path) -> None:
    for task, diff in (("t1", "diff --git a/x b/x\n+1\n"), ("t2", "")):
        d = tmp_path / "baseline" / task / "1"
        d.mkdir(parents=True)
        (d / "patch.diff").write_text(diff, encoding="utf-8")
    sizes = sizes_from_results(tmp_path, tasks=tmp_path / "none")
    assert [s.task_id for s in sizes] == ["t1"] and sizes[0].source == "w2_patch"


def test_cli_default_suites_under_w3_14_cap() -> None:
    out = CliRunner().invoke(app, ["eval", "estimate-verifier"])
    assert out.exit_code == 0, out.output
    assert "| model | 50 次" in out.output and "reference_solution=50" in out.output
    cny = float(out.output.split("（保守 ¥")[1].split("）")[0])
    assert cny <= 3.0  # W3-14 预算上限 ¥3
