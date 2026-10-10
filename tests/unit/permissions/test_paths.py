"""Windows / POSIX 路径规范化与 gitignore 风格匹配。"""

import pytest

from triwitness.permissions.paths import compile_path_pattern, escape_glob, normalize_path

WCWD = "/c/Repo"
WHOME = "/c/Users/Eva"


def wn(raw: str, **kw: object) -> tuple[str, frozenset[str]]:
    np = normalize_path(raw, cwd=WCWD, home=WHOME, windows=True, **kw)  # type: ignore[arg-type]
    return np.path, np.flags


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (r"C:\Repo\.ENV", "/c/Repo/.ENV"),
        ("c:/repo/src/a.py", "/c/repo/src/a.py"),
        (r"\\?\C:\Repo\a.txt", "/c/Repo/a.txt"),
        (r"\\.\C:\Repo\a.txt", "/c/Repo/a.txt"),
        ("/C/Repo/a.txt", "/c/Repo/a.txt"),
        ("/cygdrive/c/Repo/a.txt", "/c/Repo/a.txt"),
        (r"src\..\..\Windows\win.ini", "/c/Windows/win.ini"),
        ("~/.ssh/id_rsa", "/c/Users/Eva/.ssh/id_rsa"),
        (r"src\a.py", "/c/Repo/src/a.py"),
        ("secret.txt.", "/c/Repo/secret.txt"),
        ("secret.txt . ", "/c/Repo/secret.txt"),
        ("D:", "/d"),
    ],
)
def test_windows_normalize(raw: str, expected: str) -> None:
    path, flags = wn(raw)
    assert path == expected
    assert not flags


def test_windows_case_insensitive_key() -> None:
    a = normalize_path(r"C:\Repo\.ENV", cwd=WCWD, home=WHOME, windows=True)
    b = normalize_path("c:/repo/.env", cwd=WCWD, home=WHOME, windows=True)
    assert a.key == b.key
    assert a.is_within(normalize_path("C:/REPO", cwd=WCWD, home=WHOME, windows=True))


@pytest.mark.parametrize(
    ("raw", "flag"),
    [
        (r"\\server\share\x", "unc"),
        (r"\\?\UNC\server\share\x", "unc"),
        ("a.txt:secret", "ads"),
        (r"C:\Repo\a.txt::$DATA", "ads"),
        ("NUL", "reserved"),
        ("con.txt", "reserved"),
        (r"src\COM1", "reserved"),
        (r"C:\PROGRA~1\x", "short_name"),
        ("$HOME/.ssh/id_rsa", "unresolved_var"),
        ("`pwd`/x", "unresolved_var"),
    ],
)
def test_windows_flags(raw: str, flag: str) -> None:
    _, flags = wn(raw)
    assert flag in flags


def test_short_name_expanded_via_callback() -> None:
    path, flags = wn(r"C:\PROGRA~1\x", long_name=lambda p: p.replace("PROGRA~1", "Program Files"))
    assert path == "/c/Program Files/x"
    assert "short_name" not in flags


def test_posix_normalize() -> None:
    np = normalize_path("../x/./y", cwd="/w/repo", home="/home/eva")
    assert np.path == "/w/x/y"
    assert normalize_path("~", cwd="/w", home="/home/eva").path == "/home/eva"
    # POSIX 下冒号是普通字符
    assert not normalize_path("a:b", cwd="/w", home="/h").flags


def m(pattern: str, path: str, *, restrictive: bool = True, windows: bool = False) -> bool:
    pat = compile_path_pattern(
        pattern, restrictive=restrictive, source_root="/w/repo", cwd="/w/repo", home="/home/eva", windows=windows
    )
    return pat.regex.match(path) is not None


@pytest.mark.parametrize(
    ("pattern", "path", "ok"),
    [
        ("**/.env", "/w/repo/.env", True),
        ("**/.env", "/w/repo/a/b/.env", True),
        ("**/.env.*", "/w/repo/.env.local", True),
        ("**/.env", "/w/repo/.envrc", False),
        ("~/.ssh/**", "/home/eva/.ssh/id_rsa", True),
        ("//etc/passwd", "/etc/passwd", True),
        ("/src/*.py", "/w/repo/src/a.py", True),
        ("/src/*.py", "/w/repo/src/sub/a.py", False),
        ("/src/**/*.py", "/w/repo/src/sub/a.py", True),
        ("./build", "/w/repo/build/x.o", True),
        ("secrets/**", "/w/repo/deep/secrets/k", True),
        ("*.pem", "/w/repo/x/y.pem", True),
    ],
)
def test_gitignore_matching(pattern: str, path: str, ok: bool) -> None:
    assert m(pattern, path) is ok


def test_windows_pattern_ignorecase() -> None:
    assert m("**/.env", "/W/REPO/.ENV", windows=True)
    assert not m("**/.env", "/w/repo/.ENV", windows=False)


def test_negation_flag_and_escape() -> None:
    pat = compile_path_pattern(
        "!**/.env.example", restrictive=True, source_root="/w", cwd="/w", home="/h", windows=False
    )
    assert pat.negated
    assert pat.regex.match("/w/.env.example")
    lit = escape_glob("/w/[x]*?.py")
    p2 = compile_path_pattern("/" + lit, restrictive=False, source_root="/w", cwd="/w", home="/h", windows=False)
    assert p2.regex.match("/w/[x]*?.py")
    assert not p2.regex.match("/w/xa.py")
