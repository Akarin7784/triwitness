"""桌面端规则编辑器（UI-21）：增删改用户层 `~/.triwitness/permissions.yaml` 与仓库本地层
`<repo>/.triwitness/permissions.local.yaml`（审批卡“总是允许”写的就是它）的 allow / ask / deny 规则。

每条规则写入前都过 `parse_rule`（与运行时同一个解析器）；其他键（mode、additional_directories…）原样保留。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

import yaml

from triwitness.core.errors import ConfigError
from triwitness.permissions.config import (
    _LIST_KEYS,
    LOCAL_FILE,
    PROJECT_DIR,
    _read_yaml,
    save_local_rules,
    user_policy_path,
)
from triwitness.permissions.rules import Decision, parse_rule

Layer = Literal["user", "local"]


def layer_path(layer: Layer, *, home: Path | None = None, repo: Path | None = None) -> Path:
    if layer == "user":
        return user_policy_path(home)
    if repo is None:
        raise ConfigError("local 层需要 --repo")
    return repo / PROJECT_DIR / LOCAL_FILE


def validate(raw: str, kind: str) -> str | None:
    """返回错误信息；合法返回 None。"""
    if kind not in _LIST_KEYS:
        return f"类型只能是 {' / '.join(_LIST_KEYS)}"
    if not raw.strip() or raw != raw.strip():
        return "规则不能为空，也不能有首尾空格"
    try:
        parse_rule(raw, cast(Decision, kind), "user")
    except ConfigError as e:
        return str(e)
    return None


def list_rules(*, home: Path | None = None, repo: Path | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    layers: list[Layer] = ["user", "local"] if repo is not None else ["user"]
    for layer in layers:
        p = layer_path(layer, home=home, repo=repo)
        data = _read_yaml(p) or {}
        out[layer] = {"path": str(p), **{k: [str(r) for r in data.get(k) or []] for k in _LIST_KEYS}}
    return out


def _write(p: Path, data: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def add_rule(raw: str, kind: str, *, layer: Layer = "user", home: Path | None = None, repo: Path | None = None) -> Path:
    err = validate(raw, kind)
    if err:
        raise ConfigError(err)
    if layer == "local":
        assert repo is not None
        return save_local_rules(repo, [raw], cast(Decision, kind))  # 同时写 .git/info/exclude
    p = layer_path(layer, home=home, repo=repo)
    data = _read_yaml(p) or {}
    items = [str(r) for r in data.get(kind) or []]
    if raw not in items:
        items.append(raw)
    data[kind] = items
    _write(p, data)
    return p


def remove_rule(
    raw: str, kind: str, *, layer: Layer = "user", home: Path | None = None, repo: Path | None = None
) -> bool:
    if kind not in _LIST_KEYS:
        raise ConfigError(f"类型只能是 {' / '.join(_LIST_KEYS)}")
    p = layer_path(layer, home=home, repo=repo)
    data = _read_yaml(p) or {}
    items = [str(r) for r in data.get(kind) or []]
    if raw not in items:
        return False
    items.remove(raw)
    if items:
        data[kind] = items
    else:
        data.pop(kind, None)
    _write(p, data)
    return True
