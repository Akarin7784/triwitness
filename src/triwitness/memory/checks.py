"""候选记忆 / Skill 的静态检查（spec 013 §6，W6-06；04 §7.1 防投毒）。

每条规则独立、可单测（正反例见 tests/unit/memory/test_checks.py）：
- length：事实 ≤ 300 字符、经验 ≤ 800、Skill 描述 ≤ 1024（Agent Skills 规范）、正文 ≤ 12000 字符且 ≤ 500 行
- secret：沿用轨迹脱敏（core/redact）与任务加固（task_hardening.redact_secrets）的规则；命中即拒，**不存脱敏版**
- bypass：要求忽略之前的指令 / 冒充系统 / 关闭检查与权限 / 跳过或删除测试 / 绕过钩子
- exfiltration：把数据发到外部（curl/wget 上传、nc、scp、粘贴站、“发送到 …”）
- task_answer：含来源任务补丁里的新增代码行、diff 片段、或来源任务的 fail_to_pass 测试名（防“学到的是答案”）
- skill_name：Skill 名符合 Agent Skills 规范（小写字母数字与单个连字符，1–64）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["fact", "episode", "skill"]

LIMITS = {"fact": 300, "episode": 800, "skill_description": 1024, "skill_body": 12_000, "skill_lines": 500}
_NAME = re.compile(r"^(?!-)(?!.*--)[a-z0-9-]{1,64}(?<!-)$")

_BYPASS = [
    (
        r"(?i)\bignore\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?)",
        "要求忽略之前的指令",
    ),
    (r"(?i)\bdisregard\s+(all\s+)?(previous|prior|above|system)\b", "要求无视之前 / 系统指令"),
    (r"忽略(之前|以上|上面|前面|先前)(的|所有)?(指令|规则|提示|要求)", "要求忽略之前的指令"),
    (r"(无视|不要理会)(系统|之前|以上)(提示|指令|规则)", "要求无视系统指令"),
    (r"(?i)\byou\s+are\s+now\b|\bnew\s+system\s+prompt\b|^\s*system\s*:", "冒充系统 / 改写身份"),
    (r"(?i)--no-verify\b|core\.hooksPath\s*/dev/null|\bSKIP=\S+\s+git\s+commit", "绕过 git 钩子"),
    (
        r"(?i)\b(disable|turn\s+off|bypass|skip)\s+(the\s+)?(verif\w*|checks?|sandbox|permissions?|review\w*|guard\w*)",
        "关闭检查 / 沙箱 / 权限 / 评审",
    ),
    (r"(关闭|绕过|跳过|禁用)(所有)?(检查|校验|验证|沙箱|权限|评审|审批|安全)", "关闭检查 / 沙箱 / 权限 / 评审"),
    (
        r"(?i)\b(delete|remove|skip|xfail)\s+(the\s+)?(failing\s+)?tests?\b|@pytest\.mark\.skip|pytest\.skip\(",
        "跳过或删除测试",
    ),
    (r"(删除|删掉|跳过|注释掉)(失败的|报错的)?测试", "跳过或删除测试"),
    (r"(?i)full[_\s-]?access|dangerously|--yolo\b|chmod\s+-R\s+777", "要求提升权限"),
    (r"(?i)\b(always|just)\s+(say|report|claim)\s+(the\s+)?tests?\s+(pass|passed)", "要求谎报测试结果"),
]
_EXFIL = [
    (r"(?i)\bcurl\b[^\n]*\s(-d|--data\S*|-F|--form|-T|--upload-file)\s", "curl 上传数据"),
    (r"(?i)\bwget\b[^\n]*--post-(data|file)", "wget 上传数据"),
    (r"(?i)\b(nc|ncat|netcat)\s+[\w.-]+\s+\d{2,5}\b", "nc 外连"),
    (r"(?i)\bscp\s+\S+\s+\S+@\S+:", "scp 到远端"),
    (r"(?i)pastebin\.com|transfer\.sh|webhook\.site|requestbin|ngrok\.io", "粘贴站 / 回调站"),
    (
        r"(?i)\b(send|upload|post|exfiltrate)\s+(the\s+)?(env|environment|secrets?|keys?|tokens?|credentials?|\.env)\b",
        "外发环境变量 / 凭据",
    ),
    (r"(发送|上传|外发|贴到)[^\n。]{0,12}(环境变量|密钥|令牌|凭据|token|key)", "外发环境变量 / 凭据"),
    (r"(环境变量|密钥|令牌|凭据)[^\n。]{0,8}(发送|上传|外发|贴)(到|给)", "外发环境变量 / 凭据"),
]
_KEYWORD = r"(return|raise|if|elif|for|while|def|class|import|from|yield|assert|throw|const|let|var|fn|func)\b"
_DIFF = re.compile(r"(?m)^(@@ -\d+|\+\+\+ [ab]/|--- [ab]/|diff --git )")


@dataclass
class Finding:
    rule: str
    detail: str


@dataclass
class CheckResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    def reasons(self) -> list[str]:
        return [f"{f.rule}：{f.detail}" for f in self.findings]


def check_length(text: str, kind: Kind, *, description: str | None = None) -> list[Finding]:
    out: list[Finding] = []
    if kind == "skill":
        if description is not None and not 1 <= len(description) <= LIMITS["skill_description"]:
            out.append(Finding("length", f"Skill 描述 {len(description)} 字符（应为 1–{LIMITS['skill_description']}）"))
        if len(text) > LIMITS["skill_body"]:
            out.append(Finding("length", f"Skill 正文 {len(text)} 字符 > {LIMITS['skill_body']}"))
        if text.count("\n") + 1 > LIMITS["skill_lines"]:
            out.append(Finding("length", f"Skill 正文超过 {LIMITS['skill_lines']} 行"))
        if not text.strip():
            out.append(Finding("length", "Skill 正文为空"))
        return out
    limit = LIMITS[kind]
    if not text.strip():
        out.append(Finding("length", "内容为空"))
    elif len(text) > limit:
        out.append(Finding("length", f"{len(text)} 字符 > {limit}"))
    return out


def check_secret(text: str) -> list[Finding]:
    from triwitness.core.redact import redact_text
    from triwitness.eval.task_hardening import redact_secrets

    _, kinds = redact_secrets(text)
    if kinds:
        return [Finding("secret", "疑似密钥：" + "、".join(sorted(set(kinds))))]
    if redact_text(text) != text:
        return [Finding("secret", "疑似密钥（KEY / TOKEN / SECRET / Authorization 赋值）")]
    return []


def _scan(text: str, rules: list[tuple[str, str]], rule: str) -> list[Finding]:
    seen: set[str] = set()
    out: list[Finding] = []
    for pat, why in rules:
        if why not in seen and re.search(pat, text, flags=re.MULTILINE):
            seen.add(why)
            out.append(Finding(rule, why))
    return out


def check_bypass(text: str) -> list[Finding]:
    return _scan(text, _BYPASS, "bypass")


def check_exfiltration(text: str) -> list[Finding]:
    return _scan(text, _EXFIL, "exfiltration")


def _added_lines(patch: str, min_len: int) -> list[str]:
    out = []
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            s = line[1:].strip()
            code = re.search(r"[A-Za-z_]\w*\s*[(=.:\[]", s) or re.match(_KEYWORD, s)
            if len(s) >= min_len and code:  # 像代码的行
                out.append(s)
    return out


def check_task_answer(text: str, *, patch: str | None = None, tests: list[str] | None = None,
                      min_len: int = 25) -> list[Finding]:  # fmt: skip
    out: list[Finding] = []
    if _DIFF.search(text):
        out.append(Finding("task_answer", "含 diff 片段"))
    norm = " ".join(text.split())
    hits = [ln for ln in _added_lines(patch or "", min_len) if " ".join(ln.split()) in norm]
    if hits:
        out.append(Finding("task_answer", f"含来源补丁的代码行（{len(hits)} 行，如 `{hits[0][:60]}`）"))

    def _named(t: str) -> bool:
        leaf = t.split("::")[-1]
        return t in text or (len(leaf) > 12 and leaf in text)

    names = [t for t in (tests or []) if t and _named(t)]
    if names:
        out.append(Finding("task_answer", f"含来源任务的判分测试名（{names[0][:80]}）"))
    return out


def check_skill_name(name: str) -> list[Finding]:
    return [] if _NAME.match(name or "") else [Finding("skill_name", f"名称 {name!r} 不符合 Agent Skills 规范")]


def check_candidate(text: str, kind: Kind, *, name: str | None = None, description: str | None = None,
                    patch: str | None = None, tests: list[str] | None = None) -> CheckResult:  # fmt: skip
    """全部规则。Skill 的 text 是正文；描述与名称一起检查（描述也会进上下文）。"""
    whole = f"{description or ''}\n{text}" if kind == "skill" else text
    findings = check_length(text, kind, description=description)
    if kind == "skill":
        findings += check_skill_name(name or "")
    findings += check_secret(whole) + check_bypass(whole) + check_exfiltration(whole)
    findings += check_task_answer(whole, patch=patch, tests=tests)
    return CheckResult(findings)


__all__ = ["LIMITS", "CheckResult", "Finding", "check_bypass", "check_candidate", "check_exfiltration",
           "check_length", "check_secret", "check_skill_name", "check_task_answer"]  # fmt: skip
