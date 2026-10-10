"""评测套件（W2-23）：evals/suites/<name>.yaml 冻结任务清单；dev / test / dev-smoke。

- 套件文件列出任务 id 与来源 / 日期 / 难度 / 许可证，并带 `digest`：所有任务目录内容的哈希。任务内容被改动时
  `check_suite` 报错——冻结的切分不能悄悄变化（要改就重新生成并在变更记录里写明）；
- test 集只用于出报告：`tw eval run --suite test` 需要显式 `--allow-test`（防止在 test 上调参）。
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from triwitness.eval.task import context_hash, discover

SUITES = Path("evals/suites")
TASKS = Path("evals/tasks")
REPORT_ONLY = {"test"}


class SuiteTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source: str
    created_at: str
    difficulty: Literal["easy", "medium", "hard"]
    license: str


class Suite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str = ""
    frozen: bool = True
    parent: str | None = None  # dev-smoke ⊂ dev
    digest: str
    tasks: list[SuiteTask] = Field(min_length=1)

    @property
    def ids(self) -> list[str]:
        return [t.id for t in self.tasks]


def task_dir(task_id: str, root: Path = TASKS) -> Path:
    hits = [p for p in discover_all(root) if p.name == task_id]
    if len(hits) != 1:
        raise FileNotFoundError(f"任务 {task_id} 在 {root} 下找到 {len(hits)} 处")
    return hits[0]


def discover_all(root: Path = TASKS) -> list[Path]:
    return sorted(p for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith("_") for p in discover(d))


def digest(dirs: list[Path]) -> str:
    h = hashlib.sha256()
    for d in sorted(dirs, key=lambda p: p.name):
        h.update(d.name.encode() + b"\0" + context_hash(d).encode() + b"\0")
    return h.hexdigest()[:16]


def load_suite(name: str, root: Path = SUITES) -> Suite:
    return Suite.model_validate(yaml.safe_load((root / f"{name}.yaml").read_text(encoding="utf-8")))


def suite_dirs(name: str, *, suites: Path = SUITES, tasks: Path = TASKS) -> list[Path]:
    """套件文件存在时按清单解析；否则退回 evals/tasks/<name> 目录（W1 行为）。"""
    if (suites / f"{name}.yaml").exists():
        return [task_dir(t, tasks) for t in load_suite(name, suites).ids]
    return discover(tasks / name)


def check_suite(name: str, *, suites: Path = SUITES, tasks: Path = TASKS) -> list[str]:
    s = load_suite(name, suites)
    problems = []
    if s.name != name:
        problems.append(f"name={s.name} 与文件名 {name} 不符")
    if len(set(s.ids)) != len(s.ids):
        problems.append("任务 id 重复")
    try:
        dirs = suite_dirs(name, suites=suites, tasks=tasks)
    except FileNotFoundError as e:
        return [*problems, str(e)]
    if s.frozen and digest(dirs) != s.digest:
        problems.append(f"冻结套件 {name} 的任务内容变了（digest {digest(dirs)} ≠ {s.digest}）")
    if s.parent and not set(s.ids) <= set(load_suite(s.parent, suites).ids):
        problems.append(f"{name} 不是 {s.parent} 的子集")
    return problems


def dump_suite(s: Suite, root: Path = SUITES) -> Path:
    path = root / f"{s.name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(s.model_dump(exclude_none=True), allow_unicode=True, sort_keys=False, width=200)
    path.write_text("# 冻结的评测套件（W2-23）；由 scripts/task_factory.py split 生成，勿手改（digest 校验）\n" + body)
    return path


__all__ = ["REPORT_ONLY", "Suite", "SuiteTask", "check_suite", "digest", "discover_all", "dump_suite", "load_suite",
           "suite_dirs", "task_dir"]  # fmt: skip
