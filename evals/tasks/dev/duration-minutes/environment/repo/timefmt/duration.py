import re

_UNITS = {"h": 3600, "m": 1, "s": 1}
_PART = re.compile(r"(\d+)([hms])")


def parse_duration(text: str) -> int:
    """"1h30m15s" -> 秒数。"""
    text = text.strip().lower()
    if not text or _PART.sub("", text):
        raise ValueError(f"bad duration: {text!r}")
    return sum(int(n) * _UNITS[u] for n, u in _PART.findall(text))
