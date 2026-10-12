"""W6-07：Skill A/B 门禁的真跑脚本（花钱；默认只出计划）。

    uv run python scripts/skill_gate.py plan   --repo <仓库> --skill <名> [--version N] [--after YYYY-MM-DD]
    uv run python scripts/skill_gate.py run    --repo <仓库> --skill <名> --version N --max-total-cny 4 --yes
    uv run python scripts/skill_gate.py report --repo <仓库> --skill <名> --version N --out <结果目录> [--apply]

- held-out：evals/suites/ext-reserve（SWE-rebench，加固过的备用集），选择规则见 triwitness.memory.gate；
- 两臂 gate-without / gate-with（with 臂只注入这一个 Skill，不带事实与经验），同任务 × 2 次配对；
- `run` 用 EvalRunner（deepseek-flash、全部记账本 category=skill-gate、总额上限、断点续跑），
  北京时间工作日高峰（9–12、14–18）不开跑（退出码 3）；必须显式 --yes，没有就只打印计划；
- `report`：配对判定（成功率提升且成本不超 5%）+ Markdown 报告；--apply 才把结论写进 Skill 池。
- 每周门禁预算约 ¥4（spec 013 §10 Q4，Eva 2026-10-12 已确认）；默认 `--max-total-cny 4`。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from triwitness.memory.gate import ARMS, GatePlan, GateResult, apply_decision, decide, plan_gate, render_report
from triwitness.memory.skills import SkillPool
from triwitness.memory.store import MemoryStore

CATEGORY = "skill-gate"
PEAK_EXIT = 3


def _plan(a: argparse.Namespace) -> tuple[MemoryStore, SkillPool, GatePlan]:
    st = MemoryStore.for_repo(str(Path(a.repo).resolve()))
    pool = SkillPool(st.root)
    plan = plan_gate(pool, a.skill, a.version, source_repo=str(Path(a.repo).resolve()), after=a.after,
                     exclude=a.exclude or [], repeats=a.repeats, min_tasks=a.min_tasks)  # fmt: skip
    return st, pool, plan


def cmd_plan(a: argparse.Namespace) -> int:
    _, _, plan = _plan(a)
    print(render_report(plan, None, None))
    return 0 if plan.sufficient else 1


def cmd_run(a: argparse.Namespace) -> int:
    from triwitness.cost.ledger import GlobalLedger
    from triwitness.eval.grade import Grader
    from triwitness.eval.runner import EvalRunner, RunConfig
    from triwitness.eval.suites import suite_dirs
    from triwitness.eval.task import load_task
    from triwitness.llm.gate import PeakGate
    from triwitness.llm.pricing import is_peak
    from triwitness.memory.context import MemoryContext

    _, pool, plan = _plan(a)
    print(render_report(plan, None, None))
    if not plan.sufficient:
        return 1
    if not a.yes:
        print("未运行：真跑会花钱，确认后加 --yes。")
        return 0
    if is_peak(datetime.now(UTC)):
        print("现在是 DeepSeek 高峰时段（北京时间工作日 9–12、14–18），不开跑。")
        return PEAK_EXIT
    os.environ["TW_LLM_MODE"] = "live"
    skill = pool.get(plan.skill, plan.version)
    tasks = [load_task(d) for d in suite_dirs(plan.suite) if d.name in set(plan.tasks)]
    configs = [RunConfig(name=f"gate-{arm}", category=CATEGORY) for arm in ARMS]

    def factory(cfg: RunConfig):  # type: ignore[no-untyped-def]
        from triwitness.eval.agents import LLMAgent
        from triwitness.llm.router import Router

        mem = MemoryContext.with_skills([skill]) if cfg.name == "gate-with" else None
        return LLMAgent(lambda: Router.deepseek_default(), category=CATEGORY, config_hash=cfg.name, memory=mem)

    runner = EvalRunner(grader=Grader(), llm_agent_factory=factory, live=True, gate=PeakGate(),
                        ledger=GlobalLedger(), max_total_cny=a.max_total_cny)  # fmt: skip
    out = Path(a.out)
    asyncio.run(runner.run(tasks, configs, attempts=plan.repeats, concurrency=a.concurrency, out_dir=out))
    print(f"完成：{out}。下一步：scripts/skill_gate.py report ... --out {out} [--apply]")
    return 0


def load_results(out: Path) -> GateResult:
    res: dict[str, dict[str, bool]] = {a: {} for a in ARMS}
    cost = dict.fromkeys(ARMS, 0.0)
    for arm in ARMS:
        for f in sorted((out / f"gate-{arm}").rglob("result.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            res[arm][f"{d['task_id']}#{d.get('attempt', 1)}"] = bool(d.get("resolved"))
            cost[arm] += float(d.get("cost_cny") or 0)
    return GateResult(res, {k: round(v, 4) for k, v in cost.items()})


def cmd_report(a: argparse.Namespace) -> int:
    st, pool, plan = _plan(a)
    res = load_results(Path(a.out))
    dec = decide(res)
    report = render_report(plan, res, dec)
    (Path(a.out) / "gate.md").write_text(report, encoding="utf-8")
    print(report)
    if a.apply:
        status = apply_decision(pool, plan, dec, report)
        st.commit(f"gate {plan.skill} v{plan.version} → {status}")
        print(f"已写入池：{plan.skill} v{plan.version} → {status}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["plan", "run", "report"])
    p.add_argument("--repo", required=True)
    p.add_argument("--skill", required=True)
    p.add_argument("--version", type=int, required=True)
    p.add_argument("--after", default="", help="只用 created_at 晚于此日期的任务（来源是评测任务时用）")
    p.add_argument("--exclude", action="append", help="排除的任务 id（来源任务）")
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--min-tasks", type=int, default=8)
    p.add_argument("--out", default="")
    p.add_argument("--concurrency", type=int, default=2)
    p.add_argument("--max-total-cny", type=float, default=4.0)
    p.add_argument("--yes", action="store_true", help="确认真跑（花钱）")
    p.add_argument("--apply", action="store_true", help="report 时把结论写进 Skill 池")
    a = p.parse_args(argv)
    if a.cmd != "plan" and not a.out:
        a.out = f"/workspace/_skill_gate/{a.skill}-v{a.version}"
    return {"plan": cmd_plan, "run": cmd_run, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
