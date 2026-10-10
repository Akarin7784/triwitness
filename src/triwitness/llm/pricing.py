"""价格表与高峰判断（spec 001 §6.8、AC5；ADR-0002）。时间一律按 Asia/Shanghai，且可注入。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from triwitness.config import config_dir, load_config
from triwitness.core.errors import ConfigError
from triwitness.core.models import Usage, Vendor

log = logging.getLogger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class Rates:
    cache_hit: float
    cache_miss: float
    output: float


@dataclass(frozen=True)
class HolidayCalendar:
    holidays: frozenset[date]
    adjusted_workdays: frozenset[date]
    covered_years: frozenset[int]


@lru_cache(maxsize=4)
def _calendar(path: str) -> HolidayCalendar:
    from pathlib import Path

    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    hol: set[date] = set()
    for start, end in data.get("holidays", []):
        d, e = date.fromisoformat(start), date.fromisoformat(end)
        while d <= e:
            hol.add(d)
            d += timedelta(days=1)
    adj = {date.fromisoformat(x) for x in data.get("adjusted_workdays", [])}
    return HolidayCalendar(frozenset(hol), frozenset(adj), frozenset(data.get("covered_years", [])))


def holiday_calendar() -> HolidayCalendar:
    cfg = load_config("pricing.yaml")["deepseek"]
    rel = cfg.get("holidays", "configs/cn_holidays.yaml")
    return _calendar(str(config_dir() / rel.split("/")[-1]))


def to_shanghai(at: datetime) -> datetime:
    if at.tzinfo is None:
        raise ValueError("时间必须带时区")
    return at.astimezone(SHANGHAI)


def is_peak(at: datetime) -> bool:
    """DeepSeek 高峰：北京时间周一至周五（不含法定节假日）9:00–12:00、14:00–18:00。"""
    cfg = load_config("pricing.yaml")["deepseek"]
    local = to_shanghai(at)
    day = local.date()
    cal = holiday_calendar()
    if day.year not in cal.covered_years:
        log.warning("节假日表未覆盖 %s 年，只按周一至周五判断", day.year)
    workday = local.weekday() < 5 and day not in cal.holidays
    if cfg.get("adjusted_workdays_are_peak") and day in cal.adjusted_workdays:
        workday = True
    if not workday:
        return False
    t = local.time()
    return any(time.fromisoformat(start) <= t < time.fromisoformat(end) for start, end in cfg["peak_windows"])


def next_off_peak(at: datetime) -> datetime:
    """从 at 起最近的空闲时刻（按分钟步进，最多 3 天）。"""
    t = to_shanghai(at).replace(second=0, microsecond=0)
    for _ in range(3 * 24 * 60):
        if not is_peak(t):
            return t
        t += timedelta(minutes=1)
    return t


def pricing_version() -> str:
    return f"deepseek-{load_config('pricing.yaml').get('verified_at', 'unknown')}"


def rates(vendor: Vendor, model: str, *, peak: bool) -> Rates:
    if vendor != "deepseek":
        raise ConfigError(f"v0.1 只有 deepseek 价格（收到 {vendor}）")
    models = load_config("pricing.yaml")["deepseek"]["models"]
    entry = None
    for name, m in models.items():
        if model == name or model in m.get("aliases", []):
            entry = m
            break
    if entry is None:
        raise ConfigError(f"pricing.yaml 中没有模型 {model}")
    r = entry["peak" if peak else "off_peak"]
    return Rates(float(r["cache_hit"]), float(r["cache_miss"]), float(r["output"]))


def price_call(vendor: Vendor, model: str, usage: Usage, at: datetime) -> tuple[float, bool | None]:
    """返回 (人民币费用, 是否高峰)。费用 = 命中×单价 + 未命中×单价 + 输出×单价（元 / 百万 token）。"""
    peak = is_peak(at) if vendor == "deepseek" else None
    r = rates(vendor, model, peak=bool(peak))
    cost = (
        usage.cache_hit_tokens * r.cache_hit + usage.cache_miss_tokens * r.cache_miss + usage.output_tokens * r.output
    ) / 1_000_000
    return round(cost, 8), peak


def estimate_cost(vendor: Vendor, model: str, *, input_tokens: int, max_output_tokens: int, at: datetime) -> float:
    """调用前的保守估算：输入全按未命中、输出按上限。"""
    r = rates(vendor, model, peak=is_peak(at))
    return (input_tokens * r.cache_miss + max_output_tokens * r.output) / 1_000_000
