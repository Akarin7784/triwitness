"""外部任务的复现位置提示（不依赖 harbor / bash，Windows 上也跑）。"""

from __future__ import annotations

from triwitness.integrations.harbor_sandbox import REPRO_DIR_DEFAULT, external_task_prompt


def test_prompt_points_repro_outside_task_dir_by_default() -> None:
    out = external_task_prompt("Write /app/polyglot/main.py.c\n")
    assert out.startswith("Write /app/polyglot/main.py.c")
    assert REPRO_DIR_DEFAULT == "/tmp/tw_repro" and f"{REPRO_DIR_DEFAULT}/" in out
    assert "不要放进任务目录" in out


def test_prompt_hint_can_be_disabled() -> None:
    assert external_task_prompt("task", "") == "task"
    assert external_task_prompt("task", None) == "task"
