"""Skills（spec 013 §5，W6-04）：Agent Skills 规范的 SKILL.md + 带版本的候选池 + 渐进加载。

SKILL.md = YAML frontmatter（name、description，可选 license / compatibility / allowed-tools / metadata）
+ Markdown 正文。
我们的版本与治理信息全部放在 `metadata`（规范要求 string → string），键名带 `tw-` 前缀避免冲突：

    metadata:
      tw-version: "2"            # 池内版本号（门禁通过一次 +1）
      tw-status: active          # candidate / active / rejected / rolled_back
      tw-source: tw://run/r_…    # 来源轨迹（多个用空格分隔）
      tw-added: 2026-10-12
      tw-scope: repo             # repo = 只用于本仓库；global = 跨仓库通用（门禁选 held-out 的范围不同）
      tw-gate: pool/<名>/v2/gate.md

池：`pool/<名>/v<N>/SKILL.md`（每个版本一份，含 gate.md / reject.txt），`pool/pool.json` 记当前版本与历史；
合入 = 把该版本复制到 `skills/<名>/SKILL.md`。回滚 = 换回上一个通过门禁的版本，没有就移除。
上下文里只放 name + description（`catalog_block`），正文由 load_skill 工具按需读取。
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml

from triwitness.core.errors import TriWitnessError
from triwitness.memory.checks import check_skill_name

Status = Literal["candidate", "active", "rejected", "rolled_back", "superseded"]


class SkillError(TriWitnessError):
    pass


@dataclass
class Skill:
    name: str
    description: str
    body: str
    metadata: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)  # license / compatibility / allowed-tools

    @property
    def version(self) -> int:
        try:
            return int(self.metadata.get("tw-version", "0"))
        except ValueError:
            return 0

    @property
    def status(self) -> str:
        return self.metadata.get("tw-status", "candidate")

    @property
    def scope(self) -> str:
        return self.metadata.get("tw-scope", "repo")

    def render(self) -> str:
        fm: dict[str, Any] = {"name": self.name, "description": self.description}
        for k in ("license", "compatibility", "allowed-tools"):
            if k in self.extra:
                fm[k] = self.extra[k]
        if self.metadata:
            fm["metadata"] = {k: str(v) for k, v in sorted(self.metadata.items())}
        head = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000).strip()
        return f"---\n{head}\n---\n\n{self.body.strip()}\n"

    @classmethod
    def parse(cls, text: str) -> Skill:
        if not text.startswith("---"):
            raise SkillError("SKILL.md 缺少 YAML frontmatter")
        try:
            _, head, body = text.split("---", 2)
            fm = yaml.safe_load(head) or {}
        except (ValueError, yaml.YAMLError) as e:
            raise SkillError(f"SKILL.md frontmatter 无法解析：{e}") from e
        if not isinstance(fm, dict) or not fm.get("name") or not fm.get("description"):
            raise SkillError("SKILL.md 需要 name 与 description")
        meta = fm.get("metadata") or {}
        if not isinstance(meta, dict):
            raise SkillError("metadata 必须是映射")
        extra = {k: fm[k] for k in ("license", "compatibility", "allowed-tools") if k in fm}
        return cls(str(fm["name"]), str(fm["description"]).strip(), body.strip(),
                   {str(k): str(v) for k, v in meta.items()}, extra)  # fmt: skip

    def validate(self) -> list[str]:
        errs = [f.detail for f in check_skill_name(self.name)]
        if not 1 <= len(self.description) <= 1024:
            errs.append("description 应为 1–1024 字符")
        comp = self.extra.get("compatibility")
        if comp is not None and not 1 <= len(str(comp)) <= 500:
            errs.append("compatibility 应为 1–500 字符")
        return errs


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class SkillPool:
    """一个记忆仓库里的 Skill 池（root = MemoryStore.root）。"""

    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def pool_json(self) -> Path:
        return self.root / "pool" / "pool.json"

    def state(self) -> dict[str, Any]:
        if not self.pool_json.is_file():
            return {}
        return json.loads(self.pool_json.read_text(encoding="utf-8"))

    def _save(self, st: dict[str, Any]) -> None:
        self.pool_json.parent.mkdir(parents=True, exist_ok=True)
        self.pool_json.write_text(json.dumps(st, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def version_dir(self, name: str, version: int) -> Path:
        return self.root / "pool" / name / f"v{version}"

    def get(self, name: str, version: int) -> Skill:
        p = self.version_dir(name, version) / "SKILL.md"
        if not p.is_file():
            raise SkillError(f"没有 {name} v{version}")
        return Skill.parse(p.read_text(encoding="utf-8"))

    def _event(self, st: dict[str, Any], name: str, action: str, version: int, note: str = "") -> None:
        st.setdefault(name, {"active": None, "versions": {}, "history": []})["history"].append(
            {"at": _now(), "action": action, "version": version, **({"note": note} if note else {})}
        )

    def add_candidate(self, skill: Skill, *, source: str, added: str) -> Skill:
        errs = skill.validate()
        if errs:
            raise SkillError("；".join(errs))
        st = self.state()
        ent = st.setdefault(skill.name, {"active": None, "versions": {}, "history": []})
        version = max([int(v) for v in ent["versions"]] or [0]) + 1
        skill.metadata.update({"tw-version": str(version), "tw-status": "candidate", "tw-source": source,
                               "tw-added": added})  # fmt: skip
        skill.metadata.setdefault("tw-scope", "repo")
        d = self.version_dir(skill.name, version)
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(skill.render(), encoding="utf-8")
        ent["versions"][str(version)] = {"status": "candidate", "source": source, "added": added}
        self._event(st, skill.name, "candidate", version)
        self._save(st)
        return skill

    def _set_status(self, name: str, version: int, status: Status, st: dict[str, Any]) -> Skill:
        sk = self.get(name, version)
        sk.metadata["tw-status"] = status
        (self.version_dir(name, version) / "SKILL.md").write_text(sk.render(), encoding="utf-8")
        st[name]["versions"][str(version)]["status"] = status
        return sk

    def promote(self, name: str, version: int, *, gate_report: str, summary: dict[str, Any] | None = None) -> Skill:
        """门禁通过：该版本成为当前版本（旧当前版本标 superseded，保留以便回滚）。"""
        st = self.state()
        if name not in st or str(version) not in st[name]["versions"]:
            raise SkillError(f"池里没有 {name} v{version}")
        d = self.version_dir(name, version)
        (d / "gate.md").write_text(gate_report, encoding="utf-8")
        prev = st[name].get("active")
        if prev is not None and prev != version:
            self._set_status(name, prev, "superseded", st)
        sk = self._set_status(name, version, "active", st)
        sk.metadata["tw-gate"] = f"pool/{name}/v{version}/gate.md"
        (d / "SKILL.md").write_text(sk.render(), encoding="utf-8")
        if summary:
            st[name]["versions"][str(version)]["gate"] = summary
        st[name]["active"] = version
        self._event(st, name, "promote", version)
        self._save(st)
        self._install(name, sk)
        return sk

    def reject(self, name: str, version: int, *, reason: str, gate_report: str | None = None) -> None:
        st = self.state()
        d = self.version_dir(name, version)
        if gate_report:
            (d / "gate.md").write_text(gate_report, encoding="utf-8")
        (d / "reject.txt").write_text(reason + "\n", encoding="utf-8")
        self._set_status(name, version, "rejected", st)
        st[name]["versions"][str(version)]["reason"] = reason
        self._event(st, name, "reject", version, reason)
        self._save(st)

    def rollback(self, name: str, *, reason: str) -> int | None:
        """回滚当前版本：换回上一个曾通过门禁（superseded）的版本；没有就移除。返回新的当前版本（None = 已移除）。"""
        st = self.state()
        cur = (st.get(name) or {}).get("active")
        if cur is None:
            raise SkillError(f"{name} 没有当前版本，无法回滚")
        self._set_status(name, cur, "rolled_back", st)
        versions = st[name]["versions"]
        prev = [int(v) for v, info in versions.items() if info.get("status") == "superseded" and int(v) < cur]
        new = max(prev) if prev else None
        if new is not None:
            sk = self._set_status(name, new, "active", st)
            self._install(name, sk)
        else:
            shutil.rmtree(self.root / "skills" / name, ignore_errors=True)
        st[name]["active"] = new
        self._event(st, name, "rollback", cur, reason)
        self._save(st)
        return new

    def _install(self, name: str, sk: Skill) -> None:
        dst = self.root / "skills" / name
        if dst.exists():
            shutil.rmtree(dst)
        src = self.version_dir(name, sk.version)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("gate.md", "reject.txt"))
        (dst / "SKILL.md").write_text(sk.render(), encoding="utf-8")

    # ---------------------------------------------------------------- 使用
    def active(self) -> list[Skill]:
        d = self.root / "skills"
        out = []
        for p in sorted(d.glob("*/SKILL.md")) if d.is_dir() else []:
            try:
                out.append(Skill.parse(p.read_text(encoding="utf-8")))
            except SkillError:
                continue
        return out

    def load(self, name: str) -> Skill:
        p = self.root / "skills" / name / "SKILL.md"
        if not p.is_file():
            raise SkillError(f"没有已合入的 Skill：{name}")
        return Skill.parse(p.read_text(encoding="utf-8"))

    def files(self, name: str) -> list[str]:
        d = self.root / "skills" / name
        return sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file() and p.name != "SKILL.md")


def catalog_block(skills: list[Skill]) -> str:
    """稳定前缀里的技能目录：只有 name + description（Agent Skills 渐进加载第 1 层）。"""
    return "\n".join(f"- {s.name}：{' '.join(s.description.split())}" for s in sorted(skills, key=lambda s: s.name))


__all__ = ["Skill", "SkillError", "SkillPool", "catalog_block"]
