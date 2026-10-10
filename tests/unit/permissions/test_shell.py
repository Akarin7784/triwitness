"""复合命令拆分、包装器剥离、执行字符串识别、PowerShell 解析。"""

import pytest

from triwitness.permissions.shell import (
    ShellParseError,
    is_exec_string,
    parse_bash,
    parse_powershell,
    program,
    strip_wrappers,
)


def texts(cmd: str) -> list[str]:
    return [strip_wrappers(c).value_text for c in parse_bash(cmd).commands]


@pytest.mark.parametrize(
    ("cmd", "expected"),
    [
        ("npm run build && git push origin x", ["npm run build", "git push origin x"]),
        ("a; b || c | d", ["a", "b", "c", "d"]),
        ("a |& b", ["a", "b"]),
        ("a & b", ["a", "b"]),
        ("a\nb", ["a", "b"]),
        ("echo 'a && b'", ["echo a && b"]),
        ('echo "x; y"', ["echo x; y"]),
        ("(cd sub && make)", ["cd sub", "make"]),
        ("echo $(rm -rf x)", ["echo $(…)", "rm -rf x"]),
        ("echo `whoami`", ["echo `…`", "whoami"]),
        ("diff <(ls a) <(ls b)", ["diff <(…) <(…)", "ls a", "ls b"]),
        ("timeout 5 nice -n 5 pytest -q", ["pytest -q"]),
        ("env FOO=1 make test", ["make test"]),
        ("nohup sleep 1 &", ["sleep 1"]),
        ("ls # && rm -rf /", ["ls"]),
    ],
)
def test_compound_split(cmd: str, expected: list[str]) -> None:
    got = texts(cmd)
    for e in expected:
        assert any(e == g or e in g for g in got), (cmd, got)
    assert len(got) >= len([e for e in expected if e])


def test_heredoc_body_not_commands() -> None:
    cmd = "cat <<EOF > out.txt\nrm -rf /\nEOF\necho done"
    got = texts(cmd)
    assert not any(g.startswith("rm") for g in got)
    assert any(g.startswith("echo done") for g in got)


def test_redirects_parsed() -> None:
    (c,) = parse_bash("echo hi>out 2>&1").commands
    assert [w.value for w in c.words] == ["echo", "hi"]
    ops = {(r.op, r.target) for r in c.redirects}
    assert any(t == "out" for _, t in ops)


@pytest.mark.parametrize("bad", ["a &&", "echo 'unterminated", "case x in a) ;; esac", "f() { rm x; }", "x" * 10_001])
def test_parse_errors(bad: str) -> None:
    with pytest.raises(ShellParseError):
        parse_bash(bad)


def test_assignments_kept_separately() -> None:
    (c,) = parse_bash("FOO=1 LD_PRELOAD=/x.so make").commands
    assert dict(c.assigns) == {"FOO": "1", "LD_PRELOAD": "/x.so"}
    assert program(c) == "make"


@pytest.mark.parametrize(
    ("cmd", "exec_str"),
    [
        ("bash -c 'rm x'", True),
        ("sh -c ls", True),
        ("python -c 'print(1)'", True),
        ("python3 -c x", True),
        ("node -e x", True),
        ("eval foo", True),
        ("xargs -0 rm", True),
        ("xargs rm", False),  # 无参数的 xargs 被剥离，按 rm 本身判定
        ("find . -exec rm {} ;", True),
        ("find . -name x", False),
        ("python script.py", False),
        ("ls -la", False),
    ],
)
def test_exec_string(cmd: str, exec_str: bool) -> None:
    (c, *_) = parse_bash(cmd).commands
    assert is_exec_string(strip_wrappers(c)) is exec_str


def test_full_path_program_basename() -> None:
    (c,) = parse_bash("/usr/bin/git status").commands
    assert program(c) == "git"


def test_powershell_split_and_aliases() -> None:
    cmds = parse_powershell("ls C:\\Repo; rm -Recurse x | Out-Null && echo ok").commands
    progs = [program(c).lower() for c in cmds]
    assert progs[:2] == ["get-childitem", "remove-item"]
    assert "write-output" in progs


@pytest.mark.parametrize("bad", ["& { rm x }", "Write-Output $(Get-Secret)", "@(1,2) | % { $_ }"])
def test_powershell_rejects_scriptblocks(bad: str) -> None:
    with pytest.raises(ShellParseError):
        parse_powershell(bad)
