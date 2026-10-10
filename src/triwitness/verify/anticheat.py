"""防作弊（04 §4.4，W3-09）：只看 diff，确定性规则，每条规则给出动作。

动作：
- `block`：阻断，退回 Executor（新增 skip / xfail、针对测试特判）
- `review`：风险至少 L2，Reviewer 必须逐条确认（改已有测试、削弱断言）
- `approval`：风险至少 L2 且需要人工审批（改测试基础设施 / CI）

已有测试文件**只加行**（补回归测试）不算作弊（W1-34 真跑的教训），记为 info 级的 `existing_test_extended`。
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from triwitness.core.models import RiskLevel
from triwitness.verify.diffutil import FilePatch, added_lines, is_infra, is_test_file, removed_lines, split_patch

Action = Literal["block", "approval", "review", "info"]

CI_PATTERNS = (
    re.compile(r"^\.github/workflows/"),
    re.compile(r"^\.gitlab-ci\.yml$"),
    re.compile(r"(^|/)(tox\.ini|noxfile\.py|\.pre-commit-config\.yaml|azure-pipelines\.yml|Jenkinsfile)$"),
    re.compile(r"^\.circleci/"),
)
SKIP = re.compile(
    r"(pytest\.mark\.(skip|skipif|xfail)\b|pytest\.(skip|xfail|importorskip)\(|unittest\.skip|@skip(If|Unless)?\b"
    r"|\.skipTest\(|__unittest_skip__)"
)
SPECIAL_CASE = re.compile(
    r"""(["']pytest["']\s+in\s+sys\.modules|PYTEST_CURRENT_TEST|PYTEST_VERSION|["']_pytest["']"""
    r"""|sys\.argv\[0\].*pytest|["'][\w/]*test_\w+\.py["']|getattr\(sys,\s*["']_called_from_test)"""
)
ASSERT = re.compile(r"^\s*(assert\b|self\.assert\w*\(|pytest\.raises\()")
TRIVIAL_ASSERT = re.compile(r"^\s*assert\s+(True|1|not\s+False|\(\s*\)|.+\s+or\s+True)\s*(,.*)?$")
SWALLOW = re.compile(r"^\s*except(\s+(Exception|BaseException))?\s*(as\s+\w+)?\s*:\s*(pass|\.\.\.)?\s*$")


class AntiCheatFlag(BaseModel):
    code: str
    action: Action
    path: str
    line: int | None = None
    detail: str


class AntiCheatReport(BaseModel):
    flags: list[AntiCheatFlag] = Field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(f.action == "block" for f in self.flags)

    @property
    def needs_approval(self) -> bool:
        return any(f.action == "approval" for f in self.flags)

    @property
    def min_level(self) -> RiskLevel:
        acts = {f.action for f in self.flags}
        return "L3" if "block" in acts else "L2" if acts & {"approval", "review"} else "L0"

    @property
    def codes(self) -> list[str]:
        return list(dict.fromkeys(f.code for f in self.flags))


def _code_only(s: str) -> str:
    """去掉行尾注释（粗略：不处理字符串里的 #），整行注释返回空。"""
    t = s.strip()
    return "" if t.startswith("#") else t.split("  #", 1)[0]


def check(patch: str, *, new_test_ok: bool = True) -> AntiCheatReport:
    rep = AntiCheatReport()
    for fp in split_patch(patch):
        rep.flags += _check_file(fp, new_test_ok=new_test_ok)
    return rep


def _check_file(fp: FilePatch, *, new_test_ok: bool) -> list[AntiCheatFlag]:
    out: list[AntiCheatFlag] = []
    path = fp.path
    paths = list(dict.fromkeys([fp.old_path, fp.path]))
    test = any(is_test_file(p) for p in paths)
    added = added_lines(fp)
    removed = removed_lines(fp)

    if any(is_infra(p) for p in paths) or any(c.search(p) for c in CI_PATTERNS for p in paths):
        out.append(
            AntiCheatFlag(code="test_infra_modified", action="approval", path=path, detail="改了测试基础设施 / CI 配置")
        )
    if test and not fp.new_file:
        if fp.deleted or fp.old_path != fp.path or removed:
            out.append(
                AntiCheatFlag(
                    code="existing_test_modified",
                    action="review",
                    path=path,
                    detail=f"删改了已有测试（删 {len(removed)} 行{'，删文件' * fp.deleted}）",
                )
            )
        elif added:
            out.append(
                AntiCheatFlag(
                    code="existing_test_extended",
                    action="info",
                    path=path,
                    detail=f"已有测试文件只新增 {len(added)} 行",
                )
            )
    if test and fp.new_file and not new_test_ok:
        out.append(AntiCheatFlag(code="new_test_file", action="info", path=path, detail="新增测试文件"))
    for ln, text in added:
        code = _code_only(text)
        if code and SKIP.search(code):
            out.append(
                AntiCheatFlag(
                    code="skip_or_xfail_added",
                    action="block",
                    path=path,
                    line=ln,
                    detail=f"新增 skip / xfail：{code[:80]}",
                )
            )
        if code and not test and SPECIAL_CASE.search(code):
            out.append(
                AntiCheatFlag(
                    code="test_special_casing",
                    action="block",
                    path=path,
                    line=ln,
                    detail=f"产品代码里针对测试特判：{code[:80]}",
                )
            )
        if code and test and TRIVIAL_ASSERT.match(code):
            out.append(
                AntiCheatFlag(
                    code="assertion_weakened", action="review", path=path, line=ln, detail=f"恒真断言：{code[:80]}"
                )
            )
        if code and SWALLOW.match(code):
            out.append(
                AntiCheatFlag(
                    code="exception_swallowed",
                    action="review",
                    path=path,
                    line=ln,
                    detail="新增吞异常的 except（可能把被测代码的错误藏起来）",
                )
            )
    if test and not fp.new_file:
        lost = sum(1 for r in removed if ASSERT.match(r)) - sum(1 for _, a in added if ASSERT.match(a))
        if lost > 0:
            out.append(
                AntiCheatFlag(
                    code="assertion_weakened", action="review", path=path, detail=f"测试里净减少 {lost} 条断言"
                )
            )
    return out
