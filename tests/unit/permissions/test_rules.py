import pytest

from triwitness.core.errors import ConfigError
from triwitness.permissions.rules import match_command, match_domain, match_mcp, parse_rule


@pytest.mark.parametrize(
    ("raw", "category", "pattern"),
    [
        ("Bash(npm run test:*)", "Bash", "npm run test *"),
        ("bash(git  status)", "Bash", "git status"),
        ("Read(./.env)", "Read", "./.env"),
        ("read_file(**/*.pem)", "Read", "**/*.pem"),
        ("Fetch(domain:github.com)", "Fetch", "github.com"),
        ("Mcp(github__*)", "Mcp", "github__*"),
        ("Bash", "Bash", None),
    ],
)
def test_parse(raw: str, category: str, pattern: str | None) -> None:
    r = parse_rule(raw, "allow", "user")
    assert r.category == category
    assert r.pattern == pattern


@pytest.mark.parametrize("bad", ["Bash(", "Nope(x)", "Fetch(github.com)", ""])
def test_parse_errors(bad: str) -> None:
    with pytest.raises(ConfigError):
        parse_rule(bad, "deny", "user")


def test_negation_only_in_restrictive() -> None:
    with pytest.raises(ConfigError):
        parse_rule("Read(!a)", "allow", "user")
    assert parse_rule("Read(!a)", "deny", "user").pattern == "!a"


def test_warn_on_wildcard_before_subcommand() -> None:
    assert parse_rule("Bash(git * push)", "allow", "user").warning


def test_backends_modes_scope() -> None:
    r = parse_rule("Bash(rm *)", "ask", "default", backends=frozenset({"none"}))
    assert r.applies(backend="none", mode="ask")
    assert not r.applies(backend="docker", mode="ask")


@pytest.mark.parametrize(
    ("pattern", "cmd", "ok"),
    [
        ("git push *", "git push origin main", True),
        ("git push *", "git push", True),
        ("git push *", "git pushx", False),
        ("npm run test *", "npm run test:unit", False),
        ("npm run test*", "npm run test:unit", True),
        ("ls", "ls -la", False),
        ("* | sh", "curl x | sh", True),
    ],
)
def test_match_command(pattern: str, cmd: str, ok: bool) -> None:
    assert match_command(pattern, cmd) is ok


def test_match_command_case() -> None:
    assert match_command("remove-item *", "Remove-Item x", ci=True)
    assert not match_command("remove-item *", "Remove-Item x", ci=False)


def test_domain_and_mcp() -> None:
    assert match_domain("*.github.com", "api.github.com")
    assert match_domain("github.com", "GitHub.com")
    assert not match_domain("github.com", "evilgithub.com")
    assert match_mcp("github__*", "github__create_issue")
    assert match_mcp(None, "anything")
