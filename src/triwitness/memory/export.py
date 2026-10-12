"""`tw memory export`（spec 013 §7，W6-09）：把记忆导出成其他工具能读的格式。

- memory-repo：Agent Memory Repo 原样（MEMORY.md + episodes.md + skills/<名>/SKILL.md），可直接作为独立 git 仓库使用；
- agents-md：一段可贴进 AGENTS.md 的 Markdown（仓库事实 + 技能目录），带起止标记，重复导出可替换；
- claude-skills：`.claude/skills/<名>/SKILL.md`（Agent Skills 规范，Claude Code 读取）；
- opencode：`.opencode/skills/<名>/SKILL.md`（OpenCode 的项目级 Skill 目录）；
- agents-skills：`.agents/skills/<名>/SKILL.md`（跨工具通用目录，OpenCode 等也会读）。
只导出已接受的事实 / 经验与**当前版本**的 Skill（候选、被拒、回滚的不导出）。不写用户仓库，只写 --out 指定的目录。
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


def export(store: MemoryStore, fmt: str, out: Path) -> list[Path]:
    if fmt not in FORMATS:
        raise ValueError(f"未知格式 {fmt}（可选：{'、'.join(FORMATS)}）")
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


__all__ = ["FORMATS", "agents_md_fragment", "export"]
