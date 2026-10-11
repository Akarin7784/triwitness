"""桌面端输入（UI-21）：附件与用户说明（个人偏好 / 风格 / 项目说明）拼进任务描述。

- 文本附件内联为带文件名的代码块（默认单个 20K 字、合计 60K 字封顶，超出截断并注明）
- 传 `max_chars`（= harness 的任务分配）时，用户设置 + Issue + 附件整体落在这个预算内：附件按剩余预算截断并注明，
  不会再被 `ContextManager.task_message` 二次头尾截断（以前附件中段会被悄悄切掉）
- 图片 / 二进制不读内容：当前模型（deepseek-flash）只读文字，只列出文件名与大小，诚实说明
- 用户说明放在任务描述前，作为“用户设置”而非 Issue 正文；同样封顶
附件原件复制到 run_dir/attachments/ 留档。
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

PER_FILE_CHARS = 20_000
TOTAL_CHARS = 60_000
GUIDANCE_CHARS = 8_000
MAX_FILES = 20
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic", ".tif", ".tiff", ".svgz"})


@dataclass
class ComposedTask:
    prompt: str
    texts: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    binaries: list[str] = field(default_factory=list)
    truncated: list[str] = field(default_factory=list)


def _fence(text: str) -> str:
    n = 3
    while "`" * n in text:
        n += 1
    return "`" * n


def _read_text(p: Path) -> str | None:
    data = p.read_bytes()
    if b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("gb18030")
        except UnicodeDecodeError:
            return None


TASK_SHARE = 0.85  # 任务分配里留给首轮描述的比例：续跑说明 / 验证反馈会追加在后面
BLOCK_OVERHEAD = 200  # 每个附件块的标题 / 代码围栏


def compose_task(
    issue: str, *, guidance: str | None = None, attachments: list[Path] | None = None, max_chars: int | None = None
) -> ComposedTask:
    files = list(attachments or [])[:MAX_FILES]
    out = ComposedTask(prompt="")
    parts: list[str] = []
    g = (guidance or "").strip()
    if g:
        if len(g) > GUIDANCE_CHARS:
            g = g[:GUIDANCE_CHARS] + "\n…（已截断）"
        parts.append(f"## 用户设置（偏好 / 风格 / 项目说明）\n\n{g}")
    parts.append(issue.strip())
    budget = TOTAL_CHARS
    per_file = PER_FILE_CHARS
    if max_chars is not None:
        budget = int(max_chars * TASK_SHARE) - sum(len(p) for p in parts) - BLOCK_OVERHEAD * (len(files) + 1)
        per_file = max(PER_FILE_CHARS, budget // 2)
    blocks: list[str] = []
    for p in files:
        name = p.name
        size = p.stat().st_size
        if p.suffix.lower() in IMAGE_SUFFIXES:
            out.images.append(name)
            blocks.append(f"- 图片 `{name}`（{size} 字节）：当前模型只能读文字，未读取图片内容")
            continue
        text = _read_text(p)
        if text is None:
            out.binaries.append(name)
            blocks.append(f"- 二进制文件 `{name}`（{size} 字节）：未读取内容")
            continue
        cap = min(per_file, budget)
        if cap <= 0:
            out.truncated.append(name)
            blocks.append(f"- `{name}`：附件总量已达上限，未内联")
            continue
        body = text
        if len(body) > cap:
            body = body[:cap] + "\n…（已截断）"
            out.truncated.append(name)
        budget -= len(body) + BLOCK_OVERHEAD
        out.texts.append(name)
        f = _fence(body)
        blocks.append(f"### {name}\n\n{f}\n{body}\n{f}")
    if blocks:
        parts.append("## 附件\n\n" + "\n\n".join(blocks))
    out.prompt = "\n\n".join(parts)
    return out


def archive_attachments(files: list[Path], run_dir: Path) -> None:
    dest = run_dir / "attachments"
    for p in files[:MAX_FILES]:
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest / p.name)
