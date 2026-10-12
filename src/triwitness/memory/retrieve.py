"""经验片段检索（spec 013 §4.2）：不依赖向量库的词法相似度（英文词 + 中文二元组，IDF 加权）。

经验片段每个仓库通常几十到几百条，词法检索足够；接口留给以后换向量索引。
"""

from __future__ import annotations

import math
import re
from collections import Counter

from triwitness.memory.format import Entry

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}|\d{2,}")
_CJK = re.compile(r"[\u4e00-\u9fff]+")
_STOP = frozenset({"the", "and", "for", "with", "this", "that", "from", "are", "was", "not", "but", "you", "use",
                   "根因", "有效", "做法", "无效"})  # fmt: skip


def tokens(text: str) -> list[str]:
    out = [w.lower() for w in _WORD.findall(text)]
    for run in _CJK.findall(text):
        out += [run[i : i + 2] for i in range(max(1, len(run) - 1))]
    return [t for t in out if t not in _STOP]


def rank(query: str, entries: list[Entry], k: int = 3, min_score: float = 0.05) -> list[Entry]:
    if not entries:
        return []
    docs = [Counter(tokens(e.text + " " + e.meta.get("kind", ""))) for e in entries]
    df: Counter[str] = Counter()
    for d in docs:
        df.update(d.keys())
    n = len(docs)
    q = Counter(tokens(query))
    scored = []
    for e, d in zip(entries, docs, strict=True):
        if not d:
            continue
        s = sum(min(c, d[t]) * math.log(1 + n / df[t]) for t, c in q.items() if t in d)
        s /= math.sqrt(sum(d.values()))
        if s >= min_score:
            scored.append((s, e))
    scored.sort(key=lambda x: (-x[0], x[1].id))
    return [e for _, e in scored[:k]]
