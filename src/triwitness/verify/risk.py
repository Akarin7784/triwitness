"""风险分级（04 §4.6，spec 009，W3-11）：因子计分 → L0–L3；硬下限（阻断、无沙箱复跑）单独记一条原因。"""

from __future__ import annotations

import fnmatch
import posixpath
import re
from functools import cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from triwitness.config import resource_root
from triwitness.core.models import RiskFactor, RiskLevel
from triwitness.verify.anticheat import AntiCheatReport
from triwitness.verify.diffutil import added_lines, changed_line_count, is_test_file, removed_lines, split_patch

DEFAULT_POLICY = resource_root() / "configs" / "policies" / "risk.yaml"
ORDER: tuple[RiskLevel, ...] = ("L0", "L1", "L2", "L3")
ReproStatus = Literal["reproduced", "not_applicable", "inconclusive", "failed"]
_PUBLIC_DEF = re.compile(r"^(?:async\s+)?def\s+([A-Za-z]\w*)\s*\((.*)$|^class\s+([A-Za-z]\w*)\b(.*)$")


class RiskPolicy(BaseModel):
    levels: dict[str, int]
    factors: dict[str, int]
    coverage_threshold: float = 0.5
    verifier_confidence_threshold: float = 0.6
    sensitive_paths: list[str] = Field(default_factory=list)
    build_files: list[str] = Field(default_factory=list)
    floors: dict[str, RiskLevel] = Field(default_factory=dict)


@cache
def load_policy(path: Path = DEFAULT_POLICY) -> RiskPolicy:
    return RiskPolicy.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


class RiskInputs(BaseModel):
    patch: str
    anticheat: AntiCheatReport = Field(default_factory=AntiCheatReport)
    repro_status: ReproStatus = "reproduced"
    verdict: Literal["pass", "fail", "inconclusive"] = "pass"
    verifier_confidence: float = 1.0
    review_major_open: int = 0
    coverage_changed: float | None = None  # 改动行覆盖率（0–1）；None = 没有数据
    bandit_medium_high: int = 0
    clean_env: Literal["verified", "unverified"] = "verified"
    claim_flags: list[str] = Field(default_factory=list)
    secrets_found: int = 0  # 静态检查的密钥扫描命中数


class RiskResult(BaseModel):
    score: int
    level: RiskLevel
    factors: list[RiskFactor]

    @property
    def needs_human(self) -> bool:
        return self.level == "L3"


def level_of(score: int, policy: RiskPolicy) -> RiskLevel:
    lv: RiskLevel = "L0"
    for name in ORDER[1:]:
        if score >= policy.levels[name]:
            lv = name
    return lv


def _max(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    return a if ORDER.index(a) >= ORDER.index(b) else b


def public_api_changes(patch: str) -> list[str]:
    """非测试文件里，被删掉或改了签名的公开 def / class（名字不以 _ 开头、行首定义，即模块级）。"""
    out: list[str] = []
    for fp in split_patch(patch):
        if not fp.path.endswith(".py") or is_test_file(fp.path) or fp.new_file:
            continue
        added = {_sig(t) for _, t in added_lines(fp)} - {None}
        for r in removed_lines(fp):
            s = _sig(r)
            if s is not None and s not in added:
                out.append(f"{fp.path}:{s[0]}")
    return out


def _sig(line: str) -> tuple[str, str] | None:
    m = _PUBLIC_DEF.match(line)
    if not m:
        return None
    return (m.group(1) or m.group(3), re.sub(r"\s+", "", m.group(2) or m.group(4) or ""))


def _matches(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(posixpath.basename(path), g) for g in globs)


def assess(inp: RiskInputs, policy: RiskPolicy | None = None) -> RiskResult:
    p = policy or load_policy()
    pts = p.factors
    factors: list[RiskFactor] = []

    def add(code: str, detail: str) -> None:
        factors.append(RiskFactor(code=code, points=pts[code], detail=detail))

    paths = [fp.path for fp in split_patch(inp.patch)]
    n = changed_line_count(inp.patch)
    if n > 500:
        add("lines_over_500", f"改动 {n} 行（> 500）")
    elif n > 200:
        add("lines_over_200", f"改动 {n} 行（> 200）")
    sens = [x for x in paths if any(k in x.lower() for k in p.sensitive_paths)]
    if sens:
        add("sensitive_path", "触及敏感路径：" + ", ".join(sens[:3]))
    build = [x for x in paths if _matches(x, p.build_files)]
    if build:
        add("ci_build_deps", "改了 CI / 构建 / 依赖文件：" + ", ".join(build[:3]))
    mod = [f.path for f in inp.anticheat.flags if f.code == "existing_test_modified"]
    if mod:
        add("existing_test_modified", "删改已有测试：" + ", ".join(dict.fromkeys(mod)))
    if inp.coverage_changed is not None and inp.coverage_changed < p.coverage_threshold:
        add("low_coverage", f"改动行覆盖率 {inp.coverage_changed:.0%}（< {p.coverage_threshold:.0%}）")
    if inp.repro_status != "reproduced":
        add("repro_not_reproduced", f"复现状态 {inp.repro_status}")
    if inp.verdict == "inconclusive" or inp.verifier_confidence < p.verifier_confidence_threshold:
        add("verifier_uncertain", f"Verifier {inp.verdict}，置信度 {inp.verifier_confidence:.2f}")
    if inp.review_major_open:
        add("review_major_open", f"Reviewer 有 {inp.review_major_open} 个未解决的 major / blocker")
    api = public_api_changes(inp.patch)
    if api:
        add("public_api_changed", "公共 API 签名变化：" + ", ".join(api[:3]))
    if inp.bandit_medium_high:
        add("security_scan", f"bandit 中高告警 {inp.bandit_medium_high} 条")
    if inp.claim_flags:
        add("claim_audit", "声明审计：" + ", ".join(inp.claim_flags))

    score = min(100, sum(f.points for f in factors))
    level = level_of(score, p)
    floors: list[tuple[str, RiskLevel, str]] = []
    ac = inp.anticheat
    if ac.blocked:
        floors.append(("anticheat_block", p.floors.get("anticheat_block", "L3"),
                       "命中阻断规则：" + ", ".join(f.code for f in ac.flags if f.action == "block")))  # fmt: skip
    elif ac.min_level == "L2":
        floors.append(("anticheat_review", p.floors.get("anticheat_review", "L2"),
                       "防作弊需复核：" + ", ".join(c for c in ac.codes if c != "existing_test_extended")))  # fmt: skip
    if inp.secrets_found:
        floors.append(("secrets", p.floors.get("secrets", "L3"), f"diff 里疑似有密钥（{inp.secrets_found} 处）"))
    if inp.clean_env == "unverified":
        floors.append(("clean_env_unverified", p.floors.get("clean_env_unverified", "L2"),
                       "未在干净环境复跑（无沙箱），禁止自动合并"))  # fmt: skip
    if inp.repro_status != "reproduced":
        floors.append(("repro_not_reproduced", p.floors.get("repro_not_reproduced", "L1"), "没有可复现的证据"))
    for code, floor, detail in floors:
        if ORDER.index(floor) > ORDER.index(level):
            factors.append(RiskFactor(code=f"floor:{code}", points=0, detail=f"{detail} → 至少 {floor}"))
            level = _max(level, floor)
    return RiskResult(score=score, level=level, factors=factors)
