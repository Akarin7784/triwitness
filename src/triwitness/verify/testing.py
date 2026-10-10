"""测试用的小 diff 构造器与临时 git 仓库（单测、集成测试共用，和 harness.testing 一样放在包里）。"""

from __future__ import annotations

import subprocess
from pathlib import Path


def modify(path: str, removed: list[str], added: list[str], start: int = 1) -> str:
    body = [f"-{r}" for r in removed] + [f"+{a}" for a in added]
    return (f"diff --git a/{path} b/{path}\nindex 1111111..2222222 100644\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -{start},{len(removed)} +{start},{len(added)} @@\n" + "\n".join(body) + "\n")  # fmt: skip


def new_file(path: str, lines: list[str]) -> str:
    return (f"diff --git a/{path} b/{path}\nnew file mode 100644\nindex 0000000..3333333\n--- /dev/null\n"
            f"+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n" + "\n".join(f"+{x}" for x in lines) + "\n")  # fmt: skip


def delete(path: str, lines: list[str]) -> str:
    return (f"diff --git a/{path} b/{path}\ndeleted file mode 100644\nindex 3333333..0000000\n--- a/{path}\n"
            f"+++ /dev/null\n@@ -1,{len(lines)} +0,0 @@\n" + "\n".join(f"-{x}" for x in lines) + "\n")  # fmt: skip


def git(repo: Path, *a: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *a],
                       check=True, capture_output=True, text=True)  # fmt: skip
    return r.stdout


def _write(repo: Path, files: dict[str, str]) -> None:
    for k, v in files.items():
        (repo / k).parent.mkdir(parents=True, exist_ok=True)
        (repo / k).write_text(v, newline="\n")  # Windows 上也写 LF，否则补丁打不上


def make_repo(tmp: Path, files: dict[str, str]) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _write(repo, files)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    return repo


def make_patch(repo: Path, files: dict[str, str]) -> str:
    """在仓库里写入改动 → 取 diff → 还原（模拟 Executor 交出来的补丁）。"""
    _write(repo, files)
    git(repo, "add", "-A")
    patch = git(repo, "diff", "--cached", "--binary")
    git(repo, "reset", "-q", "--hard")
    git(repo, "clean", "-qfd")
    return patch
