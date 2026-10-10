"""完成声明审计（04 §3.3 / §4.5 的确定性部分，W3）：不跑代码，只看 Issue、FinishReport 与补丁。

来源：W1-34 真跑的 swe-crosstl-257——Issue 只写“给 translator 的 lexer 加 token”，没点名；Agent 自己写的复现测试
断言 LBRACKET / RBRACKET 并通过，隐藏测试要的却是 UNSIGNED_INT。复现“通过”不等于“解决了 Issue”。

信号（每条都给出原因，写进证据包）：
- `repro_missing`：声明里没有复现测试，或复现文件不在补丁里
- `repro_not_tied_to_issue`：复现测试断言的具体值（字符串字面量）在 Issue 里一个都没出现
- `issue_underspecified`：Issue 没有任何可执行的验收信号（报错 / 期望行为 / 代码示例 / 具体标识符）
- `claim_contradicts_open_risks`：自述风险里承认“未覆盖 / 不确定”，却声明测试通过且置信度 ≥ 0.8
判定：声明测试未通过 → fail；有上述任一信号 → insufficient_evidence（Evidence 里记为 inconclusive）；否则 pass
（只是“声明层面可信”，最终结论还要看干净环境复跑与回归）。
"""

from __future__ import annotations

import ast
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from triwitness.core.models import FinishReport
from triwitness.verify.diffutil import added_lines, split_patch

CONFIDENT = 0.8
_UNCERTAIN = re.compile(
    r"not covered|not tested|untested|unsure|uncertain|may not|might not|could not verify|if the hidden tests"
    r"|not (?:fully )?verified|未覆盖|不确定|未验证|可能不",
    re.I,
)
_SPEC_WORDS = re.compile(
    r"traceback|error|exception|raises?\b|expected|should|instead|actual|returns?\b|crash|fails?\b|bug"
    r"|应该|期望|预期|报错|异常|崩溃|返回|错误",
    re.I,
)
_BACKTICK = re.compile(r"`([^`\n]+)`")
_PATHLIKE = re.compile(r"^[\w./-]+\.(py|md|txt|toml|cfg|ini|ya?ml|json)$")


class ClaimVerdict(BaseModel):
    verdict: Literal["pass", "fail", "insufficient_evidence"]
    flags: list[str] = Field(default_factory=list)
    reasons: dict[str, str] = Field(default_factory=dict)

    @property
    def evidence_verdict(self) -> Literal["pass", "fail", "inconclusive"]:
        return "inconclusive" if self.verdict == "insufficient_evidence" else self.verdict


def asserted_literals(source: str) -> set[str]:
    """复现测试里 assert 语句（含 assert 内的比较 / any(...)）用到的字符串字面量；解析失败时退回正则。"""
    out: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {
            m
            for line in source.splitlines()
            if "assert" in line
            for m in re.findall(r"""["']([^"'\n]{3,})["']""", line)
        }
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and len(sub.value.strip()) >= 3:
                    out.add(sub.value.strip())
    return out


def issue_is_underspecified(issue: str) -> bool:
    if "```" in issue or ">>>" in issue or _SPEC_WORDS.search(issue):
        return False
    concrete = [s for s in _BACKTICK.findall(issue) if not _PATHLIKE.match(s.strip())]
    # 反引号里像代码的东西（调用、赋值、下划线 / 大写标识符）才算具体；单个小写词（`lexer`）不算
    return not any(re.search(r"[()=_.\[]|[A-Z]", s) for s in concrete)


def verify_claim(*, issue: str, claim: FinishReport | dict[str, Any], patch: str) -> ClaimVerdict:
    c = claim if isinstance(claim, FinishReport) else FinishReport.model_validate(claim)
    v = ClaimVerdict(verdict="pass")

    def flag(code: str, why: str) -> None:
        v.flags.append(code)
        v.reasons[code] = why

    files = {fp.path: fp for fp in split_patch(patch)}
    repro = files.get(c.repro.path) if c.repro else None
    if repro is None:
        flag("repro_missing", "声明里没有复现测试，或复现文件不在补丁里")
    else:
        src = "\n".join(t for _, t in added_lines(repro))
        lits = asserted_literals(src)
        low = issue.lower()
        if lits and not any(x.lower() in low for x in lits):
            flag("repro_not_tied_to_issue",
                 f"复现测试断言的值 {sorted(lits)[:5]} 在 Issue 里都没出现——复现的是 Agent 自己选的目标")  # fmt: skip
    if issue_is_underspecified(issue):
        flag("issue_underspecified", "Issue 没有报错、期望行为、代码示例或具体标识符；应先补验收标准或转人工")
    risky = [r for r in c.open_risks if _UNCERTAIN.search(r)]
    if risky and c.tests_passed and c.confidence >= CONFIDENT:
        flag("claim_contradicts_open_risks",
             f"自述风险承认未覆盖 / 不确定（{risky[0][:80]}…），却声明测试通过、置信度 {c.confidence:.2f}")  # fmt: skip
    if not c.tests_passed:
        v.verdict = "fail"
    elif v.flags:
        v.verdict = "insufficient_evidence"
    return v
