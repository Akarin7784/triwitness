"""ID 生成：ULID（26 位 Crockford Base32，按时间可排序），带类型前缀。"""

import os
import re
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")

PREFIXES = {"task": "t_", "run": "r_", "hitl": "h_"}


def new_ulid(ts_ms: int | None = None, randomness: bytes | None = None) -> str:
    """生成 ULID。`ts_ms` / `randomness` 仅供测试注入。"""
    ms = int(time.time() * 1000) if ts_ms is None else ts_ms
    if not 0 <= ms < 2**48:
        raise ValueError("ULID 时间戳必须在 48 位范围内")
    rnd = os.urandom(10) if randomness is None else randomness
    if len(rnd) != 10:
        raise ValueError("ULID 随机部分必须是 10 字节")
    value = (ms << 80) | int.from_bytes(rnd, "big")
    out = []
    for _ in range(26):
        out.append(_ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(out))


def is_ulid(s: str) -> bool:
    return bool(_ULID_RE.match(s))


def new_task_id() -> str:
    return PREFIXES["task"] + new_ulid()


def new_run_id() -> str:
    return PREFIXES["run"] + new_ulid()


def new_hitl_id() -> str:
    return PREFIXES["hitl"] + new_ulid()
