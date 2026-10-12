"""Skill A/B 门禁（spec 013 §5.3，W6-07）：候选 Skill 只有在 held-out 任务上**配对**比较胜出才合入。

- held-out 选择（防泄漏）：
  - 永远排除来源任务本身；来源是评测任务时只取 created_at **晚于**它的任务（时间切分，`after`）。
    来源是日常 run（dogfood）时 Skill 不可能见过这些公开任务的答案，不加时间限制，只排除来源。
  - scope=repo：同一仓库（按 repo_key 归一）；scope=global：任意仓库。
  - 少于 min_tasks 个就判 insufficient_heldout，不跑（结论没有意义）。
- 设计：两臂 A（无 Skill）/ B（只注入这个 Skill，见 MemoryContext.with_skills），同任务同次数配对，默认 2 次。
- 判定：B 的成功率 > A（至少 min_gain）且 B 的单次成本 ≤ A ×（1 + cost_tolerance）才合入；
  McNemar 精确检验 p ≥ 0.05 时标“功效不足”（结论仍按点估计给出，报告里写明，见 spec 013 开放问题 Q4）。
- 真跑由 `scripts/skill_gate.py` 驱动（EvalRunner + 高峰闸门 + 账本 + 总额上限）；这里的 `run_gate` 接受注入的
  runner，单元测试与 `tw memory gate --fake` 用假 runner，不花钱。
"""

from __future__ import annotations

import hashlib
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from triwitness.eval.ablation import McNemar, mcnemar, paired_diff_ci, wilson
from triwitness.memory.skills import SkillPool
from triwitness.memory.store import repo_key

DEFAULT_SUITE = "ext-reserve"
MIN_TASKS = 8
MAX_TASKS = 12
REPEATS = 2
PER_RUN_CNY = 0.08  # ext 任务单次的历史均值量级（deepseek-flash，闲时）；真跑前脚本会用历史数据重估
ARMS = ("without", "with")


@dataclass(frozen=True)
class HeldoutTask:
    id: str
    repo: str
    created_at: str


def load_tasks(suite: str = DEFAULT_SUITE) -> list[HeldoutTask]:
    from triwitness.eval.suites import suite_dirs

    out = []
    for d in suite_dirs(suite):
        meta = tomllib.loads((d / "task.toml").read_text(encoding="utf-8")).get("metadata", {})
        repo, created = str(meta.get("repo") or ""), str(meta.get("created_at") or "")
        out.append(HeldoutTask(id=d.name, repo=repo, created_at=created))
    return out


@dataclass
class Selection:
    tasks: list[HeldoutTask]
    scope: str
    eligible: int
    min_tasks: int
    excluded: list[str] = field(default_factory=list)

    @property
    def sufficient(self) -> bool:
        return len(self.tasks) >= self.min_tasks


def select_heldout(tasks: list[HeldoutTask], *, scope: str, source_repo: str = "", after: str = "",
                   exclude: list[str] | tuple[str, ...] = (), min_tasks: int = MIN_TASKS, max_tasks: int = MAX_TASKS,
                   seed: str = "tw-gate") -> Selection:  # fmt: skip
    """时间切分 + 仓库范围；确定性抽样（同一 seed 同一结果）。"""
    if scope not in ("repo", "global"):
        raise ValueError("scope 只能是 repo / global")
    key = repo_key(source_repo) if source_repo else ""
    ex = set(exclude)
    eligible = [t for t in tasks if t.id not in ex and (not after or t.created_at > after)
                and (scope == "global" or (key and repo_key(t.repo) == key))]  # fmt: skip
    order = sorted(eligible, key=lambda t: hashlib.sha256(f"{seed}:{t.id}".encode()).hexdigest())
    return Selection(tasks=order[:max_tasks], scope=scope, eligible=len(eligible), min_tasks=min_tasks,
                     excluded=sorted(ex))  # fmt: skip


@dataclass
class GatePlan:
    skill: str
    version: int
    scope: str
    suite: str
    tasks: list[str]
    repeats: int = REPEATS
    per_run_cny: float = PER_RUN_CNY
    sufficient: bool = True
    note: str = ""

    @property
    def runs(self) -> int:
        return len(self.tasks) * self.repeats * len(ARMS)

    @property
    def est_cny(self) -> float:
        return round(self.runs * self.per_run_cny, 2)


def plan_gate(pool: SkillPool, name: str, version: int, *, suite: str = DEFAULT_SUITE, source_repo: str = "",
              after: str = "", exclude: list[str] | None = None, repeats: int = REPEATS,
              min_tasks: int = MIN_TASKS, max_tasks: int = MAX_TASKS, per_run_cny: float = PER_RUN_CNY,
              tasks: list[HeldoutTask] | None = None) -> GatePlan:  # fmt: skip
    sk = pool.get(name, version)
    scope = sk.scope
    sel = select_heldout(tasks if tasks is not None else load_tasks(suite), scope=scope, source_repo=source_repo,
                         after=after, exclude=exclude or [],
                         min_tasks=min_tasks, max_tasks=max_tasks)  # fmt: skip
    note = "" if sel.sufficient else (f"insufficient_heldout：scope={scope} 只有 {sel.eligible} 个合格任务"
                                      f"（需要 ≥ {min_tasks}）")  # fmt: skip
    return GatePlan(skill=name, version=version, scope=scope, suite=suite, tasks=[t.id for t in sel.tasks],
                    repeats=repeats, per_run_cny=per_run_cny, sufficient=sel.sufficient, note=note)  # fmt: skip


@dataclass
class Outcome:
    solved: bool
    cost_cny: float = 0.0


Runner = Callable[[str, str, int], Outcome]  # (task_id, arm, repeat) -> Outcome


@dataclass
class GateResult:
    results: dict[str, dict[str, bool]]  # arm -> {task#rep: solved}
    costs: dict[str, float]  # arm -> 总花费


def run_gate(plan: GatePlan, runner: Runner) -> GateResult:
    res: dict[str, dict[str, bool]] = {a: {} for a in ARMS}
    cost = dict.fromkeys(ARMS, 0.0)
    for t in plan.tasks:
        for r in range(1, plan.repeats + 1):
            for a in ARMS:
                o = runner(t, a, r)
                res[a][f"{t}#{r}"] = o.solved
                cost[a] += o.cost_cny
    return GateResult(res, {a: round(c, 4) for a, c in cost.items()})


@dataclass
class Thresholds:
    min_gain: float = 0.0  # B − A 成功率差必须 > 它
    cost_tolerance: float = 0.05  # B 的单次成本 ≤ A ×（1 + 它）
    alpha: float = 0.05


@dataclass
class Decision:
    promote: bool
    reason: str
    rate_a: float
    rate_b: float
    n: int
    cost_a: float
    cost_b: float
    test: McNemar
    diff_ci: tuple[float, float] | None
    underpowered: bool

    def summary(self) -> dict[str, Any]:
        d = asdict(self)
        d["test"] = asdict(self.test)
        return d


def decide(result: GateResult, th: Thresholds | None = None) -> Decision:
    th = th or Thresholds()
    a, b = result.results["without"], result.results["with"]
    common = sorted(set(a) & set(b))
    xa, xb = [a[k] for k in common], [b[k] for k in common]
    n = len(common)
    ra = sum(xa) / n if n else 0.0
    rb = sum(xb) / n if n else 0.0
    ca = result.costs["without"] / n if n else 0.0
    cb = result.costs["with"] / n if n else 0.0
    t = mcnemar(xa, xb)
    ci = paired_diff_ci(xa, xb) if n else None
    under = t.p_exact >= th.alpha
    if n == 0:
        ok, why = False, "没有配对结果"
    elif rb - ra <= th.min_gain:
        ok, why = False, f"成功率没有提升（A {ra:.0%} → B {rb:.0%}）"
    elif ca > 0 and cb > ca * (1 + th.cost_tolerance):
        ok, why = False, f"成功率提升但单次成本超出容差（¥{ca:.4f} → ¥{cb:.4f}，容差 {th.cost_tolerance:.0%}）"
    else:
        ok, why = True, f"成功率 A {ra:.0%} → B {rb:.0%}，单次成本 ¥{ca:.4f} → ¥{cb:.4f}"
    if ok and under:
        why += f"（McNemar p={t.p_exact:.3f}，功效不足）"
    return Decision(promote=ok, reason=why, rate_a=round(ra, 4), rate_b=round(rb, 4), n=n, cost_a=round(ca, 4),
                    cost_b=round(cb, 4), test=t, diff_ci=ci, underpowered=under)  # fmt: skip


def render_report(plan: GatePlan, result: GateResult | None, dec: Decision | None, *, mode: str = "real") -> str:
    lines = [f"# Skill 门禁：{plan.skill} v{plan.version}", "",
             f"- 方式：{'假 runner（不花钱，只验证流程）' if mode == 'fake' else '真跑'}",
             f"- held-out：{plan.suite}，scope={plan.scope}，{len(plan.tasks)} 个任务 × {plan.repeats} 次 × 2 臂"
             f" = {plan.runs} 次运行（预估 ¥{plan.est_cny}）",
             f"- 任务：{', '.join(plan.tasks) or '无'}"]  # fmt: skip
    if not plan.sufficient:
        lines += ["", f"**未运行**：{plan.note}"]
        return "\n".join(lines) + "\n"
    if result is None or dec is None:
        return "\n".join(lines) + "\n"
    lo, hi = wilson(round(dec.rate_a * dec.n), dec.n), wilson(round(dec.rate_b * dec.n), dec.n)
    ci = f"[{dec.diff_ci[0]:+.0%}, {dec.diff_ci[1]:+.0%}]" if dec.diff_ci else "—"
    lines += ["", "| 臂 | n | 成功率 | Wilson 95% | 单次成本 |", "|---|---|---|---|---|",
              f"| A 无 Skill | {dec.n} | {dec.rate_a:.0%} | [{lo[0]:.0%}, {lo[1]:.0%}] | ¥{dec.cost_a:.4f} |",
              f"| B 有 Skill | {dec.n} | {dec.rate_b:.0%} | [{hi[0]:.0%}, {hi[1]:.0%}] | ¥{dec.cost_b:.4f} |",
              "", f"- 配对差 B−A：{dec.rate_b - dec.rate_a:+.0%}，bootstrap 95% CI {ci}",
              f"- McNemar：A 胜 B 败 {dec.test.b}，B 胜 A 败 {dec.test.c}，精确 p = {dec.test.p_exact}",
              f"- 结论：**{'合入' if dec.promote else '不合入'}** —— {dec.reason}"]  # fmt: skip
    return "\n".join(lines) + "\n"


def apply_decision(pool: SkillPool, plan: GatePlan, dec: Decision | None, report: str) -> str:
    """把门禁结论写进池：通过 → promote；未通过 / held-out 不足 → reject（附报告）。返回新状态。"""
    if dec is not None and dec.promote:
        pool.promote(plan.skill, plan.version, gate_report=report, summary=dec.summary())
        return "active"
    reason = plan.note if not plan.sufficient else (dec.reason if dec else "未运行")
    pool.reject(plan.skill, plan.version, reason=reason, gate_report=report)
    return "rejected"


__all__ = [
    "ARMS",
    "DEFAULT_SUITE",
    "Decision",
    "GatePlan",
    "GateResult",
    "HeldoutTask",
    "Outcome",
    "Selection",
    "Thresholds",
    "apply_decision",
    "decide",
    "load_tasks",
    "plan_gate",
    "render_report",
    "run_gate",
    "select_heldout",
]
