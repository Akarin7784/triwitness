"""干净环境复跑证人（04 §4.2–4.3，W3-05 / W3-07 / W3-20）。

- 每次复跑都**新建**沙箱（base_ref 检出 → 应用 diff），从不复用 Executor 的沙箱。
- 复现：基线沙箱只应用补丁里的测试文件 → 复现测试必须**失败**；修复后沙箱应用完整补丁 → 必须**通过**。
  基线就通过 = 复现没有证明 bug（inconclusive）；修复后仍失败 = failed。
- 回归：同一测试命令在基线与修复后各跑一次，只把“新出现的失败”算回归；每个新失败再单独重跑 2 次，
  只要有一次通过就记 flaky（不计失败，但写进证据）。
- 无沙箱（none 后端，capabilities.clean_env = False）：仍在全新 worktree 里复跑，但结论标
  `clean_env = unverified`、`unverified_reason = no_sandbox`（spec 002 §8 / ADR-0005 §3.3）——宿主机环境
  （已装的包、环境变量）可能让测试“碰巧”通过；风险至少 L2、禁止自动合并（verify.risk 的硬下限）。
"""

from __future__ import annotations

import shlex
from typing import Literal

from pydantic import BaseModel, Field

from triwitness.core.models import ReproRef, TestRun
from triwitness.sandbox.base import Sandbox, SandboxBackend, SandboxSpec
from triwitness.tools.pytest_report import parse_junit
from triwitness.verify.diffutil import is_test_file, split_patch

ReproStatus = Literal["reproduced", "not_applicable", "inconclusive", "failed"]
Scope = Literal["repro_base", "repro_patched", "related", "full", "hidden"]
FLAKY_RERUNS = 2


class RerunResult(BaseModel):
    repro_status: ReproStatus
    clean_env: Literal["verified", "unverified"]
    unverified_reason: str | None = None
    test_runs: list[TestRun] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    logs: dict[str, str] = Field(default_factory=dict)  # scope → 输出尾部


def only_test_files(patch: str) -> str:
    """补丁里只保留测试文件（基线沙箱用：带上复现测试，但不带修复）。"""
    return "".join(fp.text for fp in split_patch(patch) if is_test_file(fp.path))


def _tw_dir(sb: Sandbox) -> str:
    return str(getattr(sb, "tw_dir", "/workspace/.tw"))


async def _fresh(backend: SandboxBackend, spec: SandboxSpec, patch: str, label: str) -> Sandbox:
    sb = await backend.create(spec)
    apply = getattr(sb, "apply_patch", None)
    if patch.strip() and apply is not None:  # docker：在宿主镜像目录上 git apply（任务镜像里不一定有 git）
        try:
            await apply(patch)
        except Exception as e:
            await sb.close()
            raise PatchApplyError(f"{label}: git apply 失败：{str(e)[-400:]}") from e
    elif patch.strip():
        path = f"{_tw_dir(sb)}/verify-{label}.patch"
        await sb.write_file(path, patch.encode())
        r = await sb.exec(f"git apply --whitespace=nowarn {shlex.quote(path)}", timeout_s=60)
        if r.exit_code != 0:
            await sb.close()
            raise PatchApplyError(f"{label}: git apply 失败：{(r.stderr or r.stdout)[-400:]}")
    return sb


class PatchApplyError(RuntimeError):
    pass


def _env(backend: SandboxBackend) -> tuple[Literal["verified", "unverified"], str | None]:
    caps = getattr(backend, "capabilities", None)
    if caps is not None and caps.clean_env:
        return "verified", None
    return "unverified", "no_sandbox"


async def _run(
    sb: Sandbox, cmd: str, scope: Scope, timeout_s: int, label: str | None = None
) -> tuple[TestRun, set[str], str]:
    """跑一次测试命令；pytest 时加 --junitxml 拿到失败用例 id。返回 (TestRun, 失败 id 集合, 输出尾部)。"""
    label = label or scope
    junit = f"{_tw_dir(sb)}/verify-{label}.xml"
    is_pytest = "pytest" in cmd
    run_cmd = f"{cmd} --junitxml={shlex.quote(junit)}" if is_pytest else cmd
    if is_pytest:
        await sb.write_file(junit, b"")
    r = await sb.exec(run_cmd, timeout_s=timeout_s)
    rep = parse_junit(await sb.read_file(junit)) if is_pytest else None
    failed_ids = {f.nodeid for f in rep.failures} if rep else ({"<command>"} if r.exit_code else set())
    tail = (r.stdout + r.stderr)[-2000:]
    if rep is not None:
        passed = max(0, rep.tests - rep.failed - rep.errors - rep.skipped)
        run = TestRun(scope=scope, command=cmd, passed=passed, failed=rep.failed, skipped=rep.skipped,
                      errors=rep.errors, duration_s=r.duration_ms / 1000, log_ref=f"{sb.id}:{label}")  # fmt: skip
    else:
        run = TestRun(scope=scope, command=cmd, passed=int(r.exit_code == 0), failed=int(r.exit_code != 0),
                      skipped=0, duration_s=r.duration_ms / 1000, log_ref=f"{sb.id}:{label}")  # fmt: skip
    if r.timed_out:
        failed_ids.add("<timeout>")
    return run, failed_ids, tail


async def rerun_repro(
    backend: SandboxBackend, spec: SandboxSpec, patch: str, repro: ReproRef | None, *, timeout_s: int = 600
) -> RerunResult:
    clean, why = _env(backend)
    res = RerunResult(repro_status="not_applicable", clean_env=clean, unverified_reason=why)
    if repro is None:
        res.notes.append("没有复现测试（repro_status = not_applicable）：证据改为行为对比 / 静态论证，风险至少 L1")
        return res
    try:
        base = await _fresh(backend, spec, only_test_files(patch), "repro_base")
    except PatchApplyError as e:
        res.repro_status = "inconclusive"
        res.notes.append(str(e))
        return res
    try:
        run_b, fail_b, res.logs["repro_base"] = await _run(base, repro.cmd, "repro_base", timeout_s)
    finally:
        await base.close()
    try:
        fixed = await _fresh(backend, spec, patch, "repro_patched")
    except PatchApplyError as e:
        res.repro_status = "failed"
        res.notes.append(str(e))
        return res
    try:
        run_p, fail_p, res.logs["repro_patched"] = await _run(fixed, repro.cmd, "repro_patched", timeout_s)
    finally:
        await fixed.close()
    res.test_runs += [run_b, run_p]
    if fail_p:
        res.repro_status = "failed"
        res.notes.append(f"修复后复现测试仍失败：{sorted(fail_p)[:5]}")
    elif not fail_b:
        res.repro_status = "inconclusive"
        res.notes.append("复现测试在基线上就通过——它没有证明 bug 存在")
    else:
        res.repro_status = "reproduced"
    return res


async def regression(
    backend: SandboxBackend, spec: SandboxSpec, patch: str, test_cmd: str, *, timeout_s: int = 900
) -> tuple[TestRun, RerunResult]:
    """全量（或给定范围）测试：基线 vs 修复后；新失败重跑 FLAKY_RERUNS 次判 flaky。"""
    clean, why = _env(backend)
    res = RerunResult(repro_status="not_applicable", clean_env=clean, unverified_reason=why)
    base = await _fresh(backend, spec, "", "full_base")
    try:
        _, fail_b, res.logs["full_base"] = await _run(base, test_cmd, "full", timeout_s, label="full_base")
    finally:
        await base.close()
    sb = await _fresh(backend, spec, patch, "full")
    try:
        run, fail_p, res.logs["full"] = await _run(sb, test_cmd, "full", timeout_s)
        new = sorted(fail_p - fail_b)
        flaky: list[str] = []
        for nodeid in new:
            if nodeid.startswith("<"):
                continue
            for i in range(FLAKY_RERUNS):
                _, again, _ = await _run(sb, f"{test_cmd} {shlex.quote(nodeid)}", "full", timeout_s, label=f"rerun{i}")
                if nodeid not in again:
                    flaky.append(nodeid)
                    break
    finally:
        await sb.close()
    run.new_failures = [x for x in new if x not in flaky]
    run.flaky = flaky
    pre = sorted(fail_b & fail_p)
    if pre:
        res.notes.append(f"{len(pre)} 个失败在基线上就存在，不计回归")
    res.test_runs.append(run)
    return run, res
