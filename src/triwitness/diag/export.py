"""`tw diag export`：把排查问题需要的东西打成一个 zip，留在本机，由用户自己决定发给谁。

内容：
- ``system.json``：版本、平台、Python、git / gh / docker 是否可用、TW_* 环境变量、
  各密钥是否已配置（只给真假）；
- ``usage.json``：本地账本汇总（`tw usage --json` 同款，没有密钥）；
- ``logs/``：``$TW_HOME/logs`` 下的日志；
- ``runs/<id>/``：指定运行（默认最近 3 个）的文本文件——轨迹、结论、证据、补丁、PR 说明等；
- ``MANIFEST.json``：收了哪些文件、跳过了哪些、脱敏了多少处。

所有文本先过 :func:`triwitness.core.redact.redact_text`，再把当前进程里真实的密钥值（DEEPSEEK_API_KEY、
GITHUB_TOKEN 等）逐字替换掉；用户家目录替换成 ``~``。
不收：llm 缓存、worktree、账本数据库原件、二进制、超过 2 MiB 的文件。
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from triwitness.core.redact import redact_text

MAX_FILE_BYTES = 2 * 1024 * 1024
DEFAULT_RECENT = 3
_SKIP_DIRS = {"tree", "tree.git", "worktrees", "llm-cache", "__pycache__", ".git"}
_TEXT_EXT = {".json", ".jsonl", ".md", ".txt", ".log", ".diff", ".patch", ".yaml", ".yml", ".toml", ".py", ".csv", ""}
_SECRET_ENV = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD)", re.I)
_RUN_RE = re.compile(r"^r_[0-9A-Za-z]{8,40}$")


@dataclass
class DiagResult:
    path: Path
    files: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    redactions: int = 0
    runs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"path": str(self.path), "files": len(self.files), "skipped": len(self.skipped),
                "redactions": self.redactions, "runs": self.runs, "bytes": self.path.stat().st_size}  # fmt: skip


class _Scrubber:
    def __init__(self, env: dict[str, str]) -> None:
        vals = {v for k, v in env.items() if _SECRET_ENV.search(k) and len(v) >= 8}
        self.secrets = sorted(vals, key=len, reverse=True)
        home = str(Path.home())
        self.home = home if len(home) > 3 else ""
        self.count = 0

    def __call__(self, text: str) -> str:
        out = redact_text(text)
        for s in self.secrets:
            out = out.replace(s, "***")
        if out != text:
            self.count += 1
        if self.home:
            out = out.replace(self.home, "~")
        return out


def _which(name: str) -> bool:
    return shutil.which(name) is not None


def system_info(env: dict[str, str]) -> dict[str, Any]:
    from triwitness import __version__

    tw_env = {}
    for k in sorted(env):
        if k.startswith("TW_"):
            tw_env[k] = "***" if _SECRET_ENV.search(k) else env[k]
    return {
        "triwitness": __version__,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "frozen": bool(getattr(sys, "frozen", False)),
        "tools": {n: _which(n) for n in ("git", "gh", "docker")},
        "secrets_configured": {k: bool(env.get(k)) for k in ("DEEPSEEK_API_KEY", "GITHUB_TOKEN")},
        "env": tw_env,
    }


def _usage() -> dict[str, Any]:
    try:
        from triwitness.cost.dashboard import usage_json, usage_view
        from triwitness.cost.ledger import GlobalLedger

        led = GlobalLedger()
        return usage_json(usage_view(led), led, recent=50)
    except Exception as e:  # 诊断包不能因为账本坏了就打不出来
        return {"error": f"{type(e).__name__}: {e}"}


def _pick_runs(home: Path, run_ids: list[str] | None, recent: int) -> list[Path]:
    runs = home / "runs"
    if run_ids:
        out = []
        for rid in run_ids:
            if not _RUN_RE.match(rid):
                raise ValueError(f"运行 id 不合法：{rid}")
            d = runs / rid
            if not d.is_dir():
                raise FileNotFoundError(f"找不到运行：{rid}")
            out.append(d)
        return out
    if not runs.is_dir():
        return []
    cands = [d for d in runs.iterdir() if d.is_dir() and _RUN_RE.match(d.name)]
    cands.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return cands[:recent]


def _walk(root: Path):  # type: ignore[no-untyped-def]
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for f in sorted(filenames):
            yield Path(dirpath) / f


def _add_text(zf: zipfile.ZipFile, src: Path, arc: str, scrub: _Scrubber, res: DiagResult) -> None:
    if src.suffix.lower() not in _TEXT_EXT:
        res.skipped.append(f"{arc}（非文本）")
        return
    try:
        size = src.stat().st_size
        if size > MAX_FILE_BYTES:
            res.skipped.append(f"{arc}（{size // 1024} KiB，超过上限）")
            return
        raw = src.read_bytes()
    except OSError as e:
        res.skipped.append(f"{arc}（读不了：{e.strerror}）")
        return
    if b"\x00" in raw[:4096]:
        res.skipped.append(f"{arc}（二进制）")
        return
    zf.writestr(arc, scrub(raw.decode("utf-8", errors="replace")))
    res.files.append(arc)


def export_diagnostics(
    home: Path,
    *,
    run_ids: list[str] | None = None,
    recent: int = DEFAULT_RECENT,
    out: Path | None = None,
    env: dict[str, str] | None = None,
) -> DiagResult:
    env = dict(os.environ if env is None else env)
    runs = _pick_runs(home, run_ids, recent)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dest = out or home / "diagnostics" / f"tw-diag-{stamp}.zip"
    if dest.suffix.lower() != ".zip":
        dest = dest / f"tw-diag-{stamp}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".zip.part")
    scrub = _Scrubber(env)
    res = DiagResult(path=dest, runs=[d.name for d in runs])
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, obj in (("system.json", system_info(env)), ("usage.json", _usage())):
            zf.writestr(name, scrub(json.dumps(obj, ensure_ascii=False, indent=2)))
            res.files.append(name)
        logs = home / "logs"
        if logs.is_dir():
            for f in _walk(logs):
                _add_text(zf, f, "logs/" + f.relative_to(logs).as_posix(), scrub, res)
        for d in runs:
            for f in _walk(d):
                if f.name.endswith(".pid"):
                    continue
                _add_text(zf, f, f"runs/{d.name}/" + f.relative_to(d).as_posix(), scrub, res)
        note = "密钥已脱敏（常见密钥形态 + 本机环境里的真实密钥值），家目录替换为 ~。只在本机生成，不会自动上传。"
        manifest = {"files": res.files, "skipped": res.skipped, "redacted_files": scrub.count, "note": note}
        zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    res.redactions = scrub.count
    os.replace(tmp, dest)
    return res
