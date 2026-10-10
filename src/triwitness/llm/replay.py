"""录制 / 回放缓存（W1-08）：单测和 CI 花费 ¥0。

模式（环境变量 TW_LLM_MODE，默认 replay）：
- replay：只查缓存；找不到就抛 ReplayMiss，绝不联网。
- record：先查缓存，未命中才真调并写入缓存（受空闲闸门与预算约束）。
- live：直接真调，不读不写缓存。

键 = 规范化请求 JSON 的 sha256（模型、消息、工具 schema、关键参数；不含任何密钥 / 请求头）。
缓存文件：tests/fixtures/llm/<vendor>/*.json（仓库内，命名用例）与 ~/.triwitness/llm-cache/<vendor>/<key>.json。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from triwitness.config import tw_home
from triwitness.core.errors import TriWitnessError

Mode = Literal["replay", "record", "live"]
FIXTURE_FORMAT = "tw-llm-fixture/1"
_SECRET_RE = re.compile(r"sk-[A-Za-z0-9]{16,}|Bearer\s+\S+", re.I)
_SECRET_KEYS = {"authorization", "api_key", "api-key", "x-api-key", "headers"}


class ReplayMiss(TriWitnessError):
    """回放模式下找不到录制响应。"""


class Transport(Protocol):
    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]: ...


def current_mode() -> Mode:
    m = os.environ.get("TW_LLM_MODE", "replay").strip().lower()
    if m not in ("replay", "record", "live"):
        raise ValueError(f"TW_LLM_MODE 只能是 replay / record / live，收到 {m!r}")
    return m  # type: ignore[return-value]


def canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def request_key(vendor: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256(f"{vendor}\n{canonical(payload)}".encode()).hexdigest()


def scrub(obj: Any) -> Any:
    """递归去掉认证相关字段与密钥样式字符串。"""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if k.lower() not in _SECRET_KEYS}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    if isinstance(obj, str):
        out = _SECRET_RE.sub("[REDACTED]", obj)
        key = os.environ.get("DEEPSEEK_API_KEY")
        return out.replace(key, "[REDACTED]") if key else out
    return obj


class ReplayStore:
    def __init__(self, vendor: str, dirs: list[Path], write_dir: Path | None = None) -> None:
        self.vendor = vendor
        self.dirs = dirs
        self.write_dir = write_dir
        self._index: dict[str, Path] | None = None

    @classmethod
    def default(cls, vendor: str) -> ReplayStore:
        repo_fixtures = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "llm" / vendor
        user_cache = tw_home() / "llm-cache" / vendor
        return cls(vendor, [repo_fixtures, user_cache], write_dir=user_cache)

    def _build_index(self) -> dict[str, Path]:
        idx: dict[str, Path] = {}
        for d in self.dirs:
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.json")):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and data.get("format") == FIXTURE_FORMAT:
                    idx.setdefault(data["key"], p)
        return idx

    def get(self, key: str) -> dict[str, Any] | None:
        if self._index is None:
            self._index = self._build_index()
        p = self._index.get(key)
        return json.loads(p.read_text(encoding="utf-8")) if p else None

    def put(self, key: str, payload: dict[str, Any], response: dict[str, Any], *, name: str | None = None) -> Path:
        if self.write_dir is None:
            raise TriWitnessError("ReplayStore 没有可写目录")
        self.write_dir.mkdir(parents=True, exist_ok=True)
        rec = {
            "format": FIXTURE_FORMAT,
            "vendor": self.vendor,
            "key": key,
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "request": scrub(payload),
            "response": scrub(response),
        }
        text = json.dumps(rec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if _SECRET_RE.search(text):
            raise TriWitnessError("录制内容疑似包含密钥，已拒绝写入")
        path = self.write_dir / f"{name or key[:16]}.json"
        path.write_text(text, encoding="utf-8")
        if self._index is not None:
            self._index[key] = path
        return path


class RecordReplayTransport:
    """包在真实传输外面。replay 模式下 inner 永远不会被调用（inner 可以为 None）。"""

    def __init__(self, store: ReplayStore, inner: Transport | None, mode: Mode | None = None) -> None:
        self.store = store
        self.inner = inner
        self.mode: Mode = mode or current_mode()
        self.network_calls = 0
        self.last_source: Literal["live", "replay"] = "replay"
        self.last_key: str | None = None
        self.next_name: str | None = None  # 录制时的文件名（脚本用）

    @property
    def may_hit_network(self) -> bool:
        return self.mode in ("record", "live")

    def lookup(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if self.mode == "live":
            return None
        rec = self.store.get(request_key(self.store.vendor, payload))
        return rec["response"] if rec else None

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        key = request_key(self.store.vendor, payload)
        self.last_key = key
        if self.mode != "live":
            rec = self.store.get(key)
            if rec is not None:
                self.last_source = "replay"
                return rec["response"]
            if self.mode == "replay":
                raise ReplayMiss(
                    f"回放缓存未命中（key={key[:12]}…）。在空闲时段用 TW_LLM_MODE=record 录制，"
                    "或检查请求是否被意外改动（前缀不稳定也会导致缓存与回放双双失效）"
                )
        if self.inner is None:
            raise TriWitnessError("record / live 模式需要真实传输")
        self.network_calls += 1
        resp = await self.inner.post(path, payload)
        self.last_source = "live"
        if self.mode == "record":
            self.store.put(key, payload, resp, name=self.next_name)
            self.next_name = None
        return resp
