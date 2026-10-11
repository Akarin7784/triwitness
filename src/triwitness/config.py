"""读取 configs/*.yaml。仓库根目录可用 TW_CONFIG_DIR 覆盖（测试注入用）。"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from triwitness.core.errors import ConfigError


def resource_root() -> Path:
    """只读资源根（含 configs/）：源码运行时是仓库根；PyInstaller 打包（桌面内置核心）时是解包目录 `_internal/`。"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # src/triwitness/config.py → 仓库根
    return Path(__file__).resolve().parents[2]


def config_dir() -> Path:
    env = os.environ.get("TW_CONFIG_DIR")
    if env:
        return Path(env)
    return resource_root() / "configs"


def tw_home() -> Path:
    """用户数据目录：账本、llm 缓存、run 轨迹。默认 ~/.triwitness，TW_HOME 可配。"""
    return Path(os.environ.get("TW_HOME") or Path.home() / ".triwitness")


@lru_cache(maxsize=32)
def _load(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"缺少配置文件：{p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"配置文件必须是映射：{p}")
    return data


def load_config(name: str) -> dict[str, Any]:
    """按文件名读取 configs/ 下的 YAML（带缓存）。"""
    return _load(str(config_dir() / name))


def clear_config_cache() -> None:
    _load.cache_clear()
