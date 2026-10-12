# ruff: noqa: E501  （typer 选项的中文帮助串较长，整文件放宽行宽）
"""`tw memory …`（spec 013 §8）：记忆与 Skill 的查看、写入、蒸馏、门禁、监控、导出。

写记忆只走这里的显式命令（以及 `tw run` 结束后的 Skill 监控记录）；评测 / 自动化会话不读不写。
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

memory_app = typer.Typer(add_completion=False, no_args_is_help=True, help="记忆与 Skill（spec 013）")
gate_app = typer.Typer(add_completion=False, no_args_is_help=True, help="Skill A/B 门禁")
memory_app.add_typer(gate_app, name="gate")

RepoOpt = Annotated[Path, typer.Option("--repo", help="代码仓库路径（按 origin 远端或路径定位记忆）")]


def _store(repo: Path):  # type: ignore[no-untyped-def]
    from triwitness.memory.store import MemoryStore

    return MemoryStore.for_repo(str(repo.resolve()))


def _fail(msg: str, code: int = 1) -> None:
    typer.echo(msg, err=True)
    raise typer.Exit(code)


@memory_app.command("show")
def show_cmd(repo: RepoOpt = Path(".")) -> None:
    """记忆位置、事实、经验、Skill 与待定候选。"""
    from triwitness.memory.skills import SkillPool

    st = _store(repo)
    typer.echo(f"记忆仓库：{st.root}{'' if st.exists() else '（还没有）'}")
    if not st.exists():
        return
    facts, eps = st.facts(), st.episodes()
    typer.echo(f"\n仓库事实 {len(facts)} 条：")
    for f in facts:
        typer.echo(
            f"  {f.id}  [{f.meta.get('kind', '')}] {f.text}  ({f.meta.get('source', '')}, {f.meta.get('added', '')})"
        )
    typer.echo(f"\n经验片段 {len(eps)} 条：")
    for e in eps:
        typer.echo(f"  {e.id}  {e.text[:100]}")
    pool = SkillPool(st.root)
    typer.echo("\nSkill：")
    for name, info in sorted(pool.state().items()):
        vs = ", ".join(f"v{v}={i['status']}" for v, i in sorted(info["versions"].items(), key=lambda x: int(x[0])))
        typer.echo(f"  {name}  当前 {('v' + str(info['active'])) if info.get('active') else '无'}  [{vs}]")
    pend = [c for c in st.candidates() if c.get("status") == "pending"]
    typer.echo(f"\n待定候选 {len(pend)} 条（tw memory candidates）")


@memory_app.command("add-fact")
def add_fact_cmd(text: str, repo: RepoOpt = Path("."),
                 kind: Annotated[str, typer.Option(help="install / test / layout / convention / pitfall / other")] = "other",
                 source: Annotated[str, typer.Option(help="来源（默认手动）")] = "tw://manual") -> None:  # fmt: skip
    """手动加一条仓库事实（同样过静态检查，含密钥直接拒）。"""
    from triwitness.memory.store import MemoryRejected

    try:
        e = _store(repo).add_fact(text, kind=kind, source=source)
    except MemoryRejected as ex:
        _fail(str(ex))
        return
    typer.echo(f"已记住 {e.id}")


@memory_app.command("forget")
def forget_cmd(entry_id: str, repo: RepoOpt = Path(".")) -> None:
    """删除一条事实或经验（git 历史里仍可追溯）。"""
    if not _store(repo).forget(entry_id):
        _fail(f"没有 {entry_id}")
    typer.echo(f"已删除 {entry_id}")


@memory_app.command("candidates")
def candidates_cmd(
    repo: RepoOpt = Path("."), all_: Annotated[bool, typer.Option("--all", help="含已处理的")] = False
) -> None:
    """蒸馏出的候选（事实 / 经验待接受；Skill 待门禁）。"""
    for c in _store(repo).candidates():
        if not all_ and c.get("status") != "pending":
            continue
        head = c.get("text") or f"{c.get('name')}：{c.get('description', '')}"
        why = f"  ✗ {'；'.join(c['reasons'])}" if c.get("reasons") else ""
        ver = f" v{c['version']}" if c.get("version") else ""
        typer.echo(f"{c['id']}  {c['type']}{ver}  {c['status']}  {head[:120]}  ({c.get('source', '')}){why}")


@memory_app.command("accept")
def accept_cmd(cid: str, repo: RepoOpt = Path(".")) -> None:
    """接受一条事实 / 经验候选，写进记忆。"""
    from triwitness.memory.distill import DistillError, accept_candidate
    from triwitness.memory.store import MemoryRejected

    try:
        eid = accept_candidate(_store(repo), cid)
    except (DistillError, MemoryRejected) as e:
        _fail(str(e))
        return
    typer.echo(f"已接受 {cid} → {eid}")


@memory_app.command("reject")
def reject_cmd(cid: str, repo: RepoOpt = Path("."), reason: str = "人工拒绝") -> None:
    """拒绝一条候选。"""
    if _store(repo).set_candidate_status(cid, "rejected", note=reason) is None:
        _fail(f"没有候选 {cid}")
    typer.echo(f"已拒绝 {cid}")


@memory_app.command("distill")
def distill_cmd(run_id: str,
                live: Annotated[bool, typer.Option("--live", help="真实调用 reflector（deepseek-flash 非思考，记账）；默认只回放")] = False,
                allow_peak: Annotated[bool, typer.Option("--allow-peak", help="高峰时段也调用（默认拒绝）")] = False,
                repo: Annotated[Path | None, typer.Option(help="默认取 run 的 summary.json 里的仓库")] = None) -> None:  # fmt: skip
    """从一次验证通过的 run 提炼候选（只进候选区，不直接改记忆）。"""
    from triwitness.config import tw_home
    from triwitness.core.errors import TriWitnessError
    from triwitness.llm.pricing import is_peak
    from triwitness.memory.distill import distill_run
    from triwitness.memory.store import MemoryStore

    run_dir = tw_home() / "runs" / run_id
    if not run_dir.is_dir():
        _fail(f"没有 run：{run_dir}")
    if live:
        if is_peak(datetime.now(UTC)) and not allow_peak:
            _fail("现在是 DeepSeek 高峰时段（北京时间工作日 9–12、14–18），不调用；闲时再试或加 --allow-peak", 2)
        os.environ["TW_LLM_MODE"] = "live"
    summary = (
        json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        if (run_dir / "summary.json").is_file()
        else {}
    )
    target = str(repo.resolve()) if repo else str(summary.get("repo") or "")
    if not target:
        _fail("不知道是哪个仓库的 run；请加 --repo")
    from triwitness.llm.router import Router

    store = MemoryStore.for_repo(target)
    try:
        res = asyncio.run(distill_run(run_dir, Router.deepseek_default(), store, category="memory"))
    except TriWitnessError as e:
        _fail(f"蒸馏失败：{e}")
        return
    typer.echo(f"{res.run_id}：{json.dumps(res.counts(), ensure_ascii=False)}｜¥{res.cost_cny:.4f}｜记忆 {store.root}")
    for c in res.candidates:
        mark = "✓" if c["status"] == "pending" else "✗"
        head = c.get("text") or f"{c.get('name')}：{c.get('description', '')}"
        typer.echo(
            f"  {mark} {c['id']} {c['type']}  {head[:120]}"
            + (f"  —— {'；'.join(c['reasons'])}" if c.get("reasons") else "")
        )


@memory_app.command("check")
def check_cmd(path: Path, kind: Annotated[str, typer.Option(help="fact / episode / skill（SKILL.md 自动识别）")] = "fact",
              patch: Annotated[Path | None, typer.Option(help="来源补丁（检查是否夹带任务答案）")] = None) -> None:  # fmt: skip
    """对一段文本或 SKILL.md 做静态检查（长度 / 密钥 / 绕过 / 外传 / 任务答案 / 命名）。"""
    from triwitness.memory.checks import check_candidate
    from triwitness.memory.skills import Skill, SkillError

    text = path.read_text(encoding="utf-8")
    p = patch.read_text(encoding="utf-8") if patch else None
    if path.name == "SKILL.md" or kind == "skill":
        try:
            sk = Skill.parse(text)
        except SkillError as e:
            _fail(f"✗ 解析失败：{e}")
            return
        res = check_candidate(sk.body, "skill", name=sk.name, description=sk.description, patch=p)
        errs = sk.validate() + res.reasons()
    else:
        errs = check_candidate(text.strip(), kind, patch=p).reasons()  # type: ignore[arg-type]
    if errs:
        _fail("✗ " + "\n✗ ".join(errs))
    typer.echo("✓ 通过")


@memory_app.command("add-skill")
def add_skill_cmd(path: Path, repo: RepoOpt = Path("."),
                  source: Annotated[str, typer.Option(help="来源")] = "tw://manual") -> None:  # fmt: skip
    """把一个手写的 SKILL.md 放进候选池（之后要过门禁才合入）。"""
    from triwitness.memory.checks import check_candidate
    from triwitness.memory.skills import Skill, SkillError, SkillPool
    from triwitness.memory.store import today

    st = _store(repo)
    try:
        sk = Skill.parse(path.read_text(encoding="utf-8"))
    except SkillError as e:
        _fail(str(e))
        return
    res = check_candidate(sk.body, "skill", name=sk.name, description=sk.description)
    if not res.ok:
        _fail("✗ " + "；".join(res.reasons()))
    st.init()
    try:
        sk = SkillPool(st.root).add_candidate(sk, source=source, added=today())
    except SkillError as e:
        _fail(str(e))
        return
    st.commit(f"skill candidate {sk.name} v{sk.version}")
    typer.echo(f"候选 {sk.name} v{sk.version}（tw memory gate plan {sk.name} --version {sk.version}）")


def _plan(repo: Path, name: str, version: int | None, after: str, exclude: list[str] | None, repeats: int,
          min_tasks: int):  # type: ignore[no-untyped-def]  # fmt: skip
    from triwitness.memory.gate import plan_gate
    from triwitness.memory.skills import SkillPool

    st = _store(repo)
    pool = SkillPool(st.root)
    info = pool.state().get(name)
    if not info:
        _fail(f"池里没有 {name}")
    v = version or max(int(k) for k, i in info["versions"].items() if i["status"] == "candidate")  # type: ignore[index]
    return st, pool, plan_gate(pool, name, v, source_repo=str(repo.resolve()), after=after, exclude=exclude,
                               repeats=repeats, min_tasks=min_tasks)  # fmt: skip


@gate_app.command("plan")
def gate_plan_cmd(name: str, repo: RepoOpt = Path("."), version: int | None = None,
                  after: Annotated[str, typer.Option(help="只用 created_at 晚于此日期的任务（来源是评测任务时填它的日期）")] = "",
                  exclude: Annotated[list[str] | None, typer.Option(help="排除的任务（来源任务）")] = None,
                  repeats: int = 2, min_tasks: int = 8) -> None:  # fmt: skip
    """只出计划与花费预估，不运行。真跑：scripts/skill_gate.py run（需人工确认）。"""
    from triwitness.memory.gate import render_report

    _, _, plan = _plan(repo, name, version, after, exclude, repeats, min_tasks)
    typer.echo(render_report(plan, None, None))
    if plan.sufficient:
        typer.echo(f"真跑：uv run python scripts/skill_gate.py run --repo {repo} --skill {name} --version {plan.version}"
                   f" --max-total-cny {round(plan.est_cny * 1.5, 1)} --yes")  # fmt: skip


@gate_app.command("fake")
def gate_fake_cmd(name: str, repo: RepoOpt = Path("."), version: int | None = None,
                  rate_a: float = 0.5, rate_b: float = 0.7, seed: int = 0,
                  apply: Annotated[bool, typer.Option("--apply", help="把假结论写进池（只用于演示 / 测试）")] = False,
                  min_tasks: int = 8) -> None:  # fmt: skip
    """用假 runner 走一遍门禁流程（不调模型、¥0），验证选择 / 判定 / 报告。"""
    import random

    from triwitness.memory.gate import Outcome, apply_decision, decide, render_report, run_gate

    st, pool, plan = _plan(repo, name, version, "", None, 2, min_tasks)
    rng = random.Random(seed)

    def runner(task: str, arm: str, rep: int) -> Outcome:
        return Outcome(solved=rng.random() < (rate_b if arm == "with" else rate_a), cost_cny=0.0)

    res = run_gate(plan, runner) if plan.sufficient else None
    dec = decide(res) if res is not None else None
    report = render_report(plan, res, dec, mode="fake")
    typer.echo(report)
    if apply:
        status = apply_decision(pool, plan, dec, report)
        st.commit(f"gate(fake) {name} v{plan.version} → {status}")
        typer.echo(f"已写入池：{name} v{plan.version} → {status}")


@memory_app.command("rollback")
def rollback_cmd(name: str, repo: RepoOpt = Path("."), reason: str = "人工回滚") -> None:
    """把 Skill 回滚到上一个通过门禁的版本（没有就移除）。"""
    from triwitness.memory.skills import SkillError, SkillPool

    st = _store(repo)
    try:
        new = SkillPool(st.root).rollback(name, reason=reason)
    except SkillError as e:
        _fail(str(e))
        return
    st.commit(f"rollback {name} → {new}")
    typer.echo(f"{name} → {'v' + str(new) if new else '已移除'}")


@memory_app.command("approve-skill")
def approve_skill_cmd(name: str, version: Annotated[int, typer.Option(help="要合入的版本")],
                      reviewer: Annotated[str, typer.Option(help="审核人")], repo: RepoOpt = Path("."),
                      note: str = "") -> None:  # fmt: skip
    """repo 级 Skill 人工审核合入（held-out 不够开门禁时；上线后靠监控自动回滚）。"""
    from triwitness.memory.skills import SkillError, SkillPool

    st = _store(repo)
    try:
        sk = SkillPool(st.root).approve(name, version, reviewer=reviewer, note=note)
    except SkillError as e:
        _fail(str(e))
        return
    st.commit(f"skill human-review {name} v{version} by {reviewer}")
    typer.echo(f"{sk.name} v{sk.version} 已人工审核合入（上线监控：读取后成功率比基线低 15 个百分点以上自动回滚）")


@memory_app.command("monitor")
def monitor_cmd(
    repo: RepoOpt = Path("."),
    apply: Annotated[bool, typer.Option("--apply", help="退化的立即回滚（tw run 结束时会自动做）")] = False,
) -> None:
    """当前 Skill 的线上表现。"""
    from triwitness.memory.monitor import auto_rollback, health
    from triwitness.memory.skills import SkillPool

    st = _store(repo)
    pool = SkillPool(st.root)
    for name in sorted(pool.state()):
        h = health(pool, name)
        if h is not None:
            typer.echo(h.line())
    if apply:
        for h, new in auto_rollback(pool):
            typer.echo(f"已回滚 {h.skill} v{h.version} → {'v' + str(new) if new else '已移除'}")
        st.commit("monitor --apply")


@memory_app.command("export")
def export_cmd(
    repo: RepoOpt = Path("."),
    fmt: Annotated[
        str, typer.Option("--format", help="memory-repo / agents-md / claude-skills / opencode / agents-skills")
    ] = "memory-repo",
    out: Annotated[
        Path | None, typer.Option(help="输出目录（默认 ~/.triwitness/exports/<仓库>；不能在任何 git 工作区里）")
    ] = None,
) -> None:
    """导出记忆（Agent Memory Repo / AGENTS.md 片段 / Claude Code / OpenCode Skill 目录），不写进代码仓库。"""
    from triwitness.memory.export import default_out, export

    st = _store(repo)
    try:
        files = export(st, fmt, out or default_out(st))
    except (ValueError, FileNotFoundError) as e:
        _fail(str(e))
        return
    for f in files:
        typer.echo(str(f))


@memory_app.command("history")
def history_cmd(repo: RepoOpt = Path("."), n: int = 20) -> None:
    """记忆仓库的 git 历史（每次写入一次提交）。"""
    for line in _store(repo).history(n):
        typer.echo(line)


__all__ = ["memory_app"]
