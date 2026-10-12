"""Skill 上线后的监控与自动回滚（spec 013 §5.4，W6-08）。

每次读了记忆的 run 结束后（`tw run` 交互 / 后台；评测不读记忆所以不记），给每个注入的 Skill 记一行：
`pool/monitor.jsonl`：{at, skill, version, run, solved, loaded}
（loaded = 这次 Agent 是否真的调用 load_skill 读了正文）。

判定（只看 loaded 的 run，最近 window 条）：样本 ≥ min_n 且成功率 < 门禁时 A 臂（无 Skill）成功率 − drop
→ 自动回滚到上一个通过门禁的版本（没有就移除），写进 pool.json 历史并 git 提交。人工审核合入的 repo 级 Skill
用同仓库“注入但没读”的 run 成功率作基线（≥ min_n 条才判）；两者都没有的不自动回滚。
注意：门禁是在 held-out 评测任务上测的，日常任务的成功率不完全可比；drop = −15pp（spec 013 §10 Q5，Eva 2026-10-12 已决定）。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from triwitness.memory.skills import Skill, SkillPool

WINDOW = 20
MIN_N = 8
DROP = 0.15


def monitor_path(pool: SkillPool) -> Path:
    return pool.root / "pool" / "monitor.jsonl"


def record(pool: SkillPool, skills: list[Skill], *, run_id: str, solved: bool, loaded: set[str]) -> None:
    p = monitor_path(pool)
    p.parent.mkdir(parents=True, exist_ok=True)
    at = datetime.now(UTC).isoformat(timespec="seconds")
    with p.open("a", encoding="utf-8") as f:
        for s in skills:
            f.write(json.dumps({"at": at, "skill": s.name, "version": s.version, "run": run_id, "solved": solved,
                                "loaded": s.name in loaded}, ensure_ascii=False) + "\n")  # fmt: skip


def outcomes(pool: SkillPool, name: str, version: int) -> list[dict]:
    p = monitor_path(pool)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("skill") == name and d.get("version") == version:
            out.append(d)
    return out


@dataclass
class Health:
    skill: str
    version: int
    n: int
    rate: float | None
    floor: float | None
    degraded: bool
    exposures: int

    def line(self) -> str:
        r = "—" if self.rate is None else f"{self.rate:.0%}"
        f = "无门禁基线" if self.floor is None else f"下限 {self.floor:.0%}"
        flag = "⚠ 退化" if self.degraded else "正常"
        return f"{self.skill} v{self.version}：读取后 {self.n} 次，成功率 {r}（{f}；注入 {self.exposures} 次）{flag}"


def health(pool: SkillPool, name: str, *, window: int = WINDOW, min_n: int = MIN_N,
           drop: float = DROP) -> Health | None:  # fmt: skip
    st = pool.state().get(name) or {}
    v = st.get("active")
    if v is None:
        return None
    rows = outcomes(pool, name, int(v))
    used = [r for r in rows if r.get("loaded")][-window:]
    rate = sum(1 for r in used if r.get("solved")) / len(used) if used else None
    gate = (st.get("versions", {}).get(str(v)) or {}).get("gate") or {}
    floor = None
    if "rate_a" in gate:
        floor = max(0.0, float(gate["rate_a"]) - drop)
    elif gate.get("human_review"):
        # 人工审核合入的 repo 级 Skill 没有门禁 A 臂：用同仓库“注入了但没读”的 run 当基线（§10 Q1/Q5 已决定）
        base = [r for r in rows if not r.get("loaded")][-window:]
        if len(base) >= min_n:
            floor = max(0.0, sum(1 for r in base if r.get("solved")) / len(base) - drop)
    degraded = floor is not None and rate is not None and len(used) >= min_n and rate < floor
    return Health(skill=name, version=int(v), n=len(used), rate=rate, floor=floor, degraded=degraded,
                  exposures=len(rows))  # fmt: skip


def auto_rollback(pool: SkillPool, **kw: float) -> list[tuple[Health, int | None]]:
    """对每个当前 Skill 做健康检查；退化的回滚。返回 [(健康, 回滚后的版本或 None=已移除)]。"""
    done = []
    for name, st in sorted(pool.state().items()):
        if st.get("active") is None:
            continue
        h = health(pool, name, **kw)  # type: ignore[arg-type]
        if h is not None and h.degraded:
            new = pool.rollback(name, reason=f"监控自动回滚：{h.line()}")
            done.append((h, new))
    return done


def loaded_skills(trajectory: Path) -> set[str]:
    """从轨迹里找这次真正调用过 load_skill（成功）的 Skill 名。"""
    out: set[str] = set()
    if not trajectory.is_file():
        return out
    for line in trajectory.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        p = e.get("payload") or {}
        if e.get("kind") == "tool_call" and p.get("tool") == "load_skill" and p.get("ok"):
            try:
                name = json.loads(p.get("args_preview") or "{}").get("name")
            except (json.JSONDecodeError, AttributeError):
                name = None
            if name:
                out.add(str(name))
    return out


def observe_run(store_root: Path, skills: list[Skill], *, run_id: str, solved: bool, trajectory: Path,
                commit: Callable[[str], None] | None = None) -> list[tuple[Health, int | None]]:  # fmt: skip
    """`tw run` 结束后调用：记一行结果并做健康检查，退化的自动回滚。"""
    pool = SkillPool(store_root)
    record(pool, skills, run_id=run_id, solved=solved, loaded=loaded_skills(trajectory))
    done = auto_rollback(pool)
    if commit is not None:
        commit(f"monitor {run_id}" + "".join(f"; rollback {h.skill} v{h.version}" for h, _ in done))
    return done


__all__ = [
    "DROP",
    "MIN_N",
    "WINDOW",
    "Health",
    "auto_rollback",
    "health",
    "loaded_skills",
    "monitor_path",
    "observe_run",
    "outcomes",
    "record",
]
