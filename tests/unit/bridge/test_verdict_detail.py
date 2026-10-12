"""结论卡「证据不足」的下一步提示需要的细节（真实 run r_01M4RVEZWKASMK9HYES8RPTFK3 的 evidence.json）。"""

from __future__ import annotations

import json
from pathlib import Path

from triwitness.bridge.stdio import changed_files, verdict_detail
from triwitness.core.models import Evidence

FIX = Path(__file__).parents[2] / "fixtures" / "bridge" / "pelican_inconclusive_evidence.json"


def test_changed_files_skips_deleted_and_dupes() -> None:
    patch = "+++ b/index.html\n+++ /dev/null\n+++ b/tests/t.py\n+++ b/index.html\n"
    assert changed_files(patch) == ["index.html", "tests/t.py"]


def test_verdict_detail_from_real_evidence(tmp_path: Path) -> None:
    ev = Evidence.model_validate(json.loads(FIX.read_text(encoding="utf-8")))
    (tmp_path / "patch.diff").write_text("+++ b/index.html\n+++ b/tests/tw_repro/test_issue_1.py\n", encoding="utf-8")
    d = verdict_detail(ev, tmp_path)
    assert d["repro_status"] == "reproduced"
    assert d["claim_flags"] == ["issue_underspecified"]
    assert d["anticheat_flags"] == []
    assert d["regression_blind"] is False
    assert d["changed_files"] == ["index.html", "tests/tw_repro/test_issue_1.py"]


def test_verdict_detail_without_evidence(tmp_path: Path) -> None:
    assert verdict_detail(None, tmp_path) == {}
