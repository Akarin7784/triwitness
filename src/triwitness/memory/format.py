"""Agent Memory Repo 条目格式（spec 013 §3.1）。

一条记忆是 Markdown 里的一行 bullet，行尾可带元数据 `[key: value; key: value]`；推荐键 `source`（学到这条的会话链接）
和 `added`（YYYY-MM-DD）。我们另加 `id`（稳定编号，可撤销）与 `kind`（事实类别）。链接写 `[[path]]`（相对记忆根，
Markdown 文件省略 .md）。参考：github.com/AgentMemoryRepo/agentmemoryrepo SPEC.md（2026-10-05）。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

_META = re.compile(r"\s*\[([A-Za-z][\w-]*:\s*[^\[\]]*(?:;\s*[A-Za-z][\w-]*:\s*[^\[\]]*)*)\]\s*$")
_LINK = re.compile(r"^\[\[([^\]]+)\]\]$")


@dataclass
class Entry:
    text: str
    meta: dict[str, str] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.meta.get("id") or entry_id(self.text)

    def render(self) -> str:
        return render_entry(self.text, self.meta)


def entry_id(text: str, prefix: str = "m") -> str:
    return f"{prefix}-{hashlib.sha256(' '.join(text.split()).encode()).hexdigest()[:8]}"


def _clean(v: str) -> str:
    """元数据值不能含 `;` `[` `]` 和换行（会破坏语法）。"""
    return re.sub(r"[;\[\]\n\r]+", " ", str(v)).strip()


def render_entry(text: str, meta: dict[str, str] | None = None) -> str:
    body = " ".join(text.split())
    if not meta:
        return f"- {body}"
    order = ["source", "added", *sorted(k for k in meta if k not in ("source", "added"))]
    parts = [f"{k}: {_clean(meta[k])}" for k in order if k in meta and _clean(meta[k])]
    return f"- {body} [{'; '.join(parts)}]" if parts else f"- {body}"


def parse_entry(line: str) -> Entry | None:
    """一行 `- text [k: v; k: v]` → Entry；不是 bullet 或是 `[[link]]` 返回 None。"""
    s = line.strip()
    if not s.startswith(("- ", "* ")):
        return None
    s = s[2:].strip()
    if not s or _LINK.match(s):
        return None
    meta: dict[str, str] = {}
    m = _META.search(s)
    if m:
        for part in m.group(1).split(";"):
            k, _, v = part.partition(":")
            if k.strip():
                meta[k.strip()] = v.strip()
        s = s[: m.start()].rstrip()
    return Entry(s, meta)


def parse_entries(md: str, *, section: str | None = None, stop_at: str | None = "## Index") -> list[Entry]:
    """解析 Markdown 里的条目。section 给出时只取该 `## 标题` 下的；stop_at 之后的（索引）不算条目。"""
    out: list[Entry] = []
    current: str | None = None
    for line in md.splitlines():
        if line.startswith("## "):
            if stop_at and line.strip() == stop_at:
                break
            current = line[3:].strip()
            continue
        if section is not None and current != section:
            continue
        e = parse_entry(line)
        if e is not None:
            out.append(e)
    return out


def links(md: str) -> list[str]:
    return [m.group(1) for line in md.splitlines() if (m := _LINK.match(line.strip().removeprefix("- ").strip()))]
