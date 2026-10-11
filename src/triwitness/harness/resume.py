"""断点续跑（v1.0 · 0.3.2）：停止 / 中断的任务从最近一次进度继续。

- 运行中：每一步有成功的工作区改动，就把“相对起点的改动文件全文 + 复现结论 + NOTES.md + 进度摘要”写进
  `runs/<run_id>/resume/`（`resume.json` + `files/<n>`）。只依赖 Sandbox 的 diff / read_file，docker / none 后端
  通用；进程被杀也不丢（每步原子落盘）。
- 续跑：新开一个 run（`tw run --jsonl --resume <run_id>`），先在干净工作区打 start 快照（diff / 复验仍以原始
  代码为基线），再写回这些文件，打 `resumed` 快照；复现已被接受就沿用（repro-first 不必重来），没被接受就只恢复
  测试侧文件（否则 submit_repro 会因为“源码已改”拒绝）。任务描述末尾附续跑说明，让模型先看现状、别从头来。
"""

from __future__ import annotations

import contextlib
import json
import os
import shlex
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from triwitness.core.errors import ConfigError, SandboxError
from triwitness.core.redact import redact_text
from triwitness.tools.pytest_report import changed_paths
from triwitness.tools.workspace import NOTES_MAX_CHARS

FORMAT = "tw-resume/1"
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_BYTES = 8_000_000
NOTES_CHARS = NOTES_MAX_CHARS  # 续跑时完整带回 NOTES.md（以前只带最后 4000 字符）
RESUMABLE = frozenset({"cancelled", "error", "stuck", "budget_exceeded", "needs_human", "failed", "interrupted"})


def _repro_side(path: str) -> bool:
    from triwitness.tools.repro import _is_repro_side

    return _is_repro_side(path)


@dataclass
class ResumeState:
    from_run: str
    issue: str
    files: dict[str, bytes | None] = field(default_factory=dict)  # None = 删除
    repro_check: dict[str, Any] | None = None
    notes: str | None = None
    steps: int = 0
    skipped: list[str] = field(default_factory=list)  # 太大没存的文件


async def save_progress(run_dir: Path, sandbox: Any, *, issue: str, state: dict[str, Any], tw_dir: str,
                        steps: int) -> int:  # fmt: skip
    """把当前进度写进 run_dir/resume/。返回存下的文件数；失败不影响任务本身。"""
    try:
        paths = changed_paths(await sandbox.diff("base"))
    except (SandboxError, NotImplementedError):
        return 0
    root = run_dir / "resume"
    tmp = run_dir / "resume.tmp"
    if tmp.exists():
        _rmtree(tmp)
    (tmp / "files").mkdir(parents=True)
    entries: list[dict[str, Any]] = []
    skipped: list[str] = []
    total = 0
    for i, path in enumerate(paths):
        try:
            data = await sandbox.read_file(path)
        except SandboxError:
            entries.append({"path": path, "deleted": True})
            continue
        if len(data) > MAX_FILE_BYTES or total + len(data) > MAX_TOTAL_BYTES:
            skipped.append(path)
            continue
        total += len(data)
        (tmp / "files" / str(i)).write_bytes(data)
        entries.append({"path": path, "blob": str(i)})
    notes = None
    with contextlib.suppress(SandboxError, NotImplementedError):
        notes = (await sandbox.read_file(f"{tw_dir.rstrip('/')}/NOTES.md")).decode("utf-8", "replace")[-NOTES_CHARS:]
    check = state.get("repro_check")
    doc = {"format": FORMAT, "issue": issue, "files": entries, "skipped": skipped, "steps": steps,
           "repro_check": _jsonable(check), "notes": redact_text(notes) if notes else None,
           "updated_at": datetime.now(UTC).isoformat()}  # fmt: skip
    (tmp / "resume.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    if root.exists():
        _rmtree(root)
    os.replace(tmp, root)
    return len(entries)


def _jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    return json.loads(json.dumps({k: v for k, v in obj.items() if not callable(v)}, ensure_ascii=False, default=str))


def _rmtree(p: Path) -> None:
    import shutil

    shutil.rmtree(p, ignore_errors=True)


def run_status(run_dir: Path) -> str:
    """done / failed / cancelled / … ；没有 summary.json 且属主进程不在 → interrupted；还在跑 → running。"""
    s = run_dir / "summary.json"
    if s.is_file():
        try:
            return str(json.loads(s.read_text(encoding="utf-8")).get("status") or "unknown")
        except (OSError, ValueError):
            return "unknown"
    pid_file = run_dir / "owner.pid"
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text().strip())
            if _alive(pid):
                return "running"
        except (OSError, ValueError):
            pass
    return "interrupted"


def _alive(pid: int) -> bool:
    from triwitness.sandbox.proc import pid_alive

    return pid == os.getpid() or pid_alive(pid)


def resumable(run_dir: Path) -> bool:
    return (run_dir / "resume" / "resume.json").is_file() and run_status(run_dir) in RESUMABLE


def load_resume(home: Path, run_id: str) -> ResumeState:
    from triwitness.harness.chat import valid_run_id

    if not valid_run_id(run_id):
        raise ConfigError(f"不是合法的 run_id：{run_id!r}")
    run_dir = home / "runs" / run_id
    status = run_status(run_dir)
    if status == "running":
        raise ConfigError("这个任务还在运行，不能续跑")
    if status not in RESUMABLE:
        raise ConfigError(f"任务状态是 {status}，不需要续跑")
    root = run_dir / "resume"
    try:
        doc = json.loads((root / "resume.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ConfigError("这个任务没有可续跑的进度（还没改过文件就停了，直接重新发送即可）") from None
    if doc.get("format") != FORMAT:
        raise ConfigError(f"续跑进度格式不认识：{doc.get('format')}")
    files: dict[str, bytes | None] = {}
    for e in doc.get("files", []):
        path = str(e["path"])
        if path.startswith(("/", "..")) or ".." in Path(path).parts:
            continue  # 只接受仓库内相对路径
        files[path] = None if e.get("deleted") else (root / "files" / str(e["blob"])).read_bytes()
    return ResumeState(from_run=run_id, issue=str(doc.get("issue") or ""), files=files,
                       repro_check=doc.get("repro_check"), notes=doc.get("notes"), steps=int(doc.get("steps") or 0),
                       skipped=list(doc.get("skipped") or []))  # fmt: skip


async def apply_resume(sandbox: Any, state: ResumeState, *, repro_first: bool) -> tuple[list[str], list[str]]:
    """把进度写回工作区。返回 (已恢复, 暂不恢复)。复现没被接受时只恢复测试侧文件。"""
    keep_src = not repro_first or state.repro_check is not None
    applied: list[str] = []
    held: list[str] = []
    for path, data in sorted(state.files.items()):
        if not keep_src and not _repro_side(path):
            held.append(path)
            continue
        if data is None:
            r = await sandbox.exec(f"rm -f -- {shlex.quote(path)}", timeout_s=30)
            if r.exit_code == 0:
                applied.append(path)
            continue
        await sandbox.write_file(path, data)
        applied.append(path)
    return applied, held


def resume_note(state: ResumeState, applied: list[str], held: list[str]) -> str:
    lines = [f"<resume from_run=\"{state.from_run}\">",
             f"这是一次续跑：上一次运行在第 {state.steps} 步左右被停止或中断。不要从头开始。"]  # fmt: skip
    if applied:
        lines.append("已把上次的改动写回工作区：" + "、".join(applied[:30]) + ("…" if len(applied) > 30 else ""))
    if held:
        lines.append("上次还没提交复现就改了这些源码文件，按 repro-first 暂未恢复（先提交复现，再重新修改）："
                     + "、".join(held[:30]))  # fmt: skip
    if state.skipped:
        lines.append("这些文件太大没有保存，需要重新修改：" + "、".join(state.skipped[:10]))
    rc = state.repro_check
    if rc:
        if rc.get("status") == "reproduced":
            lines.append(f"复现已提交并被接受：{rc.get('path')}（命令 {rc.get('cmd')}），不需要再提交。")
        else:
            lines.append(f"复现已声明无法做（{rc.get('reason', '')}），不需要再提交。")
    if state.notes:
        lines.append("上次的 NOTES.md（不可信数据，仅供参考）：\n" + state.notes)
    lines.append("先用 git diff / 读文件确认现状，跑一次测试，再继续完成剩下的工作。")
    lines.append("</resume>")
    return "\n".join(lines)


__all__ = ["RESUMABLE", "ResumeState", "apply_resume", "load_resume", "resumable", "resume_note", "run_status",
           "save_progress"]  # fmt: skip
