"""W8-03 轨迹导出：四种格式 + 样例夹具（¥0，不调模型、不拉镜像）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from triwitness.eval.traj_export import (
    FORMATS,
    export_harbor,
    export_html,
    export_openai,
    export_rlvr,
    export_run,
)

# 仓库内真实评测产物（已脱敏）
SAMPLE_RUN = Path("evals/results/2026-10-10T13-10-16/baseline-deepseek/csv-blank-line/1")
FIXTURE_OUT = Path("evals/fixtures/traj_export")


@pytest.fixture(scope="module")
def run_dir() -> Path:
    if not (SAMPLE_RUN / "trajectory.jsonl").is_file():
        pytest.skip(f"缺少样例轨迹 {SAMPLE_RUN}")
    return SAMPLE_RUN


def test_export_openai_messages(run_dir: Path) -> None:
    data = export_openai(run_dir)
    assert data["format"] == "openai-messages/v1"
    assert data["task_id"] == "csv-blank-line"
    assert data["reward"] == 1.0
    msgs = data["messages"]
    assert msgs[0]["role"] == "system"
    assert any(m["role"] == "user" for m in msgs)
    assert msgs[-1]["role"] == "assistant"
    # 中间应有 tool 轮次
    assert any(m["role"] == "tool" for m in msgs)


def test_export_rlvr(run_dir: Path) -> None:
    data = export_rlvr(run_dir)
    assert data["format"] == "trajectory-reward/v1"
    assert data["reward"] == 1.0
    assert data["resolved"] is True
    kinds = {s["type"] for s in data["steps"]}
    assert "model_call" in kinds and "tool_call" in kinds


def test_export_harbor(run_dir: Path, tmp_path: Path) -> None:
    out = export_harbor(run_dir, tmp_path / "trial")
    assert (out / "verifier" / "reward.txt").read_text(encoding="utf-8").strip() == "1.0"
    trial = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert trial["verifier_result"]["rewards"]["reward"] == 1.0
    assert trial["task_name"] == "csv-blank-line"
    assert (out / "agent" / "trajectory.jsonl").is_file()


def test_export_html(run_dir: Path) -> None:
    text = export_html(run_dir)
    assert text.startswith("<!DOCTYPE html>")
    assert "csv-blank-line" in text
    assert "reward=1.0" in text
    assert "model_call" in text


def test_export_run_all(run_dir: Path, tmp_path: Path) -> None:
    results = export_run(run_dir, tmp_path / "out", formats=["all"])
    names = {r.format for r in results}
    assert names == set(FORMATS)
    assert (tmp_path / "out" / "openai-messages.json").is_file()
    assert (tmp_path / "out" / "trajectory-reward.json").is_file()
    assert (tmp_path / "out" / "harbor-trial" / "result.json").is_file()
    assert (tmp_path / "out" / "replay.html").is_file()


def test_export_missing_traj(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        export_openai(tmp_path)


def test_fixture_samples_match_formats() -> None:
    """仓库内样例夹具齐全（供文档与下游引用）。"""
    if not FIXTURE_OUT.is_dir():
        pytest.skip("fixtures not generated yet")
    assert (FIXTURE_OUT / "openai-messages.json").is_file()
    assert (FIXTURE_OUT / "trajectory-reward.json").is_file()
    assert (FIXTURE_OUT / "harbor-trial" / "result.json").is_file()
    assert (FIXTURE_OUT / "replay.html").is_file()
    assert (FIXTURE_OUT / "README.md").is_file()
