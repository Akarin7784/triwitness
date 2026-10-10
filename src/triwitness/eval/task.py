"""评测任务格式（spec 004 §4，W1-26）：Harbor task.toml（schema_version 1.x）+ `[tw]` 扩展。

对照 Harbor 官方文档（docs.harborframework.com/tasks/configuration，2026-10 查阅）：
- 顶层 `schema_version`（不是 `version`）；`[task] name = "org/name"`；`[metadata]` 为作者自定义；
- `[agent]` / `[verifier]` 的 `timeout_sec`；`[environment]` 用 `network_mode`（public / no-network / allowlist）、
  `cpus`、`memory_mb`、`storage_mb`、`docker_image`、`workdir`；
- 判分写 `/logs/verifier/reward.txt`（或 reward.json）。
TriWitness 自有字段只放在 `[tw]` 与 `[metadata]` 里，Harbor 读这些任务时会忽略它们。
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from triwitness.core.errors import TriWitnessError

SUPPORTED_SCHEMA_MAJOR = 1
NetworkMode = Literal["public", "no-network", "allowlist"]


class TaskFormatError(TriWitnessError):
    pass


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow")


class TaskSection(_Open):
    name: str  # org/name
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)


class TaskMeta(_Open):
    """Harbor 的 `[metadata]` 是自由字段；TriWitness 约定下面这些（防污染需要 created_at）。"""

    source: str = "synthetic"  # synthetic | github-issue | swe-rebench | ...
    repo: str | None = None
    base_commit: str | None = None
    difficulty: Literal["easy", "medium", "hard"] = "easy"
    tags: list[str] = Field(default_factory=list)
    created_at: str  # YYYY-MM-DD，真实日期
    license: str | None = None


class PhaseConfig(_Open):
    timeout_sec: float | None = None
    network_mode: NetworkMode | None = None
    user: str | None = None


class EnvironmentConfig(_Open):
    network_mode: NetworkMode = "public"  # Harbor 默认 public；TriWitness 任务要求显式 no-network
    allowed_hosts: list[str] = Field(default_factory=list)
    docker_image: str | None = None
    cpus: float | None = None
    memory_mb: int | None = None
    storage_mb: int | None = None
    workdir: str | None = None
    build_timeout_sec: float | None = None


class TwExt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_cmd: str = "pytest -q"
    fail_to_pass: list[str] = Field(default_factory=list)
    pass_to_pass: list[str] = Field(default_factory=list)
    max_cost_cny: float = Field(default=0.8, gt=0)


class TaskToml(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str
    task: TaskSection
    metadata: TaskMeta
    agent: PhaseConfig = Field(default_factory=PhaseConfig)
    verifier: PhaseConfig = Field(default_factory=PhaseConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    tw: TwExt = Field(default_factory=TwExt)

    @field_validator("schema_version")
    @classmethod
    def _major(cls, v: str) -> str:
        try:
            major = int(v.split(".", 1)[0])
        except ValueError as e:
            raise ValueError(f"schema_version 格式不对：{v}") from e
        if major != SUPPORTED_SCHEMA_MAJOR:
            raise ValueError(f"只支持 schema_version 1.x，得到 {v}")
        return v


class EvalTask(BaseModel):
    id: str
    path: Path
    config: TaskToml
    instruction: str

    @property
    def meta(self) -> TaskMeta:
        return self.config.metadata

    @property
    def tw(self) -> TwExt:
        return self.config.tw

    @property
    def tests_dir(self) -> Path:
        return self.path / "tests"

    @property
    def solution_dir(self) -> Path:
        return self.path / "solution"

    @property
    def environment_dir(self) -> Path:
        return self.path / "environment"

    @property
    def agent_timeout_sec(self) -> float:
        return self.config.agent.timeout_sec or 1800.0

    @property
    def verifier_timeout_sec(self) -> float:
        return self.config.verifier.timeout_sec or 600.0

    def image_tag(self) -> str:
        """镜像按 environment/ 全部内容哈希打 tag（内容不变就复用缓存）。"""
        if self.config.environment.docker_image:
            return self.config.environment.docker_image
        return f"tw-task/{self.id}:{context_hash(self.environment_dir)}"


def context_hash(directory: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in directory.rglob("*") if p.is_file()):
        rel = f.relative_to(directory).as_posix()
        h.update(rel.encode() + b"\0")
        h.update(f.read_bytes().replace(b"\r\n", b"\n") + b"\0")  # 与检出时的换行风格无关
    return h.hexdigest()[:12]


def _fmt_errors(e: ValidationError) -> str:
    return "；".join(f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors())


def load_task(path: Path) -> EvalTask:
    """解析任务目录；结构或字段不对时抛 TaskFormatError（列出全部问题）。"""
    path = Path(path)
    problems: list[str] = []
    toml_path = path / "task.toml"
    if not toml_path.is_file():
        raise TaskFormatError(f"{path}：缺少 task.toml")
    try:
        raw: dict[str, Any] = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise TaskFormatError(f"{toml_path}：TOML 语法错误：{e}") from e
    try:
        cfg = TaskToml.model_validate(raw)
    except ValidationError as e:
        raise TaskFormatError(f"{toml_path}：{_fmt_errors(e)}") from e
    tid = cfg.task.name.rsplit("/", 1)[-1]
    if tid != path.name:
        problems.append(f"task.name 的名字部分（{tid}）应与目录名（{path.name}）一致")
    instr = path / "instruction.md"
    if not instr.is_file() or not instr.read_text(encoding="utf-8").strip():
        problems.append("缺少或空的 instruction.md")
    if not cfg.environment.docker_image and not (path / "environment" / "Dockerfile").is_file():
        problems.append("缺少 environment/Dockerfile（或在 [environment] 写 docker_image）")
    if not (path / "tests" / "test.sh").is_file():
        problems.append("缺少 tests/test.sh")
    if not (path / "solution" / "solve.sh").is_file():
        problems.append("缺少 solution/solve.sh")
    if cfg.environment.network_mode != "no-network":
        problems.append('TriWitness 评测任务要求 [environment] network_mode = "no-network"（依赖在构建镜像时装好）')
    if not cfg.tw.fail_to_pass:
        problems.append("[tw] fail_to_pass 不能为空")
    if problems:
        raise TaskFormatError(f"{path}：" + "；".join(problems))
    return EvalTask(id=tid, path=path, config=cfg, instruction=instr.read_text(encoding="utf-8"))


def discover(root: Path) -> list[Path]:
    return sorted(p.parent for p in Path(root).glob("*/task.toml"))


__all__ = ["EvalTask", "TaskFormatError", "TaskMeta", "TaskToml", "TwExt", "context_hash", "discover", "load_task"]
