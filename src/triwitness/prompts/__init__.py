"""版本化提示（04 §3.3 原则 4，W2-12）：`prompts/<name>.md`，头部 `---` 块写 name / version。

版本号写入 Trajectory（task_started.prompt_versions）与 harness config_hash，消融可追溯到具体提示版本。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).parent


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    text: str

    @property
    def tag(self) -> str:
        return f"{self.name}@v{self.version}"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> Prompt:
    raw = (DIR / f"{name}.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    meta: dict[str, str] = {}
    body = raw
    if raw.startswith("---\n"):
        head, _, body = raw[4:].partition("\n---\n")
        for line in head.splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    if "version" not in meta:
        raise ValueError(f"prompts/{name}.md 缺少 version")
    return Prompt(name=meta.get("name", name), version=meta["version"], text=body.strip())


__all__ = ["Prompt", "load_prompt"]
