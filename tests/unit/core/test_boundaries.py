import re
from pathlib import Path

CORE = Path(__file__).resolve().parents[3] / "src" / "triwitness" / "core"


def test_core_depends_on_nothing_else_in_triwitness() -> None:
    pat = re.compile(r"^\s*(?:from|import)\s+triwitness\.(?!core\b)", re.M)
    offenders = [p.name for p in CORE.glob("*.py") if pat.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
