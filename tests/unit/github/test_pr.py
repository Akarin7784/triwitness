"""审批后开 PR（v1.0 B4 方案②）：本地裸仓库当远端 + 假 GitHub API，不联网、不需要真令牌。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from triwitness.github.pr import (
    TOKEN_GUIDANCE,
    PrError,
    create_pr_api,
    open_pr,
    parse_remote,
    plan_pr,
    record_pr,
    redact,
)

RUN = "r_01M4NANDBP5J50KF7ESFJ0M7E3"
FAKE = "github_pat_" + "A1b2C3d4" * 6  # 形状像细粒度令牌，不是真的


def git(cwd: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    home, repo, bare = tmp_path / "home", tmp_path / "repo", tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    (repo / "verses.py").write_text("def line_count(t):\n    return len(t.split('\\n'))\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    git(repo, "remote", "add", "origin", "https://github.com/acme/demo.git")
    git(repo, "push", "-q", str(bare), "main:main")
    git(repo, "checkout", "-qb", f"tw/{RUN}")
    (repo / "verses.py").write_text("def line_count(t):\n    return sum(1 for x in t.split('\\n') if x.strip())\n")
    git(repo, "commit", "-qam", "fix")
    git(repo, "checkout", "-q", "main")
    rd = home / "runs" / RUN
    rd.mkdir(parents=True)
    (rd / "summary.json").write_text(json.dumps({"status": "done", "branch": f"tw/{RUN}", "verdict": "pass"}))
    (rd / "finish.json").write_text(
        json.dumps({"summary": "line_count 只数非空行。复现测试通过。"}, ensure_ascii=False)
    )
    (rd / "pr.md").write_text("## TriWitness 证据包\n复验通过", encoding="utf-8")
    return home, repo, bare


def test_parse_remote_and_redact() -> None:
    assert parse_remote("https://github.com/Akarin7784/tw-scratch.git") == ("Akarin7784", "tw-scratch")
    assert parse_remote("git@github.com:a-b/c.d") == ("a-b", "c.d")
    assert parse_remote("https://x:y@github.com/o/r") == ("o", "r")
    for bad in ("https://gitlab.com/o/r.git", "https://github.com.evil.io/o/r", "file:///tmp/r"):
        with pytest.raises(PrError):
            parse_remote(bad)
    assert FAKE not in redact(f"push https://u:{FAKE}@github.com/o/r token {FAKE}")


def test_plan_shows_repo_branch_base_title(setup: tuple[Path, Path, Path]) -> None:
    home, repo, _ = setup
    p = plan_pr(home, RUN, repo, env={"GITHUB_TOKEN": FAKE})
    assert (p.full_name, p.head, p.base, p.auth) == ("acme/demo", f"tw/{RUN}", "main", "token")
    assert p.title == "[TriWitness] line_count 只数非空行" and p.commits == 1 and p.files == ["verses.py"]
    card = p.card()
    assert card["ok"] and card["full_name"] == "acme/demo" and "Contents" in card["guidance"]
    assert "Pull requests" in TOKEN_GUIDANCE and FAKE not in json.dumps(card)


def test_plan_refuses_bad_inputs(setup: tuple[Path, Path, Path], tmp_path: Path) -> None:
    home, repo, _ = setup
    with pytest.raises(PrError, match="run_id"):
        plan_pr(home, "../etc", repo)
    git(repo, "remote", "set-url", "origin", "https://gitlab.com/acme/demo.git")
    with pytest.raises(PrError, match="不是 GitHub"):
        plan_pr(home, RUN, repo)
    git(repo, "remote", "set-url", "origin", "https://github.com/acme/demo.git")
    s = home / "runs" / RUN / "summary.json"
    s.write_text(json.dumps({"status": "cancelled", "branch": f"tw/{RUN}"}))
    with pytest.raises(PrError, match="完成"):
        plan_pr(home, RUN, repo)
    s.write_text(json.dumps({"status": "done", "branch": None}))
    with pytest.raises(PrError, match="没有改动分支"):
        plan_pr(home, RUN, repo)


def fake_github(seen: list[httpx.Request], *, existing: bool = False, status: int = 201) -> httpx.Client:
    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.method == "GET":
            return httpx.Response(
                200, json=[{"html_url": "https://github.com/acme/demo/pull/3", "number": 3}] if existing else []
            )
        if status != 201:
            return httpx.Response(status, json={"message": "Resource not accessible by personal access token"})
        body = json.loads(req.content)
        assert body["head"] == f"tw/{RUN}" and body["base"] == "main" and "证据包" in body["body"]
        return httpx.Response(201, json={"html_url": "https://github.com/acme/demo/pull/7", "number": 7})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_open_pushes_branch_and_creates_pr(setup: tuple[Path, Path, Path]) -> None:
    home, repo, bare = setup
    plan = plan_pr(home, RUN, repo, env={"GITHUB_TOKEN": FAKE})
    seen: list[httpx.Request] = []
    res = open_pr(plan, env={"GITHUB_TOKEN": FAKE}, push_url=str(bare), client=fake_github(seen))
    assert (res.url, res.number, res.created) == ("https://github.com/acme/demo/pull/7", 7, True)
    assert git(bare, "rev-parse", f"refs/heads/tw/{RUN}") == git(repo, "rev-parse", f"tw/{RUN}")
    assert seen[-1].headers["Authorization"] == f"Bearer {FAKE}" and seen[-1].url.path == "/repos/acme/demo/pulls"
    f = record_pr(home, plan, res)
    assert FAKE not in f.read_text(encoding="utf-8") and "pull/7" in f.read_text(encoding="utf-8")
    assert plan_pr(home, RUN, repo, env={}, auth=None).existing_url == res.url
    assert FAKE not in git(repo, "config", "--list")  # 令牌没写进仓库配置


def test_existing_open_pr_is_returned_not_duplicated(setup: tuple[Path, Path, Path]) -> None:
    home, repo, _ = setup
    plan = plan_pr(home, RUN, repo, env={"GITHUB_TOKEN": FAKE})
    seen: list[httpx.Request] = []
    res = create_pr_api(plan, FAKE, client=fake_github(seen, existing=True))
    assert (res.number, res.created) == (3, False) and [r.method for r in seen] == ["GET"]


def test_api_errors_are_actionable_and_redacted(setup: tuple[Path, Path, Path]) -> None:
    home, repo, _ = setup
    plan = plan_pr(home, RUN, repo, env={"GITHUB_TOKEN": FAKE})
    with pytest.raises(PrError, match="权限不够") as e:
        create_pr_api(plan, FAKE, client=fake_github([], status=403))
    assert FAKE not in str(e.value)


def test_no_auth_refuses_before_pushing(setup: tuple[Path, Path, Path]) -> None:
    home, repo, bare = setup
    plan = plan_pr(home, RUN, repo, env={}, auth=None)
    with pytest.raises(PrError, match="没有 GitHub 授权"):
        open_pr(plan, env={}, push_url=str(bare))
    assert not git(bare, "branch", "--list", f"tw/{RUN}")


def test_cli_plan_json_and_open_requires_yes(setup: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    from triwitness.cli.main import app

    home, repo, _ = setup
    monkeypatch.setenv("TW_HOME", str(home))
    monkeypatch.setenv("GITHUB_TOKEN", FAKE)
    r = CliRunner().invoke(app, ["pr", "plan", "--run", RUN, "--repo", str(repo), "--json"])
    d = json.loads(r.output)
    assert r.exit_code == 0 and d["ok"] and d["full_name"] == "acme/demo" and d["auth"] == "token"
    assert FAKE not in r.output
    r = CliRunner().invoke(app, ["pr", "open", "--run", RUN, "--repo", str(repo)])
    assert r.exit_code == 2 and "--yes" in r.output
    r = CliRunner().invoke(app, ["pr", "plan", "--run", "r_bad", "--repo", str(repo)])
    assert r.exit_code == 2 and json.loads(r.output)["ok"] is False
