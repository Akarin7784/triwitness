"""`tw task validate`（W1-26）：构建镜像 → 不打补丁跑 test.sh（reward 必须 0）→ 跑 solve.sh 后再跑（必须 1）。

容器一律 network_mode=none、带 tw.managed 标签（`tw sandbox gc` 能回收），跑完即删。
"""

from __future__ import annotations

import asyncio
import io
import json
import tarfile
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from triwitness.eval.task import EvalTask
from triwitness.sandbox.docker import LABEL, _client, _tar_bytes

LOG_TAIL = 4000


class Phase(BaseModel):
    reward: float | None
    exit_code: int
    log_tail: str


class ValidationReport(BaseModel):
    task_id: str
    image: str
    image_cached: bool
    without_solution: Phase
    with_solution: Phase
    problems: list[str]

    @property
    def ok(self) -> bool:
        return not self.problems


def _dir_entries(src: Path, dest: str) -> list[tuple[str, bytes | None, int]]:
    out: list[tuple[str, bytes | None, int]] = [(dest, None, 0o755)]
    for p in sorted(src.rglob("*")):
        name = f"{dest}/{p.relative_to(src).as_posix()}"
        if p.is_dir():
            out.append((name, None, 0o755))
        else:
            data = p.read_bytes()
            if p.suffix == ".sh":
                data = data.replace(b"\r\n", b"\n")  # Windows 检出的脚本也能跑
            out.append((name, data, 0o755 if p.suffix == ".sh" else 0o644))
    return out


def ensure_image(task: EvalTask, client: Any) -> tuple[str, bool]:
    from docker.errors import ImageNotFound

    tag = task.image_tag()
    try:
        client.images.get(tag)
        return tag, True
    except ImageNotFound:
        pass
    if task.config.environment.docker_image:
        client.images.pull(tag)
        return tag, False
    client.images.build(path=str(task.environment_dir), tag=tag, rm=True, labels={"tw.kind": "task-image"})
    return tag, False


def _read_reward(container: Any) -> float | None:
    for name in ("reward.txt", "reward.json"):
        try:
            stream, _ = container.get_archive(f"/logs/verifier/{name}")
        except Exception:
            continue
        with tarfile.open(fileobj=io.BytesIO(b"".join(stream))) as tf:
            m = tf.next()
            f = tf.extractfile(m) if m else None
            text = f.read().decode("utf-8", "replace").strip() if f else ""
        if name == "reward.json":
            try:
                val = json.loads(text)
                return float(val.get("reward", 0.0)) if isinstance(val, dict) else float(val)
            except (ValueError, TypeError, AttributeError):
                return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def run_verifier(
    task: EvalTask, container: Any, *, user: str = "root", solution: bool = False, workdir: str | None = None
) -> Phase:
    """在给定容器里放入 /tests（及可选 /solution），可选先跑 solve.sh，再跑 test.sh 并读 reward。"""
    workdir = workdir or task.config.environment.workdir
    entries = [("logs", None, 0o777), ("logs/verifier", None, 0o777), ("logs/agent", None, 0o777)]
    entries += _dir_entries(task.tests_dir, "tests")
    if solution:
        entries += _dir_entries(task.solution_dir, "solution")
    container.put_archive("/", _tar_bytes(entries, uid=0))
    logs: list[str] = []
    if solution:
        t = int(task.agent_timeout_sec)
        code, out = container.exec_run(["timeout", str(t), "bash", "/solution/solve.sh"], workdir=workdir, user=user)
        logs.append(f"$ bash /solution/solve.sh → {code}\n{out.decode('utf-8', 'replace')}")
    t = int(task.verifier_timeout_sec)
    env = {k: str(v) for k, v in (getattr(task.config.verifier, "env", None) or {}).items()}
    if user != "root":
        # 非 root（Grader 用 uid 1000，镜像里没有对应用户）时 HOME 默认是 /，不可写；任务校验是 root 跑的，
        # 参考解能过、判分却必挂（W2-25：ultraplot-696 mkdir /.config、xcp_d-1433 mkdir /.cache）。
        env.setdefault("HOME", "/tmp")
    code, out = container.exec_run(
        ["timeout", str(t), "bash", "/tests/test.sh"], workdir=workdir, environment=env, user=user
    )
    logs.append(f"$ bash /tests/test.sh → {code}\n{out.decode('utf-8', 'replace')}")
    log = "\n".join(logs)
    return Phase(reward=_read_reward(container), exit_code=code, log_tail=log[-LOG_TAIL:])


def run_phase(task: EvalTask, client: Any, image: str, *, apply_solution: bool) -> Phase:
    c = client.containers.run(
        image,
        ["sleep", "infinity"],
        detach=True,
        network_mode="none",
        labels={LABEL: "true", "tw.kind": "task-validate"},
        name=f"tw-validate-{task.id}-{uuid.uuid4().hex[:6]}",
        working_dir=task.config.environment.workdir,
        user="root",
    )
    try:
        return run_verifier(task, c, solution=apply_solution)
    finally:
        c.remove(force=True)


def validate_sync(task: EvalTask, client: Any | None = None) -> ValidationReport:
    client = client or _client()
    image, cached = ensure_image(task, client)
    before = run_phase(task, client, image, apply_solution=False)
    after = run_phase(task, client, image, apply_solution=True)
    problems: list[str] = []
    if before.reward is None:
        problems.append("未打补丁时 test.sh 没写出 /logs/verifier/reward.txt")
    elif before.reward != 0:
        problems.append(f"未打补丁时 reward 应为 0，得到 {before.reward}（测试没复现问题）")
    if after.reward is None:
        problems.append("应用 solve.sh 后 test.sh 没写出 reward")
    elif after.reward != 1:
        problems.append(f"应用 solve.sh 后 reward 应为 1，得到 {after.reward}（参考解或测试有问题）")
    return ValidationReport(
        task_id=task.id,
        image=image,
        image_cached=cached,
        without_solution=before,
        with_solution=after,
        problems=problems,
    )


async def validate(task: EvalTask) -> ValidationReport:
    return await asyncio.to_thread(validate_sync, task)


__all__ = ["Phase", "ValidationReport", "ensure_image", "run_phase", "run_verifier", "validate", "validate_sync"]
