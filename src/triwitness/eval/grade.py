"""Grader（spec 004 §6.3，W1-30）：同镜像新建干净沙箱 → 应用 diff → 放入隐藏测试 → 跑 test.sh → 读 reward。

防作弊（04 §4.4 的 W1 子集，结构性）：
- Agent 的沙箱里从来没有 tests/、solution/（镜像构建上下文只有 environment/）；Grader 永远不复用 Agent 的沙箱。
- diff 里改测试基础设施的部分**不应用**：conftest.py、pytest.ini、tox.ini、setup.cfg、pyproject.toml、
  sitecustomize / usercustomize、*.pth，以及已有测试文件。新加的测试文件同样不应用（判分只看隐藏测试），但不算篡改。
- 被丢弃的路径写进结果：`tamper_paths`（疑似篡改）/ `ignored_paths`（无害忽略）。
- 已有测试文件只“加行”（补回归测试，不删不改原有行）算无害；删改原有测试行、动测试基础设施才算篡改
  （W1-34 真跑：pyflakes / slpp 两次只是补测试却被记成篡改）。改动一律不应用，所以分类只影响标记，不影响判分。
- W2-25 真跑复核：9 个“篡改”里 6 个是按 issue 改已有测试的期望值（断言数不减、无 skip），属于“改写已有测试”
  （`edited_paths`，需人审，不算篡改）。已有测试只有出现削弱信号才算篡改：删文件 / 改名、新增 skip / xfail /
  importorskip、恒真断言、净减少断言（规则与 verify/anticheat 共用）。测试基础设施一律算篡改。
"""

from __future__ import annotations

import asyncio
import fnmatch
import posixpath
import re
from typing import NamedTuple

from pydantic import BaseModel, Field

from triwitness.core.errors import SandboxError
from triwitness.eval.task import EvalTask
from triwitness.eval.validate import ensure_image, run_verifier
from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.docker import DockerSandbox, DockerSandboxBackend

INFRA_FILES = frozenset(
    {"conftest.py", "pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml", "sitecustomize.py", "usercustomize.py"}
)
TEST_DIRS = frozenset({"tests", "test", "testing"})
VERIFIER_USER = "1000:1000"
_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.M)


class FilePatch(BaseModel):
    path: str
    old_path: str
    text: str
    new_file: bool
    deleted: bool


def additions_only(fp: FilePatch) -> bool:
    """该文件的改动只新增行（不删、不改原有行，不删除文件、不改名）。"""
    if fp.deleted or fp.old_path != fp.path or "GIT binary patch" in fp.text:
        return False
    body = fp.text.split("\n@@", 1)
    if len(body) < 2:
        return False  # 只有模式变更等，没有内容
    return not any(ln.startswith("-") and not ln.startswith("---") for ln in body[1].splitlines())


class GradeResult(BaseModel):
    resolved: bool
    reward: float | None
    patch_applied: bool
    tamper_paths: list[str] = Field(default_factory=list)
    ignored_paths: list[str] = Field(default_factory=list)
    edited_paths: list[str] = Field(default_factory=list)
    log_tail: str = ""
    error: str | None = None


def split_patch(patch: str) -> list[FilePatch]:
    """按 `diff --git` 切成每个文件一段（git diff --binary 的输出）。"""
    starts = [m.start() for m in _HEADER.finditer(patch)]
    out: list[FilePatch] = []
    for i, st in enumerate(starts):
        chunk = patch[st : starts[i + 1] if i + 1 < len(starts) else len(patch)]
        m = _HEADER.match(chunk)
        assert m is not None
        head = chunk.split("\n@@", 1)[0]
        out.append(
            FilePatch(
                old_path=m.group(1),
                path=m.group(2),
                text=chunk,
                new_file="\nnew file mode" in head,
                deleted="\ndeleted file mode" in head,
            )
        )
    return out


def is_test_file(path: str) -> bool:
    parts = path.split("/")
    name = parts[-1]
    return (
        any(p in TEST_DIRS for p in parts[:-1])
        or (name.startswith("test_") and name.endswith(".py"))
        or name.endswith("_test.py")
        or name in ("tests.py", "test.py")
    )


def is_infra(path: str, extra: list[str] | None = None) -> bool:
    name = posixpath.basename(path)
    if name in INFRA_FILES or name.endswith(".pth"):
        return True
    return any(fnmatch.fnmatch(path, g) for g in extra or [])


class FilteredPatch(NamedTuple):
    keep: str  # 可应用的 diff
    tamper: list[str]  # 疑似篡改：测试基础设施 / 删除或改名测试 / 削弱已有测试
    ignored: list[str]  # 无害忽略：新测试文件、已有测试只加行
    edited: list[str]  # 改写已有测试（无削弱信号）：不应用、不算篡改，报告里单列供人审


WEAKENING_CODES = frozenset({"skip_or_xfail_added", "assertion_weakened"})


def weakens_existing_test(fp: FilePatch) -> bool:
    """已有测试文件的改动是否有削弱信号（复用 verify/anticheat 的确定性规则）。"""
    from triwitness.verify.anticheat import _check_file  # 延迟导入：verify.diffutil 依赖本模块

    if fp.deleted or fp.old_path != fp.path or "GIT binary patch" in fp.text:
        return True
    return any(f.code in WEAKENING_CODES for f in _check_file(fp, new_test_ok=True))


def filter_patch(patch: str, *, extra_protected: list[str] | None = None) -> FilteredPatch:
    keep: list[str] = []
    tamper: list[str] = []
    ignored: list[str] = []
    edited: list[str] = []
    for fp in split_patch(patch):
        paths = list(dict.fromkeys([fp.old_path, fp.path]))  # 改名时旧路径优先
        infra = [p for p in paths if is_infra(p, extra_protected)]
        tests = [p for p in paths if is_test_file(p)]
        if infra:
            tamper.append(infra[0])
        elif tests:
            if fp.new_file or additions_only(fp):
                ignored.append(tests[0])
            elif weakens_existing_test(fp):
                tamper.append(tests[0])
            else:
                edited.append(tests[0])
        else:
            keep.append(fp.text)
    return FilteredPatch("".join(keep), tamper, ignored, edited)


class Grader:
    def __init__(self, backend: DockerSandboxBackend | None = None) -> None:
        self.backend = backend or DockerSandboxBackend()

    async def new_sandbox(self, task: EvalTask) -> DockerSandbox:
        """与 Agent 沙箱相同的规格（同镜像、断网、uid 1000）；Agent 运行器也用它。"""
        image, _ = await asyncio.to_thread(ensure_image, task, self.backend.client())
        env = task.config.environment
        spec = SandboxSpec(
            image=image,
            workdir=env.workdir or "/workspace/repo",
            cpus=env.cpus or 1.0,
            memory_mb=env.memory_mb or 2048,
            network="none",
            env={"HOME": "/tmp"},  # uid 1000 在镜像里没有 passwd 条目，默认 HOME=/ 不可写（W2-25 ultraplot / xcp_d）
        )
        sb = await self.backend.create(spec)
        assert isinstance(sb, DockerSandbox)
        return sb

    async def grade(self, task: EvalTask, patch: str) -> GradeResult:
        keep, tamper, ignored, edited = filter_patch(patch, extra_protected=task.tw.protected)
        sb = await self.new_sandbox(task)
        try:
            try:
                await sb.apply_patch(keep)
            except SandboxError as e:
                return GradeResult(
                    resolved=False,
                    reward=None,
                    patch_applied=False,
                    tamper_paths=tamper,
                    ignored_paths=ignored,
                    edited_paths=edited,
                    error=f"patch 无法应用：{e}"[:500],
                )
            phase = await asyncio.to_thread(
                run_verifier, task, sb.container, user=VERIFIER_USER, workdir=sb.spec.workdir
            )
        finally:
            await sb.close()
        return GradeResult(
            resolved=phase.reward == 1,
            reward=phase.reward,
            patch_applied=True,
            tamper_paths=tamper,
            ignored_paths=ignored,
            edited_paths=edited,
            log_tail=phase.log_tail,
        )


__all__ = [
    "FilePatch",
    "FilteredPatch",
    "GradeResult",
    "Grader",
    "filter_patch",
    "is_infra",
    "is_test_file",
    "split_patch",
]
