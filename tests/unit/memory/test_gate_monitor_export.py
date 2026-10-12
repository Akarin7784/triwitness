"""spec 013 §5.3–§7（W6-07 / 08 / 09）：门禁选择与判定、监控回滚、导出。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from triwitness.memory.export import BEGIN, END, ExportTargetError, export
from triwitness.memory.gate import (
    GateResult,
    HeldoutTask,
    Outcome,
    apply_decision,
    decide,
    plan_gate,
    render_report,
    run_gate,
    select_heldout,
)
from triwitness.memory.monitor import auto_rollback, health, loaded_skills, observe_run, record
from triwitness.memory.skills import Skill, SkillError, SkillPool
from triwitness.memory.store import MemoryStore

from .conftest import make_skill

TASKS = [HeldoutTask(f"t{i:02d}", "https://github.com/o/a" if i % 2 else "https://github.com/o/b",
                     f"2022-0{1 + i % 9}-01") for i in range(20)]  # fmt: skip


def test_select_heldout_time_split_scope_and_exclusion() -> None:
    sel = select_heldout(TASKS, scope="global", after="2022-05-01", exclude=["t04"])
    assert all(t.created_at > "2022-05-01" and t.id != "t04" for t in sel.tasks)
    assert sel.eligible == len([t for t in TASKS if t.created_at > "2022-05-01" and t.id != "t04"])
    same = select_heldout(TASKS, scope="repo", source_repo="git@github.com:o/a.git", min_tasks=3)
    assert same.tasks and all(t.repo.endswith("/o/a") for t in same.tasks)
    # 确定性：同一 seed 同一选择；不足时标出
    assert select_heldout(TASKS, scope="global").tasks == select_heldout(TASKS, scope="global").tasks
    few = select_heldout(TASKS, scope="repo", source_repo="https://github.com/o/zzz")
    assert not few.sufficient and few.tasks == []
    with pytest.raises(ValueError):
        select_heldout(TASKS, scope="team")


def test_real_reserve_suite_has_no_same_repo_heldout() -> None:
    """ext-reserve 每个仓库至多 2 个任务：scope=repo 永远不够 8 个（spec 013 开放问题 Q1）。"""
    from triwitness.memory.gate import load_tasks

    tasks = load_tasks()
    assert len(tasks) >= 50
    assert not select_heldout(tasks, scope="repo", source_repo=tasks[0].repo).sufficient
    assert select_heldout(tasks, scope="global", exclude=[tasks[0].id]).sufficient


def _pool(store: MemoryStore, scope: str = "global") -> SkillPool:
    store.init()
    pool = SkillPool(store.root)
    pool.add_candidate(make_skill(scope=scope), source="tw://run/r_1", added="2026-10-12")
    return pool


def test_gate_promotes_on_gain(store: MemoryStore) -> None:
    pool = _pool(store)
    plan = plan_gate(pool, "py-unittest-repro", 1, tasks=TASKS, max_tasks=10)
    assert plan.sufficient and plan.runs == 40 and plan.est_cny == pytest.approx(3.2)
    solved_b = {"t01", "t03", "t05", "t07", "t09", "t11"}

    def runner(task: str, arm: str, rep: int) -> Outcome:
        return Outcome(solved=task in solved_b if arm == "with" else task in {"t01", "t03"}, cost_cny=0.05)

    res = run_gate(plan, runner)
    dec = decide(res)
    assert dec.n == 20 and dec.rate_b > dec.rate_a and dec.promote
    report = render_report(plan, res, dec)
    assert "**合入**" in report and "McNemar" in report
    assert apply_decision(pool, plan, dec, report) == "active"
    (act,) = pool.active()
    assert act.version == 1 and pool.state()["py-unittest-repro"]["versions"]["1"]["gate"]["rate_a"] == dec.rate_a


def test_gate_rejects_no_gain_or_costly(store: MemoryStore) -> None:
    same = GateResult({"without": {"a#1": True, "b#1": False}, "with": {"a#1": True, "b#1": False}},
                      {"without": 0.2, "with": 0.2})  # fmt: skip
    assert not decide(same).promote and "没有提升" in decide(same).reason
    costly = GateResult({"without": {"a#1": False, "b#1": False}, "with": {"a#1": True, "b#1": False}},
                        {"without": 0.2, "with": 0.3})  # fmt: skip
    d = decide(costly)
    assert not d.promote and "成本" in d.reason and d.underpowered
    pool = _pool(store)
    plan = plan_gate(pool, "py-unittest-repro", 1, tasks=TASKS)
    assert apply_decision(pool, plan, d, "# r") == "rejected" and pool.active() == []


def test_gate_insufficient_heldout_not_run(store: MemoryStore) -> None:
    pool = _pool(store, scope="repo")
    plan = plan_gate(pool, "py-unittest-repro", 1, tasks=TASKS, source_repo="https://github.com/o/zzz")
    assert not plan.sufficient and "insufficient_heldout" in plan.note
    assert "未运行" in render_report(plan, None, None)
    # spec 013 §10 Q1（已决定）：repo 级 held-out 不够 → 转人工审核，不判拒绝
    assert apply_decision(pool, plan, None, "# n") == "awaiting_review"
    assert pool.state()["py-unittest-repro"]["versions"]["1"]["status"] == "awaiting_review"


def test_global_insufficient_heldout_rejected(store: MemoryStore) -> None:
    pool = _pool(store, scope="global")
    plan = plan_gate(pool, "py-unittest-repro", 1, tasks=TASKS[:3])
    assert not plan.sufficient
    assert apply_decision(pool, plan, None, "# n") == "rejected"
    with pytest.raises(SkillError):
        pool.approve("py-unittest-repro", 1, reviewer="eva")


def test_repo_skill_human_review_then_monitor_rollback(store: MemoryStore) -> None:
    pool = _pool(store, scope="repo")
    plan = plan_gate(pool, "py-unittest-repro", 1, tasks=TASKS, source_repo="https://github.com/o/zzz")
    apply_decision(pool, plan, None, "# n")
    with pytest.raises(SkillError):
        pool.approve("py-unittest-repro", 1, reviewer=" ")
    sk = pool.approve("py-unittest-repro", 1, reviewer="eva", note="看过正文")
    assert sk.metadata["tw-status"] == "active" and pool.load("py-unittest-repro").name == sk.name
    assert "人工审核" in (pool.version_dir("py-unittest-repro", 1) / "gate.md").read_text(encoding="utf-8")
    h = health(pool, "py-unittest-repro")
    assert h is not None and h.floor is None  # 没有基线样本时不回滚
    # 注入但没读的 8 次全过（基线 100%），读了的 8 次只过 6 次（75% < 85%）→ 回滚
    for i in range(8):
        record(pool, [sk], run_id=f"b{i}", solved=True, loaded=set())
        record(pool, [sk], run_id=f"u{i}", solved=i < 6, loaded={sk.name})
    h = health(pool, "py-unittest-repro")
    assert h is not None and h.floor == pytest.approx(0.85) and h.degraded
    assert auto_rollback(pool)[0][1] is None


def test_monitor_degradation_triggers_rollback(store: MemoryStore) -> None:
    pool = _pool(store)
    pool.promote("py-unittest-repro", 1, gate_report="#", summary={"rate_a": 0.6, "rate_b": 0.8})
    sk = pool.load("py-unittest-repro")
    for i in range(7):
        record(pool, [sk], run_id=f"r{i}", solved=False, loaded={"py-unittest-repro"})
    record(pool, [sk], run_id="r_unused", solved=False, loaded=set())  # 没读正文的不计
    h = health(pool, "py-unittest-repro")
    assert h is not None and h.n == 7 and not h.degraded  # 样本不够，不动
    assert auto_rollback(pool) == []
    record(pool, [sk], run_id="r7", solved=False, loaded={"py-unittest-repro"})
    h = health(pool, "py-unittest-repro")
    assert h is not None and h.degraded and h.floor == pytest.approx(0.45)
    ((_, new),) = auto_rollback(pool)
    assert new is None and pool.active() == []
    assert pool.state()["py-unittest-repro"]["history"][-1]["action"] == "rollback"


def test_monitor_healthy_and_no_gate_baseline(store: MemoryStore) -> None:
    pool = _pool(store)
    pool.promote("py-unittest-repro", 1, gate_report="#")  # 没有门禁摘要 → 不自动回滚
    sk = pool.load("py-unittest-repro")
    for i in range(10):
        record(pool, [sk], run_id=f"r{i}", solved=False, loaded={"py-unittest-repro"})
    assert auto_rollback(pool) == [] and len(pool.active()) == 1


def test_observe_run_reads_trajectory(store: MemoryStore, tmp_path: Path) -> None:
    pool = _pool(store)
    pool.promote("py-unittest-repro", 1, gate_report="#", summary={"rate_a": 0.5})
    traj = tmp_path / "trajectory.jsonl"
    traj.write_text(json.dumps({"kind": "tool_call", "payload": {"tool": "load_skill", "ok": True,
                                                                  "args_preview": '{"name": "py-unittest-repro"}'}}),
                    encoding="utf-8")  # fmt: skip
    assert loaded_skills(traj) == {"py-unittest-repro"}
    msgs: list[str] = []
    observe_run(store.root, pool.active(), run_id="r1", solved=True, trajectory=traj, commit=msgs.append)
    assert msgs == ["monitor r1"]
    assert health(pool, "py-unittest-repro").n == 1  # type: ignore[union-attr]


def test_export_formats(store: MemoryStore, tmp_path: Path) -> None:
    store.add_fact("测试用 tox -e py311", kind="test", source="tw://run/r_1", added="2026-10-12")
    pool = _pool(store)
    pool.promote("py-unittest-repro", 1, gate_report="#")
    pool.add_candidate(Skill("not-promoted", "候选不导出", "x"), source="s", added="2026-10-12")
    out = tmp_path / "out"
    files = export(store, "memory-repo", out / "repo")
    assert {f.relative_to(out / "repo").as_posix() for f in files} == {"MEMORY.md", "skills/py-unittest-repro/SKILL.md"}
    md = (out / "repo" / "MEMORY.md").read_text(encoding="utf-8")
    assert "[source: tw://run/r_1; added: 2026-10-12" in md and "## Index" in md
    assert "[[skills/py-unittest-repro/SKILL]]" in md
    (frag,) = export(store, "agents-md", out / "a")
    text = frag.read_text(encoding="utf-8")
    assert text.startswith(BEGIN) and text.rstrip().endswith(END)
    assert "tox -e py311" in text and "py-unittest-repro：" in text
    (c,) = export(store, "claude-skills", out / "c")
    assert c.relative_to(out / "c").as_posix() == ".claude/skills/py-unittest-repro/SKILL.md"
    assert Skill.parse(c.read_text(encoding="utf-8")).name == "py-unittest-repro"
    (o,) = export(store, "opencode", out / "o")
    assert o.relative_to(out / "o").as_posix() == ".opencode/skills/py-unittest-repro/SKILL.md"
    with pytest.raises(ValueError):
        export(store, "zip", out)
    (a,) = export(store, "agents-skills", out / "g")
    assert a.relative_to(out / "g").as_posix() == ".agents/skills/py-unittest-repro/SKILL.md"


def test_export_never_writes_into_a_repo(store: MemoryStore, tmp_path: Path) -> None:
    """spec 013 §10 Q6（已决定）：导出目录在来源仓库或任何 git 工作区里一律拒绝。"""
    pool = _pool(store)
    pool.promote("py-unittest-repro", 1, gate_report="#")
    repo = tmp_path / "work" / "proj"
    (repo / ".git").mkdir(parents=True)
    with pytest.raises(ExportTargetError):
        export(store, "claude-skills", repo)
    with pytest.raises(ExportTargetError):
        export(store, "claude-skills", repo / "sub" / "dir")
    src = MemoryStore(store.root, repo=str(tmp_path / "src"))
    with pytest.raises(ExportTargetError):
        export(src, "opencode", tmp_path / "src" / "out")
    assert not (repo / ".claude").exists()
