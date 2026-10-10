"""tw-events/1 golden fixture 校验（W1-36）。"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from triwitness.core.events import DISPLAY_MAX, PAYLOADS, TrajectoryEvent, dump_schema, parse_event_line

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = sorted((ROOT / "evals" / "fixtures" / "events").glob("*.jsonl"))
SECRET = re.compile(r"sk-[A-Za-z0-9]{8,}|DEEPSEEK_API_KEY|Bearer\s", re.I)


def _events(path: Path) -> list[TrajectoryEvent]:
    return [parse_event_line(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_fixtures_exist() -> None:
    assert {p.stem for p in FIXTURES} == {"success", "failure", "budget_exceeded", "recorded"}


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_fixture_is_valid(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert not SECRET.search(text), "fixture 里不能出现密钥样式字符串"
    evs = _events(path)
    assert [e.seq for e in evs] == list(range(len(evs))), "seq 必须从 0 连续"
    assert all(e.v == 1 for e in evs)
    assert len({e.task_id for e in evs}) == 1 and len({e.run_id for e in evs}) == 1
    assert [e.ts for e in evs] == sorted(e.ts for e in evs)
    assert all(e.ts.utcoffset() is not None and e.ts.utcoffset().total_seconds() == 0 for e in evs)  # type: ignore[union-attr]
    assert evs[0].kind == "task_started" and evs[-1].kind == "task_finished"
    for e in evs:
        p = e.typed_payload()
        assert p.display is None or len(p.display) <= DISPLAY_MAX
        if e.kind == "model_call":
            assert e.payload["model"] == "deepseek-flash" and "pro" not in e.payload["served_model"]
            assert e.payload["peak"] is False, "fixture 调用都应在空闲时段"


def test_success_covers_ui_kinds() -> None:
    kinds = {e.kind for e in _events(ROOT / "evals/fixtures/events/success.jsonl")}
    need = {
        "task_started",
        "state_change",
        "model_call",
        "tool_call",
        "checkpoint",
        "verification",
        "review",
        "task_finished",
    }
    assert need <= kinds


def test_budget_fixture_ends_over_budget() -> None:
    evs = _events(ROOT / "evals/fixtures/events/budget_exceeded.jsonl")
    assert evs[-2].kind in {"state_change", "error"}
    last = evs[-1].typed_payload()
    assert last.status == "budget_exceeded"  # type: ignore[attr-defined]
    assert last.cost_report.total_cny > last.cost_report.budget_cny  # type: ignore[attr-defined]


def test_payload_kind_mismatch_rejected() -> None:
    line = json.dumps(
        {
            "v": 1,
            "seq": 0,
            "ts": "2026-10-10T00:00:00Z",
            "task_id": "t",
            "run_id": "r",
            "kind": "tool_call",
            "payload": {"label": "x"},
        }
    )
    with pytest.raises(ValueError):
        parse_event_line(line)


def test_unknown_payload_fields_allowed() -> None:
    line = json.dumps(
        {
            "v": 1,
            "seq": 0,
            "ts": "2026-10-10T00:00:00Z",
            "task_id": "t",
            "run_id": "r",
            "kind": "checkpoint",
            "payload": {"label": "x", "future": 1},
        }
    )
    assert parse_event_line(line).typed_payload().model_extra == {"future": 1}


def test_schema_file_up_to_date() -> None:
    schema_path = ROOT / "schemas" / "tw-events-1.schema.json"
    assert schema_path.read_text(encoding="utf-8") == dump_schema()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert set(schema["discriminator"]["mapping"]) == set(PAYLOADS)


def test_fixtures_up_to_date() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_event_fixtures.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
