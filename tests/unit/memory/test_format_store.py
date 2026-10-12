"""spec 013 §3（W6-02）：Agent Memory Repo 格式、来源字段、git 历史、隔离、密钥拒绝、会话类型。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from triwitness.memory.format import Entry, links, parse_entries, parse_entry, render_entry
from triwitness.memory.store import Episode, MemoryRejected, MemoryStore, memory_allowed, repo_key


def test_entry_roundtrip_metadata_order() -> None:
    line = render_entry(
        "测试用 `python -m unittest`", {"kind": "test", "added": "2026-10-12", "source": "tw://run/r_1"}
    )
    assert line == "- 测试用 `python -m unittest` [source: tw://run/r_1; added: 2026-10-12; kind: test]"
    e = parse_entry(line)
    assert e is not None and e.text == "测试用 `python -m unittest`" and e.meta["source"] == "tw://run/r_1"
    # 元数据里的分隔符被清掉，不会破坏格式
    bad = render_entry("x", {"source": "a; b [c]"})
    assert parse_entry(bad) == Entry("x", {"source": "a, b c"}) or parse_entry(bad).meta["source"].count(";") == 0  # type: ignore[union-attr]


def test_parse_entries_stops_at_index_and_links() -> None:
    md = "# Memory\n\n- a [source: s; added: 2026-01-01]\n- b\n\n## Index\n\n- [[episodes]]\n- [[skills/x/SKILL]]\n"
    assert [e.text for e in parse_entries(md)] == ["a", "b"]
    assert links(md) == ["episodes", "skills/x/SKILL"]


def test_add_fact_writes_memory_md_with_source_and_git_history(store: MemoryStore) -> None:
    e = store.add_fact("运行测试：python -m unittest discover -s tests", kind="test", source="tw://run/r_a",
                       added="2026-10-12")  # fmt: skip
    md = store.memory_md.read_text(encoding="utf-8")
    assert md.startswith("# Memory: /repos/demo")
    assert f"[source: tw://run/r_a; added: 2026-10-12; id: {e.id}; kind: test]" in md
    assert "## Index" in md
    # 同文本再加只更新来源，不重复
    store.add_fact("运行测试：python -m unittest discover -s tests", kind="test", source="tw://run/r_b")
    assert len(store.facts()) == 1 and store.facts()[0].meta["source"] == "tw://run/r_b"
    if store.git:
        assert (store.root / ".git").is_dir()
        assert any("fact" in h for h in store.history())


def test_episodes_index_and_forget(store: MemoryStore) -> None:
    ep = store.add_episode(Episode("空输入", "除以 len(xs) 未判空", "先判空返回 0.0 并补测试", "改调用方"),
                           source="tw://run/r_1", task="t_1")  # fmt: skip
    assert "[[episodes]]" in store.memory_md.read_text(encoding="utf-8")
    assert store.episodes()[0].meta["task"] == "t_1"
    assert store.search_episodes("mean 空列表 ZeroDivisionError 除以 len")[0].id == ep.id
    assert store.forget(ep.id) and store.episodes() == []
    assert not store.forget("e-nope")


def test_secret_is_rejected_not_redacted(store: MemoryStore) -> None:
    key = "sk-" + "a1b2c3d4" * 4
    with pytest.raises(MemoryRejected, match="secret"):
        store.add_fact(f"部署用 DEEPSEEK_API_KEY={key}", source="tw://manual")
    assert not store.exists() or key not in store.memory_md.read_text(encoding="utf-8")


def test_bypass_rejected(store: MemoryStore) -> None:
    with pytest.raises(MemoryRejected, match="bypass"):
        store.add_fact("提交时用 git commit --no-verify 跳过钩子", source="tw://manual")


def test_repo_isolation(tmp_path: Path) -> None:
    def git_repo(name: str, url: str | None) -> Path:
        p = tmp_path / name
        p.mkdir()
        subprocess.run(["git", "init", "-q", str(p)], check=True)
        if url:
            subprocess.run(["git", "-C", str(p), "remote", "add", "origin", url], check=True)
        return p

    a = git_repo("a", "git@github.com:Org/Proj.git")
    b = git_repo("b", "https://github.com/org/proj")
    c = git_repo("c", None)
    assert repo_key(a) == repo_key(b) == "github.com__org__proj"  # 同一远端的不同克隆共享
    assert repo_key(c).startswith("local__c-")
    sa = MemoryStore.for_repo(a, tmp_path / "home")
    sc = MemoryStore.for_repo(c, tmp_path / "home")
    sa.add_fact("用 tox 跑测试", source="tw://manual")
    assert sc.facts() == [] and sa.root != sc.root


@pytest.mark.parametrize(
    ("mode", "category", "override", "allowed"),
    [
        ("background", "dogfood", None, True),
        ("interactive", "dev", None, True),
        ("eval", "baseline", None, False),
        ("background", "harbor-external", None, False),
        ("automated", "dev", None, False),
        ("eval", "skill-gate", True, True),
        ("background", "dogfood", False, False),
    ],
)
def test_memory_allowed_by_session(mode: str, category: str, override: bool | None, allowed: bool) -> None:
    assert memory_allowed(mode, category, override=override) is allowed


def test_origin_url_reads_config_without_git_process(tmp_path: Path) -> None:
    """仓库键直接读 .git/config（含 worktree 的 .git 文件），不起 git 子进程（Windows 桥接模式曾卡死）。"""
    from triwitness.memory.store import origin_url

    main = tmp_path / "main"
    main.mkdir()
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    subprocess.run(["git", "-C", str(main), "remote", "add", "origin", "https://github.com/o/p.git"], check=True)
    subprocess.run(["git", "-C", str(main), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                    "--allow-empty", "-m", "i"], check=True)  # fmt: skip
    wt = tmp_path / "wt"
    subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", str(wt)], check=True)
    assert (wt / ".git").is_file()
    assert origin_url(main) == origin_url(wt) == "https://github.com/o/p.git"
    assert repo_key(wt) == "github.com__o__p"
    assert origin_url(tmp_path) == ""
