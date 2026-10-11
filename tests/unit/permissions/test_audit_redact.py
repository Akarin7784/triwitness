from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from triwitness.core.redact import redact_text
from triwitness.permissions.audit import AuditLog


def test_redact_patterns() -> None:
    secrets = [
        "sk-" + "abcdef0123456789abcdef",
        "ghp_" + "A" * 36,
        "github_pat_" + "B" * 40,
        "AKIA" + "C" * 16,
    ]
    for s in secrets:
        assert s not in redact_text(f"x {s} y")
    assert "hunter2" not in redact_text("DB_PASSWORD=hunter2 make")
    assert "tok123" not in redact_text("curl -H 'Authorization: Bearer tok123'")
    assert redact_text("plain text") == "plain text"
    assert len(redact_text("a" * 5000, max_len=100)) <= 120


def test_audit_monthly_file(tmp_path: Path) -> None:
    log = AuditLog(tmp_path)
    ts = datetime(2026, 10, 31, 23, 30, tzinfo=ZoneInfo("UTC"))  # 北京时间已是 11 月
    p = log.record({"action": "ls", "decision": "allow"}, now=ts)
    assert p.name == "permissions-202611.jsonl"
    log.record({"action": "x" * 5000, "decision": "deny"}, now=ts)
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert len(lines[1]) < 2300


def test_redact_text_never_eats_json_escapes() -> None:
    """值的匹配止于反斜杠：`\\"` / `\\\\` / `\\n` 不会被吃掉一半（W5-13：脱敏后的 artifact 不是合法 JSON）。"""
    import json

    from triwitness.core.redact import redact_obj, redact_text

    for raw in ['echo "secret ===" && ls', 'API_KEY="abc123" x', "TOKEN=abc\\def", 'password: "p\\"w"',
                "authorization: Bearer abcdef0123", "x-api-key: k\\n"]:  # fmt: skip
        once = json.dumps({"a": raw})
        twice = json.dumps({"b": once})
        assert json.loads(redact_text(once))["a"] is not None
        assert json.loads(json.loads(redact_text(twice))["b"])["a"] is not None
    assert redact_text('API_KEY="abc123" x') == 'API_KEY="***" x'
    assert redact_obj({"k": ["TOKEN=abc", 1, None]}) == {"k": ["TOKEN=***", 1, None]}
