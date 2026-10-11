"""W4-13 注入缺陷集完整性 + W4-14 消融脚本（不真调模型）。"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("reviewer_ablation", ROOT / "scripts" / "reviewer_ablation.py")
assert spec and spec.loader
ab = importlib.util.module_from_spec(spec)
sys.modules["reviewer_ablation"] = ab  # dataclass 需要模块已注册
spec.loader.exec_module(ab)


def test_defect_set_is_paired_and_complete() -> None:
    items = ab.manifest()
    defects = [i for i in items if i["kind"] == "defect"]
    cleans = [i for i in items if i["kind"] == "clean"]
    assert len(defects) == len(cleans) == 20
    assert {i["task"] for i in defects} == {i["task"] for i in cleans}
    for it in items:
        d = ab.ITEMS / it["id"]
        meta = json.loads((d / "item.json").read_text(encoding="utf-8"))
        assert meta["kind"] == it["kind"]
        patch = (d / "patch.diff").read_text(encoding="utf-8")
        assert patch.startswith("diff --git ") and "+++ " in patch
        assert (d / "issue.md").read_text(encoding="utf-8").strip()
        files = [ln[6:] for ln in patch.splitlines() if ln.startswith("+++ b/")]
        assert files and not any("tests/" in f or f.split("/")[-1].startswith("test_") for f in files)
        if it["kind"] == "defect":
            t = it["defect"]
            assert meta["truth"] == t
            assert t["file"] in files and t["severity"] in ("blocker", "major") and t["in_changed_lines"]


def test_prepare_builds_base_plus_candidate_commit(tmp_path: Path) -> None:
    ab.cmd_prepare(tmp_path, ["d01-defect"], tmp_path / "repos")
    repo = tmp_path / "repos" / "d01-defect"
    log = subprocess.run(["git", "log", "--format=%s"], cwd=repo, capture_output=True, text=True).stdout.split()
    assert log == ["candidate", "patch", "base"]
    diff = ab.git("diff", "HEAD~1", "HEAD", cwd=repo)
    assert "csvkit_lite/parse.py" in diff


def _row(item: str, kind: str, arm: str, findings: list[dict[str, Any]], verdict: str = "approve") -> dict[str, Any]:
    truth = {"file": "pkg/a.py", "line": 10, "category": "off_by_one"} if kind == "defect" else None
    return {"item": item, "kind": kind, "truth": truth, "arm": arm, "rep": 0, "verdict": verdict,
            "findings": findings, "cost_cny": 0.01}  # fmt: skip


def test_classify_location_and_false_alarm() -> None:
    near = {"severity": "major", "file": "./pkg/a.py", "line": 12, "message": "x"}
    far = {"severity": "blocker", "file": "pkg/a.py", "line": 40, "message": "x"}
    c = ab.classify(_row("x", "defect", "a", [near]), 3)
    assert c["hit"] and not c["hit_blocker"] and c["loose"] and not c["blocked"]
    c = ab.classify(_row("x", "defect", "a", [far], "request_changes"), 3)
    assert not c["hit"] and c["loose"] and c["blocked"]
    assert not ab.classify(_row("x", "defect", "a", [{**near, "severity": "minor"}]), 3)["hit"]
    assert ab.classify(_row("y", "clean", "a", [far], "request_changes"), 3)["fp"]
    c = ab.classify(_row("y", "clean", "a", [near]), 3)
    assert not c["fp"] and c["fp_major"]


def test_score_reports_consensus(tmp_path: Path) -> None:
    res = tmp_path / "results"
    res.mkdir()
    hit = {"severity": "blocker", "file": "pkg/a.py", "line": 10, "message": "x"}
    rows = [_row("d1-defect", "defect", "adversarial", [hit], "request_changes"),
            _row("d1-defect", "defect", "checklist_t03", []),
            _row("d1-clean", "clean", "adversarial", [hit], "request_changes"),
            _row("d1-clean", "clean", "checklist_t03", [])]  # fmt: skip
    for r in rows:
        (res / f"{r['item']}__{r['arm']}__r0.json").write_text(json.dumps(r), encoding="utf-8")
    ab.cmd_score(tmp_path, 3)
    s = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert s["adversarial"]["hit"] == 1 and s["adversarial"]["fp"] == 1
    assert s["consensus_t03"]["hit"] == 0 and s["consensus_t03"]["fp"] == 0
    assert "consensus_t03" in (tmp_path / "report.md").read_text(encoding="utf-8")
    assert (tmp_path / "findings.csv").is_file()


def test_wilson_and_peak() -> None:
    lo, hi = ab.wilson(10, 20)
    assert 0.27 < lo < 0.3 and 0.7 < hi < 0.73
    assert ab.wilson(0, 0) == (0.0, 0.0)
    assert ab.is_peak(datetime(2026, 10, 12, 10, 0, tzinfo=ab.BJ))  # 周一 10:00
    assert not ab.is_peak(datetime(2026, 10, 12, 12, 30, tzinfo=ab.BJ))
    assert not ab.is_peak(datetime(2026, 10, 11, 10, 0, tzinfo=ab.BJ))  # 周日


async def test_arm_router_flash_only_and_sampling(monkeypatch: pytest.MonkeyPatch) -> None:
    from triwitness.llm.router import Router
    from triwitness.llm.types import LLMRequest

    seen: list[Any] = []

    async def fake_complete(self: Any, req: Any, **kw: Any) -> Any:
        seen.append((req, self.routes["reviewer"]))
        return None

    monkeypatch.setattr(Router, "complete", fake_complete)
    r = ab._arm_router(ab.ARMS["checklist_t03"])
    await r.complete(LLMRequest(role="reviewer", messages=[], effort="high"))
    req, route = seen[-1]
    assert req.temperature == 0.3 and req.effort is None and route.thinking is False
    assert route.model == ab.MODEL and not route.fallback
    r = ab._arm_router(ab.ARMS["adversarial"])
    await r.complete(LLMRequest(role="reviewer", messages=[]))
    req, route = seen[-1]
    assert req.effort == "max" and route.thinking is True and req.temperature is None


async def test_arm_router_forces_arm_thinking_over_variant_default() -> None:
    """第二轮与第一轮可比：臂定义的思考开关覆盖变体默认（checklist 默认非思考，adversarial 臂必须思考）。"""
    from triwitness.llm.types import LLMRequest, Message

    seen: list[Any] = []

    class _Client:
        async def complete(self, req: Any, model: str, **kw: Any) -> Any:
            from triwitness.llm.types import LLMResponse

            seen.append(req)
            from triwitness.core.models import Usage

            return LLMResponse(message=Message(role="assistant", content="x"), raw={}, source="fake", usage=Usage(),
                               served_model="fake", finish_reason="stop")  # fmt: skip

    for arm in ("adversarial", "checklist_t10"):
        r = ab._arm_router(ab.ARMS[arm])
        r.clients = {"deepseek": _Client()}
        await r.complete(LLMRequest(role="reviewer", messages=[Message(role="user", content="q")],
                                    thinking_override=False))  # fmt: skip
    assert (seen[0].thinking, seen[0].effort) == (True, "max")
    assert (seen[1].thinking, seen[1].temperature) == (False, 1.0)


def test_bundle_keeps_only_inconclusive_trajectories(tmp_path: Path) -> None:
    import zipfile

    out = tmp_path / "ablation"
    (out / "results").mkdir(parents=True)
    for stem, verdict in (("d01-clean__adversarial__r1", None), ("d01-defect__adversarial__r1", "approve")):
        (out / "results" / f"{stem}.json").write_text(json.dumps({"verdict": verdict}), encoding="utf-8")
        (out / "runs" / stem).mkdir(parents=True)
        (out / "runs" / stem / "trajectory.jsonl").write_text("{}\n", encoding="utf-8")
    z = zipfile.ZipFile(ab.cmd_bundle(out, tmp_path / "none.sqlite"))
    names = set(z.namelist())
    assert "ablation/runs/d01-clean__adversarial__r1/trajectory.jsonl" in names
    assert "ablation/runs/d01-defect__adversarial__r1/trajectory.jsonl" not in names
    assert {
        "ablation/results/d01-clean__adversarial__r1.json",
        "ablation/results/d01-defect__adversarial__r1.json",
    } <= names
