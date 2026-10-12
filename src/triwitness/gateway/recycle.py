"""托管区与可撤销操作（spec 014 §7，W7-09）。

- `RecycleBin`：删除文件 / 目录 = 移进 `<workspace>/.tw/trash/<条目>/`，带清单，可 `restore`；只接受工作区内路径；
- `check_git_push`：解析 `git push` 参数，只允许推 `tw/*` 分支；
  禁止 force（-f / --force / --force-with-lease / `+ref`）、删除远端分支（--delete / `:ref`）、
  --mirror / --all / --tags；
- `DeferredOps`：外部 DELETE / 批量写不立即执行：排队 → 等延迟窗口 → 人工批准后才执行；执行前随时可撤销；
- 全部动作写审计 JSONL（不记请求体）。
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

TRASH = ".tw/trash"
BULK_THRESHOLD = 20


class GuardError(Exception):
    """被护栏拒绝的操作。"""


def _now() -> float:
    return time.time()


def _audit(audit_file: Path | None, **rec: Any) -> None:
    if audit_file is None:
        return
    path = audit_file
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **rec}, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------------------------------ 回收区
@dataclass
class TrashEntry:
    id: str
    path: str  # 相对工作区
    at: float
    is_dir: bool


class RecycleBin:
    def __init__(self, workspace: Path, *, audit_path: Path | None = None) -> None:
        self.ws = workspace.resolve()
        self.root = self.ws / TRASH
        self.audit_path = audit_path

    def _rel(self, path: Path | str) -> Path:
        p = Path(path)
        full = (p if p.is_absolute() else self.ws / p).resolve()
        if full == self.ws or self.ws not in full.parents:
            raise GuardError(f"只能删除工作区内的文件：{path}")
        rel = full.relative_to(self.ws)
        if rel.parts[0] in (".git", ".tw"):
            raise GuardError(f"受保护目录不能删除：{rel}")
        return rel

    def delete(self, path: Path | str) -> TrashEntry:
        rel = self._rel(path)
        src = self.ws / rel
        if not src.exists() and not src.is_symlink():
            raise GuardError(f"不存在：{rel}")
        eid = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        dst = self.root / eid / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        is_dir = src.is_dir() and not src.is_symlink()
        shutil.move(str(src), str(dst))
        e = TrashEntry(eid, rel.as_posix(), _now(), is_dir)
        (self.root / eid / ".entry.json").write_text(json.dumps(asdict(e), ensure_ascii=False), encoding="utf-8")
        _audit(self.audit_path, kind="trash", path=e.path, id=eid)
        return e

    def entries(self) -> list[TrashEntry]:
        out = []
        for m in sorted(self.root.glob("*/.entry.json")) if self.root.is_dir() else []:
            out.append(TrashEntry(**json.loads(m.read_text(encoding="utf-8"))))
        return out

    def restore(self, eid: str, *, overwrite: bool = False) -> Path:
        meta = self.root / eid / ".entry.json"
        if not meta.is_file():
            raise GuardError(f"回收区里没有 {eid}")
        e = TrashEntry(**json.loads(meta.read_text(encoding="utf-8")))
        dst = self.ws / e.path
        if dst.exists() and not overwrite:
            raise GuardError(f"原位置已有文件：{e.path}（加 overwrite 覆盖）")
        if dst.exists():
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.root / eid / e.path), str(dst))
        shutil.rmtree(self.root / eid)
        _audit(self.audit_path, kind="restore", path=e.path, id=eid)
        return dst

    def purge(self, older_than_s: float) -> int:
        n = 0
        for e in self.entries():
            if _now() - e.at > older_than_s:
                shutil.rmtree(self.root / e.id)
                n += 1
        return n


# ------------------------------------------------------------------------------------------ git
@dataclass
class PushCheck:
    allowed: bool
    reason: str
    refs: list[str] = field(default_factory=list)


def check_git_push(args: list[str], *, current_branch: str = "") -> PushCheck:
    """args 是 `git push` 之后的参数。只允许把 tw/* 分支以非强制方式推上去。"""
    force = delete = False
    positional: list[str] = []
    for a in args:
        if a in ("-f", "--force", "--force-if-includes") or a.startswith("--force-with-lease"):
            force = True
        elif a in ("-d", "--delete"):
            delete = True
        elif a in ("--mirror", "--all", "--tags", "--prune"):
            return PushCheck(False, f"不允许 git push {a}")
        elif a.startswith("-"):
            continue  # -u / --set-upstream / -q 等无害选项
        else:
            positional.append(a)
    if force:
        return PushCheck(False, "禁止 force push")
    if delete:
        return PushCheck(False, "不允许删除远端分支")
    specs = positional[1:] if positional else []
    if not specs:
        specs = [current_branch] if current_branch else []
    if not specs:
        return PushCheck(False, "无法确定推送的分支（显式写出 tw/* 分支）")
    refs = []
    for s in specs:
        if s.startswith("+"):
            return PushCheck(False, f"禁止强制 refspec {s}")
        src, _, dst = s.partition(":")
        if s.startswith(":"):
            return PushCheck(False, f"不允许删除远端分支 {s}")
        target = (dst or src).removeprefix("refs/heads/")
        if src in ("HEAD", "@") and not dst:
            target = current_branch
        if not target.startswith("tw/"):
            return PushCheck(False, f"只允许推 tw/* 分支（目标是 {target or '?'}）")
        refs.append(target)
    return PushCheck(True, "ok", refs)


# ------------------------------------------------------------------------------------------ 延迟执行
OpStatus = Literal["pending", "approved", "revoked", "done", "failed"]


@dataclass
class DeferredOp:
    id: str
    kind: str  # http_delete / bulk_write / github_delete_branch …
    target: str  # 方法 + URL / 资源名（不含请求体与密钥）
    params: dict[str, Any]
    created: float
    not_before: float
    status: OpStatus = "pending"
    approved_by: str = ""
    result: str = ""


def is_destructive(method: str, *, items: int = 1) -> bool:
    return method.upper() == "DELETE" or (method.upper() in ("POST", "PUT", "PATCH") and items > BULK_THRESHOLD)


class DeferredOps:
    def __init__(self, path: Path, *, delay_s: float = 300, audit_path: Path | None = None) -> None:
        self.path = path
        self.delay_s = delay_s
        self.audit_path = audit_path

    def _load(self) -> dict[str, DeferredOp]:
        if not self.path.is_file():
            return {}
        return {k: DeferredOp(**v) for k, v in json.loads(self.path.read_text(encoding="utf-8")).items()}

    def _save(self, ops: dict[str, DeferredOp]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({k: asdict(v) for k, v in ops.items()}, ensure_ascii=False, indent=1),
                             encoding="utf-8")  # fmt: skip

    def schedule(self, kind: str, target: str, params: dict[str, Any] | None = None) -> DeferredOp:
        ops = self._load()
        now = _now()
        op = DeferredOp(uuid.uuid4().hex[:10], kind, target, dict(params or {}), now, now + self.delay_s)
        ops[op.id] = op
        self._save(ops)
        _audit(self.audit_path, kind="deferred", op=op.id, op_kind=kind, target=target, not_before=op.not_before)
        return op

    def approve(self, op_id: str, *, by: str) -> DeferredOp:
        if not by.strip():
            raise GuardError("批准必须写批准人")
        return self._transition(op_id, "approved", by=by)

    def revoke(self, op_id: str, *, by: str = "") -> DeferredOp:
        return self._transition(op_id, "revoked", by=by)

    def _transition(self, op_id: str, status: OpStatus, *, by: str = "") -> DeferredOp:
        ops = self._load()
        op = ops.get(op_id)
        if op is None:
            raise GuardError(f"没有操作 {op_id}")
        if op.status not in ("pending", "approved"):
            raise GuardError(f"{op_id} 已是 {op.status}，不能改成 {status}")
        op.status = status
        if status == "approved":
            op.approved_by = by
        self._save(ops)
        _audit(self.audit_path, kind=status, op=op_id, by=by)
        return op

    def run_due(self, executor: Callable[[DeferredOp], str], *, now: float | None = None) -> list[DeferredOp]:
        """执行“已批准且过了延迟窗口”的操作；pending（没人批）和 revoked 的永远不执行。"""
        t = _now() if now is None else now
        ops = self._load()
        done = []
        for op in ops.values():
            if op.status != "approved" or t < op.not_before:
                continue
            try:
                op.result = executor(op)[:500]
                op.status = "done"
            except Exception as e:
                op.result = f"{type(e).__name__}: {e}"[:500]
                op.status = "failed"
            _audit(self.audit_path, kind="executed", op=op.id, status=op.status)
            done.append(op)
        self._save(ops)
        return done

    def list(self) -> list[DeferredOp]:
        return list(self._load().values())


__all__ = ["DeferredOp", "DeferredOps", "GuardError", "PushCheck", "RecycleBin", "TrashEntry", "check_git_push",
           "is_destructive"]  # fmt: skip
