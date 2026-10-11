import sys
from textwrap import dedent

import pytest

from hlp.cli import autocomplete, autocomplete_bash


@pytest.fixture
def fake_packages(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("example")
    pa = tmp_path / "pkg_aaa"
    pb = tmp_path / "pkg_aab"
    pc = tmp_path / "pkg_aac"
    for d in [pa, pb, pc]:
        d.mkdir()
        d.joinpath("__init__.py").touch()

    pa_ma = pa.joinpath("mod_a.py")
    pa_ma.write_text(
        dedent(
            u"""
        var_a = 1
        
        class Test(object):
            var_b = 2

            class Inner(object):
                pass
    """
        ),
        encoding="utf-8",
    )
    pa_pa = pa.joinpath("pkg_a")
    pa_pa.mkdir()
    pa_pa.joinpath("__init__.py").touch()

    old_path = list(sys.path)
    sys.path.append(str(tmp_path))

    try:
        yield
    finally:
        sys.path = old_path


@pytest.mark.parametrize(
    "name,expected",
    [
        ("pkg_aa", ["pkg_aaa", "pkg_aab", "pkg_aac"]),
        ("pkg_aaa", ["pkg_aaa"]),
        ("pkg_aaa.", ["pkg_aaa.mod_a", "pkg_aaa.pkg_a"]),
        ("pkg_aaa.m", ["pkg_aaa.mod_a"]),
        ("pkg_aaa.mod_a.", ["pkg_aaa.mod_a.Test"]),
        ("pkg_aaa.mod_a.Test", ["pkg_aaa.mod_a.Test"]),
        ("pkg_aaa.mod_a.Test.", ["pkg_aaa.mod_a.Test.Inner"]),
    ],
)
def test_autocomplete_basics(name, expected, fake_packages):
    assert expected == autocomplete(name)


#  1. hlp | -> all builtins/modules
def test_autocomplete_bash_empty(fake_packages, monkeypatch):
    monkeypatch.setenv("COMP_WORDS", "hlp")
    monkeypatch.setenv("COMP_CWORD", "1")
    result = autocomplete_bash()
    # Builtins
    assert "open" in result
    assert "ord" in result
    # Standard library modules
    assert "string" in result
    assert "multiprocessing" in result
    # Our packages
    assert "pkg_aaa" in result
    # Only name, no trailing '.'
    assert "pkg_aaa." not in result


@pytest.mark.parametrize(
    "words,cword,expected",
    [
        #  hlp pkg_aa| -> entities starting with "pkg_aa"
        (["pkg_aa"], 1, ["pkg_aaa", "pkg_aab", "pkg_aac"]),
        #  hlp pkg_aaa.| -> entities in pkg_aaa and prefix with pkg_aaa.
        (["pkg_aaa."], 1, ["pkg_aaa.mod_a", "pkg_aaa.pkg_a"]),
        #  hlp pkg_aaa | -> entities in pkg_aaa and do not prefix
        (["pkg_aaa"], 2, ["mod_a", "pkg_a"]),
        #  5. hlp pkg_aaa mod_a.| -> entities in pkg_aaa.mod_a and prefix with mod_a.
        (["pkg_aaa", "mod_a."], 2, ["Test"]),
    ],
)
def test_autocomplete_bash(words, cword, expected, fake_packages, monkeypatch):
    monkeypatch.setenv("COMP_WORDS", "hlp {}".format(" ".join(words)))
    monkeypatch.setenv("COMP_CWORD", str(cword))
