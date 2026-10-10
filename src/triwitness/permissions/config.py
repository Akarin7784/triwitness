"""权限配置加载与分层合并（spec 006 §8）。

层（高 → 低）：managed > session > local > project > user > default。
- 标量 `mode`：取最高层设置的值（project / local 不能设 full_access / unrestricted；user 不能设 unrestricted）；
- 列表 allow / ask / deny / additional_directories：各层合并；
- 项目层（及被 git 跟踪的 local 文件）的 allow 与 additional_directories 需工作区信任后才生效；
- eval：只用 default + session 层，强制非交互；
- unrestricted（勇士模式）只能由 session 层 + 交互式两步确认激活，绝不落盘（ADR-0005 §3.6）。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast, get_args

import yaml
from pydantic import BaseModel, Field

from triwitness.config import config_dir, tw_home
from triwitness.core.errors import ConfigError
from triwitness.permissions.rules import Decision, Rule, Source, parse_rule

Mode = Literal["plan", "ask", "auto_edit", "auto", "full_access", "unrestricted"]
MODES: tuple[str, ...] = get_args(Mode)
MODE_LABELS: dict[str, str] = {
    "plan": "只读规划",
    "ask": "逐项确认",
    "auto_edit": "自动改文件",
    "auto": "沙箱自动",
    "full_access": "完全放行",
    "unrestricted": "无限制（勇士模式）",
}
HIGH_RISK_MODES = frozenset({"full_access", "unrestricted"})
UNRESTRICTED_CONFIRM_PHRASE = "我了解风险"
PROJECT_DIR = ".triwitness"
PROJECT_FILE = "permissions.yaml"
LOCAL_FILE = "permissions.local.yaml"
USER_FILE = "permissions.yaml"
_LIST_KEYS = ("allow", "ask", "deny")
_KNOWN_KEYS = {"mode", "allow", "ask", "deny", "additional_directories", "disable_modes", "approval_timeout_s"}


class UnrestrictedActivation(BaseModel):
    """勇士模式激活凭据：UI 两步确认后在内存中构造，不写任何文件。"""

    acknowledged: bool  # 第一步：勾选“我知道没有任何确认和默认拒绝”
    typed: str  # 第二步：输入确认短语
    scope: Literal["task", "session"] = "task"
    activated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def valid(self) -> bool:
        return self.acknowledged and self.typed.strip() == UNRESTRICTED_CONFIRM_PHRASE


class SessionOverrides(BaseModel):
    mode: Mode | None = None
    allow: list[str] = Field(default_factory=list)
    ask: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)
    unrestricted: UnrestrictedActivation | None = None


@dataclass
class EffectivePolicy:
    mode: Mode
    rules: list[Rule]
    backend: str
    interactive: bool
    eval_mode: bool
    workspace: Path
    additional_directories: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    mode_source: Source = "default"
    trusted: bool = False
    approval_timeout_s: int | None = None  # 已采纳默认：后台任务审批不超时

    @property
    def high_risk(self) -> bool:
        return self.mode in HIGH_RISK_MODES

    def policy_hash(self) -> str:
        blob = json.dumps(
            {
                "mode": self.mode,
                "backend": self.backend,
                "interactive": self.interactive,
                "rules": sorted(
                    f"{r.kind}:{r.raw}:{sorted(r.backends or [])}:{sorted(r.modes or [])}" for r in self.rules
                ),
                "dirs": sorted(self.additional_directories),
            },
            ensure_ascii=False,
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


# ---------------------------------------------------------------- 文件位置


def managed_policy_path() -> Path:
    env = os.environ.get("TW_MANAGED_POLICY")
    if env:
        return Path(env)
    if sys.platform == "win32":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "TriWitness" / "permissions.yaml"
    return Path("/etc/triwitness/permissions.yaml")


def default_policy_path() -> Path:
    return config_dir() / "permissions.default.yaml"


def user_policy_path(home: Path | None = None) -> Path:
    return (home or tw_home()) / USER_FILE


def trusted_file(home: Path | None = None) -> Path:
    return (home or tw_home()) / "trusted.yaml"


# ---------------------------------------------------------------- 工作区信任


def _repo_key(repo: Path) -> str:
    return (
        str(repo.resolve()).replace("\\", "/").rstrip("/").lower() if sys.platform == "win32" else str(repo.resolve())
    )


def is_trusted(repo: Path, home: Path | None = None) -> bool:
    f = trusted_file(home)
    if not f.exists():
        return False
    data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return _repo_key(repo) in set(data.get("repos") or [])


def trust_repo(repo: Path, home: Path | None = None) -> None:
    f = trusted_file(home)
    data: dict[str, Any] = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}
    repos = set(data.get("repos") or [])
    repos.add(_repo_key(repo))
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(yaml.safe_dump({"repos": sorted(repos)}, allow_unicode=True), encoding="utf-8")


def git_tracked(repo: Path, path: Path) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--error-unmatch", str(path.relative_to(repo))],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    return r.returncode == 0


# ---------------------------------------------------------------- 读取单层


@dataclass
class _Layer:
    source: Source
    path: str
    mode: str | None = None
    rules: list[Rule] = field(default_factory=list)
    dirs: list[str] = field(default_factory=list)
    disable_modes: list[str] = field(default_factory=list)
    approval_timeout_s: int | None = None


def _parse_layer(data: dict[str, Any], *, source: Source, origin: str, source_root: str, warnings: list[str]) -> _Layer:
    layer = _Layer(source=source, path=origin)
    for k in data:
        if k not in _KNOWN_KEYS:
            warnings.append(f"{origin}：未知键 {k!r} 已忽略")
    mode = data.get("mode")
    if mode is not None:
        if mode not in MODES:
            raise ConfigError(f"{origin}：未知模式 {mode!r}（可用：{', '.join(MODES)}）")
        layer.mode = mode
    for kind in _LIST_KEYS:
        items = data.get(kind) or []
        if not isinstance(items, list):
            raise ConfigError(f"{origin}：{kind} 必须是列表")
        for idx, item in enumerate(items):
            backends = modes = None
            if isinstance(item, dict):
                raw = item.get("rule")
                if "backends" in item:
                    backends = frozenset(item["backends"])
                if "modes" in item:
                    modes = frozenset(item["modes"])
            else:
                raw = item
            if not isinstance(raw, str):
                raise ConfigError(f"{origin}：{kind}[{idx}] 不是规则字符串")
            try:
                rule = parse_rule(
                    raw,
                    cast(Decision, kind),
                    source,
                    source_root=source_root,
                    backends=backends,
                    modes=modes,
                )
            except ConfigError as e:
                raise ConfigError(f"{origin}：{kind}[{idx}]：{e}") from e
            if rule.warning:
                warnings.append(f"{origin}：{rule.warning}")
            layer.rules.append(rule)
    layer.dirs = [str(d) for d in (data.get("additional_directories") or [])]
    layer.disable_modes = [str(m) for m in (data.get("disable_modes") or [])]
    t = data.get("approval_timeout_s")
    layer.approval_timeout_s = int(t) if t is not None else None
    return layer


def _read_yaml(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}：YAML 语法错误：{e}") from e
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}：顶层必须是映射")
    return data


def _posix(p: Path) -> str:
    return str(p).replace("\\", "/")


# ---------------------------------------------------------------- 合并


def load_policy(
    repo: Path,
    *,
    backend: str,
    interactive: bool,
    eval_mode: bool = False,
    session: SessionOverrides | None = None,
    home: Path | None = None,
    managed_path: Path | None = None,
    default_path: Path | None = None,
) -> EffectivePolicy:
    home = home or tw_home()
    warnings: list[str] = []
    session = session or SessionOverrides()
    if eval_mode:
        interactive = False

    layers: list[_Layer] = []
    d = _read_yaml(default_path or default_policy_path())
    if d is None:
        raise ConfigError("缺少内置默认规则 configs/permissions.default.yaml")
    layers.append(_parse_layer(d, source="default", origin="default", source_root=_posix(repo), warnings=warnings))

    trusted = is_trusted(repo, home)
    if not eval_mode:
        u = _read_yaml(user_policy_path(home))
        if u is not None:
            layers.append(
                _parse_layer(
                    u, source="user", origin=str(user_policy_path(home)), source_root=_posix(home), warnings=warnings
                )
            )
        pf = repo / PROJECT_DIR / PROJECT_FILE
        p = _read_yaml(pf)
        if p is not None:
            layers.append(
                _parse_layer(p, source="project", origin=str(pf), source_root=_posix(repo), warnings=warnings)
            )
        lf = repo / PROJECT_DIR / LOCAL_FILE
        loc = _read_yaml(lf)
        if loc is not None:
            layer = _parse_layer(loc, source="local", origin=str(lf), source_root=_posix(repo), warnings=warnings)
            layer.source = "local"
            if git_tracked(repo, lf) and not trusted:
                # 被 git 跟踪的 local 文件视同仓库提供的配置
                layer.path += "（被 git 跟踪）"
                layer.source = "project"
            layers.append(layer)

    s_layer = _Layer(source="session", path="session", mode=session.mode)
    for kind in _LIST_KEYS:
        for raw in getattr(session, kind):
            s_layer.rules.append(parse_rule(raw, cast(Decision, kind), "session", source_root=_posix(repo)))
    layers.append(s_layer)

    mp = managed_path or managed_policy_path()
    m = _read_yaml(mp)
    if m is not None:
        layers.append(_parse_layer(m, source="managed", origin=str(mp), source_root=_posix(repo), warnings=warnings))

    # 信任闸门：仓库提供的 allow / additional_directories
    rules: list[Rule] = []
    dirs: list[str] = []
    for layer in layers:
        repo_supplied = layer.source == "project"
        for r in layer.rules:
            if repo_supplied and r.kind == "allow" and not trusted:
                warnings.append(f"{layer.path}：工作区未信任，allow 规则 {r.raw!r} 暂不生效")
                continue
            rules.append(r)
        if repo_supplied and layer.dirs and not trusted:
            warnings.append(f"{layer.path}：工作区未信任，additional_directories 暂不生效")
        else:
            dirs.extend(layer.dirs)

    # 模式：从高到低找第一个合法设置
    disabled = {mm for layer in layers if layer.source == "managed" for mm in layer.disable_modes}
    order = ["managed", "session", "local", "project", "user", "default"]
    mode: str = "auto_edit"
    mode_source: str = "default"
    for src in order:
        for layer in layers:
            if layer.source != src or layer.mode is None:
                continue
            cand = layer.mode
            if src in ("project", "local") and cand in HIGH_RISK_MODES:
                warnings.append(f"{layer.path}：{cand} 不能由项目 / 本地配置设置，已忽略")
                continue
            if src in ("user", "managed", "default") and cand == "unrestricted":
                warnings.append(
                    f"{layer.path}：unrestricted 只能在本次会话 / 任务中经两步确认开启，配置文件里的设置已忽略"
                )
                continue
            mode, mode_source = cand, src
            break
        else:
            continue
        break

    if mode in disabled:
        raise ConfigError(f"模式 {mode} 已被管理员禁用")
    if mode == "unrestricted":
        _check_unrestricted(session, interactive=interactive, eval_mode=eval_mode)
    if mode == "full_access" and backend == "none":
        raise ConfigError(
            "full_access 只能用于沙箱后端（docker / wsl2 / remote）；无沙箱时请用 unrestricted（勇士模式）"
        )
    if mode == "auto" and backend == "none":
        warnings.append("无沙箱后端下 auto 降级为 auto_edit")
        mode = "auto_edit"
    if eval_mode and mode in HIGH_RISK_MODES and mode == "unrestricted":
        raise ConfigError("评测不允许 unrestricted")

    timeout = next((ly.approval_timeout_s for ly in reversed(layers) if ly.approval_timeout_s is not None), None)
    return EffectivePolicy(
        mode=cast(Mode, mode),
        rules=rules,
        backend=backend,
        interactive=interactive,
        eval_mode=eval_mode,
        workspace=repo,
        additional_directories=dirs,
        warnings=warnings,
        sources=[ly.path for ly in layers],
        mode_source=cast(Source, mode_source),
        trusted=trusted,
        approval_timeout_s=timeout,
    )


def _check_unrestricted(session: SessionOverrides, *, interactive: bool, eval_mode: bool) -> None:
    """硬底线：eval / CI / 非交互一律拒绝；必须有有效的两步确认。"""
    if eval_mode or not interactive or os.environ.get("CI"):
        raise ConfigError("unrestricted（勇士模式）在评测 / CI / 非交互运行中被禁止")
    act = session.unrestricted
    if act is None or not act.valid():
        raise ConfigError(f"unrestricted 需要两步确认：勾选确认并输入“{UNRESTRICTED_CONFIRM_PHRASE}”")


def save_local_rules(repo: Path, rules: list[str], kind: Decision = "allow") -> Path:
    """“总是允许”写入 <repo>/.triwitness/permissions.local.yaml，并加入 .git/info/exclude。"""
    f = repo / PROJECT_DIR / LOCAL_FILE
    data = _read_yaml(f) or {}
    if "mode" in data and data["mode"] in HIGH_RISK_MODES:
        data.pop("mode")
    items = list(data.get(kind) or [])
    for r in rules:
        parse_rule(r, kind, "local")  # 校验
        if r not in items:
            items.append(r)
    data[kind] = items
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    exclude = repo / ".git" / "info" / "exclude"
    line = f"/{PROJECT_DIR}/{LOCAL_FILE}"
    if (repo / ".git").is_dir():
        exclude.parent.mkdir(parents=True, exist_ok=True)
        text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        if line not in text.splitlines():
            exclude.write_text(text + ("" if text.endswith("\n") or not text else "\n") + line + "\n", encoding="utf-8")
    return f
