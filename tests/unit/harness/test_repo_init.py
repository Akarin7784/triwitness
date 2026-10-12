"""0.5.0：所选文件夹不是 git 仓库时自动初始化。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from triwitness.harness.repo_init import COMMIT_MESSAGE, ensure_git_repo, inside_git_repo


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 不读真实的全局 git 配置：没有 user.name / email，触发兜底身份
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig-empty"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def test_init_plain_folder_respects_gitignore(tmp_path: Path) -> None:
    d = tmp_path / "测试任务"
    d.mkdir()
    (d / "a.py").write_text("print(1)\n", encoding="utf-8")
    (d / ".gitignore").write_text("secret.txt\n", encoding="utf-8")
    (d / "secret.txt").write_text("x", encoding="utf-8")
    assert ensure_git_repo(d) is True
    assert _git(d, "log", "-1", "--format=%s") == COMMIT_MESSAGE
    files = _git(d, "ls-files").splitlines()
    assert "a.py" in files and ".gitignore" in files and "secret.txt" not in files
    assert _git(d, "config", "--local", "user.email") == "triwitness@local"
    assert _git(d, "status", "--porcelain") == ""


def test_init_empty_folder(tmp_path: Path) -> None:
    d = tmp_path / "empty"
    d.mkdir()
    assert ensure_git_repo(d) is True
    assert _git(d, "rev-parse", "HEAD")


def test_keeps_existing_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "gitconfig-user"
    cfg.write_text("[user]\n\tname = Eva\n\temail = eva@example.com\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    d = tmp_path / "w"
    d.mkdir()
    (d / "x").write_text("1", encoding="utf-8")
    assert ensure_git_repo(d) is True
    assert _git(d, "log", "-1", "--format=%ae") == "eva@example.com"
    assert subprocess.run(["git", "-C", str(d), "config", "--local", "user.email"]).returncode != 0


def test_never_touches_existing_repo_or_subdir(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "sub" / "f").write_text("1", encoding="utf-8")
    assert inside_git_repo(repo) and inside_git_repo(repo / "sub")
    assert ensure_git_repo(repo) is False
    assert ensure_git_repo(repo / "sub") is False
    assert not (repo / "sub" / ".git").exists()
    # 没有任何提交，说明一次都没动过
    assert subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True).returncode != 0
