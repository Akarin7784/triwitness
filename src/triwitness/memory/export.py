"""`tw memory export`（spec 013 §7，W6-09）：把记忆导出成其他工具能读的格式。

- memory-repo：Agent Memory Repo 原样（MEMORY.md + episodes.md + skills/<名>/SKILL.md），可直接作为独立 git 仓库使用；
- agents-md：一段可贴进 AGENTS.md 的 Markdown（仓库事实 + 技能目录），带起止标记，重复导出可替换；
- claude-skills：`.claude/skills/<名>/SKILL.md`（Agent Skills 规范，Claude Code 读取）；
- opencode：`.opencode/skills/<名>/SKILL.md`（OpenCode 的项目级 Skill 目录）；
- agents-skills：`.agents/skills/<名>/SKILL.md`（跨工具通用目录，OpenCode 等也会读）。
只导出已接受的事实 / 经验与**当前版本**的 Skill（候选、被拒、回滚的不导出）。
**绝不写进用户的代码仓库**（spec 013 §10 Q6，Eva 2026-10-12 已决定）：--out 落在来源仓库或任何 git 工作区里一律拒绝；
Skill 只写到 --out 下的 `.claude/skills`、`.opencode/skills`、`.agents/skills`，要用时用户自己复制。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from triwitness.memory.format import render_entry
from triwitness.memory.skills import SkillPool, catalog_block
from triwitness.memory.store import MemoryStore

FORMATS = ("memory-repo", "agents-md", "claude-skills", "opencode", "agents-skills")
SKILL_DIRS = {"claude-skills": ".claude/skills", "opencode": ".opencode/skills", "agents-skills": ".agents/skills"}
BEGIN, END = "<!-- triwitness-memory:begin -->", "<!-- triwitness-memory:end -->"


def agents_md_fragment(store: MemoryStore) -> str:
    facts = store.facts()
    skills = SkillPool(store.root).active()
    lines = [BEGIN, "## 仓库记忆（TriWitness 导出）", ""]
    lines += [render_entry(f.text, {"source": f.meta.get("source", ""), "added": f.meta.get("added", "")})
              for f in facts] or ["（无）"]  # fmt: skip
    if skills:
        lines += ["", "### 技能", "", catalog_block(skills)]
    lines += [END, ""]
    return "\n".join(lines)


def _copy_skills(store: MemoryStore, dst: Path) -> list[Path]:
    out = []
    src = store.root / "skills"
    for d in sorted(src.glob("*/")) if src.is_dir() else []:
        if not (d / "SKILL.md").is_file():
            continue
        target = dst / d.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(d, target)
        out.append(target / "SKILL.md")
    return out


class ExportTargetError(ValueError):
    """导出目录落在代码仓库里。"""


def _inside_git_worktree(p: Path) -> Path | None:
    for d in [p, *p.parents]:
        if (d / ".git").exists():
            return d
    return None


def check_target(store: MemoryStore, out: Path) -> None:
    """--out 不能在来源仓库里，也不能在任何 git 工作区里（防止导出物被顺手提交进用户仓库）。"""
    o = out.expanduser().resolve()
    if store.repo and not store.repo.startswith(("http://", "https://", "git@")):
        r = Path(store.repo).expanduser().resolve()
        if o == r or r in o.parents:
            raise ExportTargetError(f"导出目录在代码仓库里（{r}），不写用户仓库；换一个仓库外的目录")
    wt = _inside_git_worktree(o)
    if wt is not None:
        raise ExportTargetError(f"导出目录在 git 工作区里（{wt}），不写用户仓库；换一个仓库外的目录")


def default_out(store: MemoryStore) -> Path:
    from triwitness.config import tw_home

    return tw_home() / "exports" / store.root.name


def export(store: MemoryStore, fmt: str, out: Path) -> list[Path]:
    if fmt not in FORMATS:
        raise ValueError(f"未知格式 {fmt}（可选：{'、'.join(FORMATS)}）")
    check_target(store, out)
    if not store.exists():
        raise FileNotFoundError(f"没有记忆：{store.root}")
    out.mkdir(parents=True, exist_ok=True)
    if fmt == "agents-md":
        p = out / "AGENTS.memory.md"
        p.write_text(agents_md_fragment(store), encoding="utf-8")
        return [p]
    if fmt in SKILL_DIRS:
        return _copy_skills(store, out / SKILL_DIRS[fmt])
    files = [out / "MEMORY.md"]
    files[0].write_text(store.render_memory(), encoding="utf-8")  # 现渲染：索引与当前 Skill 一致
    if store.episodes_md.is_file():
        shutil.copy2(store.episodes_md, out / "episodes.md")
        files.append(out / "episodes.md")
    files += _copy_skills(store, out / "skills")
    return files


__all__ = ["FORMATS", "SKILL_DIRS", "ExportTargetError", "agents_md_fragment", "check_target", "default_out", "export"]
