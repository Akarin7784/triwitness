from datetime import datetime, timedelta, timezone

import pytest
from typer.testing import CliRunner

from triwitness.cli.main import app
from triwitness.core.errors import PeakHourBlocked
from triwitness.llm.gate import PeakGate, estimate_run

BJ = timezone(timedelta(hours=8))
WED_10 = datetime(2026, 10, 14, 10, 0, tzinfo=BJ)
WED_20 = datetime(2026, 10, 14, 20, 0, tzinfo=BJ)
HOLIDAY_WEEKDAY = datetime(2026, 10, 6, 10, 0, tzinfo=BJ)


def test_start_refused_in_peak() -> None:
    with pytest.raises(PeakHourBlocked, match="--allow-peak"):
        PeakGate(now=lambda: WED_10).check_start("eval")


@pytest.mark.parametrize("t", [WED_20, HOLIDAY_WEEKDAY])
def test_start_allowed_off_peak(t: datetime) -> None:
    g = PeakGate(now=lambda: t)
    g.check_start()
    assert g.report_flag is None


def test_allow_peak_is_flagged_for_report() -> None:
    g = PeakGate(allow_peak=True, now=lambda: WED_10)
    g.check_start()
    assert g.report_flag and "高峰" in g.report_flag and g.may_dispatch()


def test_stop_dispatching_when_run_crosses_into_peak() -> None:
    clock = [datetime(2026, 10, 14, 8, 50, tzinfo=BJ)]
    g = PeakGate(now=lambda: clock[0])
    g.check_start()
    assert g.may_dispatch()
    clock[0] = datetime(2026, 10, 14, 9, 1, tzinfo=BJ)
    assert not g.may_dispatch()
    clock[0] = datetime(2026, 10, 14, 12, 0, tzinfo=BJ)
    assert g.may_dispatch()


def test_estimate_peak_is_double() -> None:
    e = estimate_run(tasks=10, avg_input_tokens=1_000_000, avg_output_tokens=10_000, cache_hit_rate=0.9)
    # 空闲：命中 9M×0.02 + 未命中 1M×1 + 输出 0.1M×4 = 0.18 + 1 + 0.4
    assert e.off_peak_cny == pytest.approx(1.58)
    assert e.peak_cny == pytest.approx(3.16)
    assert e.calls_tasks == 10


def test_cli_eval_estimate() -> None:
    r = CliRunner().invoke(
        app, ["eval", "estimate", "--tasks", "10", "--avg-input", "1000000", "--avg-output", "10000"]
    )
    assert r.exit_code == 0, r.output
    assert "空闲价 ¥1.5800" in r.output and "高峰价 ¥3.1600" in r.output
