from datetime import UTC, datetime, timedelta, timezone

import pytest

from triwitness.core.models import Usage
from triwitness.llm.pricing import is_peak, next_off_peak, price_call, pricing_version

BJ = timezone(timedelta(hours=8))
U = Usage(input_tokens=2_000_000, cache_hit_tokens=1_000_000, cache_miss_tokens=1_000_000, output_tokens=1_000_000)


@pytest.mark.parametrize(
    ("when", "peak"),
    [
        (datetime(2026, 10, 14, 10, 0, tzinfo=BJ), True),  # 周三 10:00
        (datetime(2026, 10, 14, 20, 0, tzinfo=BJ), False),  # 周三 20:00
        (datetime(2026, 10, 14, 8, 59, tzinfo=BJ), False),
        (datetime(2026, 10, 14, 9, 0, tzinfo=BJ), True),
        (datetime(2026, 10, 14, 11, 59, tzinfo=BJ), True),
        (datetime(2026, 10, 14, 12, 0, tzinfo=BJ), False),  # 午间空闲
        (datetime(2026, 10, 14, 14, 0, tzinfo=BJ), True),
        (datetime(2026, 10, 14, 18, 0, tzinfo=BJ), False),
        (datetime(2026, 10, 6, 10, 0, tzinfo=BJ), False),  # 国庆假期中的周二
        (datetime(2026, 10, 11, 10, 0, tzinfo=BJ), False),  # 周日
        (datetime(2026, 10, 10, 10, 0, tzinfo=BJ), False),  # 调休上班的周六：官方字面为周末 → 空闲
        (datetime(2026, 10, 14, 2, 0, tzinfo=UTC), True),  # UTC 输入换算为北京时间 10:00
    ],
)
def test_is_peak(when: datetime, peak: bool) -> None:
    assert is_peak(when) is peak


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValueError):
        is_peak(datetime(2026, 10, 14, 10, 0))


def test_ac5_prices_match_pricing_yaml() -> None:
    peak_cost, p = price_call("deepseek", "deepseek-flash", U, datetime(2026, 10, 14, 10, 0, tzinfo=BJ))
    off_cost, o = price_call("deepseek", "deepseek-flash", U, datetime(2026, 10, 14, 20, 0, tzinfo=BJ))
    assert (p, o) == (True, False)
    assert peak_cost == pytest.approx(0.04 + 2.0 + 8.0)
    assert off_cost == pytest.approx(0.02 + 1.0 + 4.0)
    alias_cost, _ = price_call("deepseek", "deepseek-v4.1-flash", U, datetime(2026, 10, 14, 20, 0, tzinfo=BJ))
    assert alias_cost == off_cost


def test_holiday_weekday_is_off_peak_price() -> None:
    cost, peak = price_call("deepseek", "deepseek-flash", U, datetime(2026, 10, 5, 10, 0, tzinfo=BJ))
    assert peak is False and cost == pytest.approx(5.02)


def test_next_off_peak() -> None:
    t = next_off_peak(datetime(2026, 10, 14, 10, 30, tzinfo=BJ))
    assert (t.hour, t.minute) == (12, 0)


def test_pricing_version() -> None:
    assert pricing_version() == "deepseek-2026-10-10"
