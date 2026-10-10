"""影子提交快照 / 回滚 / diff（spec 002 §6），各后端共用；只在宿主上跑 git。

- snapshot：临时索引 `GIT_INDEX_FILE` + `git add -A` + `commit-tree`，写 `refs/tw/ckpt/<run_id>/<label>`；
  **不移动当前分支、不动真实索引**；
- restore：`read-tree --reset -u <ref>` → `git clean -fd`（保留被忽略的文件，如 .venv / node_modules）
  → `git reset -q`（索引回到 HEAD）；
- diff：临时索引收全工作区（含未跟踪新文件），与 base 比较；排除任何 `.tw/` 目录。
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path

from triwitness.core.errors import SandboxError
from triwitness.sandbox.base import scrub_host_env

EXCLUDES = (":(exclude).tw", ":(exclude,glob)**/.tw/**")
_LABEL_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_IDENT = {
    "GIT_AUTHOR_NAME": "TriWitness",
    "GIT_AUTHOR_EMAIL": "tw@localhost",
    "GIT_COMMITTER_NAME": "TriWitness",
    "GIT_COMMITTER_EMAIL": "tw@localhost",
}


def git_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    env = scrub_host_env(os.environ)
    env.update(_IDENT)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["LC_ALL"] = "C"
    if extra:
        env.update(extra)
    return env


async def git(
    *args: str,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    input: bytes | None = None,
    timeout: float = 120,
) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        env=git_env(env),
        stdin=asyncio.subprocess.PIPE if input is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(input), timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise SandboxError(f"git {args[0]} 超时") from None
    code = proc.returncode or 0
    if check and code != 0:
        raise SandboxError(f"git {' '.join(args[:2])} 失败：{err.decode(errors='replace').strip()[:500]}")
    return code, out, err


class GitSnapshotter:
    """在 workdir（git 工作树）里做快照；git_env 可指定 GIT_DIR / GIT_WORK_TREE（docker 镜像目录用）。"""

    def __init__(self, workdir: Path, run_id: str, *, base: str, env: Mapping[str, str] | None = None) -> None:
        self.workdir = workdir
        self.run_id = run_id
        self.base = base  # 创建时的提交 sha
        self.env = dict(env or {})

    def ref(self, label: str) -> str:
        if not _LABEL_RE.match(label):
            raise SandboxError(f"快照标签只能含字母数字 . _ -：{label!r}")
        return f"refs/tw/ckpt/{self.run_id}/{label}"

    async def _rev(self, name: str) -> str:
        cand = [name] if name.startswith(("refs/", "HEAD")) or re.fullmatch(r"[0-9a-f]{7,40}", name) else []
        if name == "base":
            return self.base
        if _LABEL_RE.match(name):
            cand.append(self.ref(name))
        cand.append(name)
        for c in cand:
            code, out, _ = await git("rev-parse", "--verify", "-q", f"{c}^{{commit}}", cwd=self.workdir, env=self.env,
                                     check=False)  # fmt: skip
            if code == 0:
                return out.decode().strip()
        raise SandboxError(f"找不到快照或提交：{name}")

    async def _tree_of_worktree(self) -> str:
        with tempfile.TemporaryDirectory(prefix="tw-idx-") as d:
            env = {**self.env, "GIT_INDEX_FILE": str(Path(d) / "index")}
            await git("read-tree", "HEAD", cwd=self.workdir, env=env)
            await git("add", "-A", "--", ".", *EXCLUDES, cwd=self.workdir, env=env)
            _, out, _ = await git("write-tree", cwd=self.workdir, env=env)
        return out.decode().strip()

    async def snapshot(self, label: str) -> str:
        ref = self.ref(label)
        tree = await self._tree_of_worktree()
        _, head, _ = await git("rev-parse", "HEAD", cwd=self.workdir, env=self.env)
        _, commit, _ = await git(
            "commit-tree", tree, "-p", head.decode().strip(), "-m", f"tw checkpoint {label}",
            cwd=self.workdir, env=self.env,
        )  # fmt: skip
        await git("update-ref", ref, commit.decode().strip(), cwd=self.workdir, env=self.env)
        return ref

    async def restore(self, ref: str) -> None:
        sha = await self._rev(ref)
        await git("read-tree", "--reset", "-u", sha, cwd=self.workdir, env=self.env)
        await git("clean", "-fdq", "-e", ".tw", cwd=self.workdir, env=self.env)
        await git("reset", "-q", cwd=self.workdir, env=self.env)

    async def diff(self, base: str = "base") -> str:
        sha = await self._rev(base)
        tree = await self._tree_of_worktree()
        _, out, _ = await git("diff", "--binary", "--no-color", "--no-ext-diff", sha, tree, "--", ".", *EXCLUDES,
                              cwd=self.workdir, env=self.env)  # fmt: skip
        return out.decode("utf-8", "replace")

    async def list(self) -> list[str]:
        _, out, _ = await git("for-each-ref", "--format=%(refname)", f"refs/tw/ckpt/{self.run_id}/",
                              cwd=self.workdir, env=self.env)  # fmt: skip
        return [r.rsplit("/", 1)[1] for r in out.decode().split()]

    async def drop_refs(self) -> None:
        for label in await self.list():
            await git("update-ref", "-d", self.ref(label), cwd=self.workdir, env=self.env, check=False)
