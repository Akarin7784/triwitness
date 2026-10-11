"""审批后开真实 GitHub PR（v1.0 B4 方案②）。

流程（桌面端：结论卡「开 PR」→ 审批卡 → 确认）：
1. `plan_pr`（不联网、不推送）：从运行目录读分支 `tw/<run_id>`、pr.md、结论，从仓库的远端解析 owner/repo、
   目标分支；审批卡把 仓库 / 分支 / 目标分支 / 标题 / 提交数 / 改动文件 摆给用户看。
2. `open_pr`（只有用户在审批卡上确认后，CLI 才带 `--yes` 调用）：`git push` 分支 → REST API 开 PR
   （已有同分支的 open PR 就直接返回它，不重复开）→ 结果写进 `runs/<id>/pr.json`。

鉴权两种（都不把令牌写进任何文件 / 命令行参数 / 日志）：
- 令牌：环境变量 `GITHUB_TOKEN`（桌面端从系统凭据库取出，只注入这个子进程）。推送用
  `http.<host>.extraheader`（经 GIT_CONFIG_* 环境变量传给 git 子进程，不进 argv），开 PR 用 REST。
- gh：本机已 `gh auth login` 时，推送走 gh 自带的凭据助手（`gh auth git-credential`），开 PR 用 `gh pr create`；
  我们不读取 gh 的令牌。

最小权限建议见 `TOKEN_GUIDANCE`：细粒度令牌、只选这一个仓库、Contents + Pull requests 读写、设过期时间。
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx

from triwitness.core.errors import ConfigError

API = "https://api.github.com"
API_OVERRIDE_ENV = "TW_GITHUB_API_OVERRIDE"  # 仅测试：本机假 GitHub API
TOKEN_ENV = "GITHUB_TOKEN"
TOKEN_GUIDANCE = (
    "建议用细粒度令牌（Fine-grained personal access token）：Repository access 只选这一个仓库；"
    "Permissions 只给 Contents: Read and write、Pull requests: Read and write（Metadata: Read 自动附带）；"
    "设置过期时间（如 30 天）。不要用勾选了 repo 全权限的经典令牌。令牌只存进系统凭据库，随时可在设置里清除。"
)
TOKEN_URL = "https://github.com/settings/personal-access-tokens/new"

Auth = Literal["token", "gh"]
Git = Callable[..., "subprocess.CompletedProcess[str]"]

_RUN_ID = re.compile(r"^r_[0-9A-HJKMNP-TV-Z]{26}$")
_REMOTE = re.compile(
    r"^(?:https://(?:[^@/]+@)?github\.com/|ssh://git@github\.com/|git@github\.com:)"
    r"(?P<owner>[A-Za-z0-9-]{1,39})/(?P<repo>[A-Za-z0-9._-]{1,100}?)(?:\.git)?/?$"
)
_BRANCH = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")


class PrError(ConfigError):
    """开 PR 的前置条件不满足或 GitHub 拒绝（消息给用户看，不含令牌）。"""


@dataclass
class PrPlan:
    run_id: str
    repo_path: str
    remote: str
    owner: str
    repo: str
    head: str
    base: str
    title: str
    body: str
    commits: int
    files: list[str] = field(default_factory=list)
    auth: Auth | None = None
    existing_url: str | None = None  # 之前已经开过（runs/<id>/pr.json）

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    def card(self) -> dict[str, Any]:
        """审批卡 / `tw pr plan --json` 的内容（正文只给预览）。"""
        d = asdict(self)
        d["body_preview"] = self.body[:1200]
        del d["body"]
        d.update(ok=True, full_name=self.full_name, guidance=TOKEN_GUIDANCE, token_url=TOKEN_URL)
        return d


@dataclass(frozen=True)
class PrResult:
    url: str
    number: int
    created: bool  # False = 同分支已有 open PR，直接返回
    pushed: bool


# ---------------------------------------------------------------- 小工具


def parse_remote(url: str) -> tuple[str, str]:
    """GitHub 远端地址 → (owner, repo)。只认 github.com（https / ssh）。"""
    m = _REMOTE.match(url.strip())
    if not m:
        raise PrError(f"远端不是 GitHub 仓库：{redact(url)}")
    return m["owner"], m["repo"]


def redact(text: str, *secrets: str | None) -> str:
    """去掉 URL 里的 user:pass@ 和任何已知密钥。"""
    out = re.sub(r"(https?://)[^/@\s]+@", r"\1", text)
    out = re.sub(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b", "***", out)
    for s in secrets:
        if s:
            out = out.replace(s, "***")
    return out


def _git(repo: Path, *args: str, env: Mapping[str, str] | None = None, check: bool = True) -> str:
    p = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})},
        timeout=300,
    )
    if check and p.returncode != 0:
        raise PrError(f"git {args[0]} 失败：{redact((p.stderr or p.stdout).strip()[-600:], *(env or {}).values())}")
    return p.stdout.strip()


def api_base() -> str:
    url = os.environ.get(API_OVERRIDE_ENV, "").strip().rstrip("/")
    if not url:
        return API
    if not re.match(r"^http://(127\.0\.0\.1|localhost)(:\d+)?$", url):
        raise ConfigError(f"{API_OVERRIDE_ENV} 只允许本机地址（测试用）：{url}")
    return url


def gh_available() -> bool:
    """本机有 gh 且已登录 github.com（只看退出码，不读令牌）。"""
    if not shutil.which("gh"):
        return False
    try:
        p = subprocess.run(["gh", "auth", "status", "--hostname", "github.com"], capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return p.returncode == 0


def detect_auth(env: Mapping[str, str] | None = None) -> Auth | None:
    env = os.environ if env is None else env
    if env.get(TOKEN_ENV, "").strip():
        return "token"
    return "gh" if gh_available() else None


def _title(run_dir: Path) -> str:
    for name, key in (("finish.json", "summary"),):
        f = run_dir / name
        if f.is_file():
            try:
                s = str(json.loads(f.read_text(encoding="utf-8")).get(key) or "")
            except (OSError, ValueError):
                s = ""
            s = re.split(r"[。；;，\n]|\. ", s.strip())[0].strip()
            if s:
                return "[TriWitness] " + (s if len(s) <= 72 else s[:71] + "…")
    turn = run_dir / "turn.json"
    if turn.is_file():
        try:
            u = str(json.loads(turn.read_text(encoding="utf-8")).get("user") or "").strip().splitlines()
        except (OSError, ValueError):
            u = []
        if u and u[0]:
            return ("[TriWitness] " + u[0])[:120]
    return f"[TriWitness] {run_dir.name}"


# ---------------------------------------------------------------- 计划（不联网）


def plan_pr(
    home: Path,
    run_id: str,
    repo_path: Path | None = None,
    *,
    remote: str = "origin",
    base: str | None = None,
    title: str | None = None,
    env: Mapping[str, str] | None = None,
    auth: Auth | Literal["detect"] | None = "detect",
) -> PrPlan:
    if not _RUN_ID.match(run_id):
        raise PrError("run_id 格式不对")
    run_dir = home / "runs" / run_id
    summary = run_dir / "summary.json"
    if not summary.is_file():
        raise PrError("这个任务还没结束或没有产出（缺 summary.json）")
    s = json.loads(summary.read_text(encoding="utf-8"))
    head = s.get("branch")
    if not head:
        raise PrError("这个任务没有改动分支（没有改代码，或用了沙箱后端），没法开 PR")
    if s.get("status") != "done":
        raise PrError(f"任务状态是 {s.get('status')}，只有完成的任务才能开 PR")
    if repo_path is None:
        if not s.get("repo"):
            raise PrError("不知道仓库在哪（旧任务没有记录仓库路径），请指定 --repo")
        repo_path = Path(str(s["repo"]))
    repo = repo_path.resolve()
    if not (repo / ".git").exists():
        raise PrError(f"不是 git 仓库：{repo}")
    if not _BRANCH.match(remote):
        raise PrError("远端名不合法")
    url = _git(repo, "remote", "get-url", remote, check=False)
    if not url:
        raise PrError(f"仓库没有名为 {remote} 的远端")
    owner, name = parse_remote(url)
    if not _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{head}", check=False):
        raise PrError(f"本地找不到分支 {head}（可能已被删除）")
    if base is None:
        cur = _git(repo, "rev-parse", "--abbrev-ref", "HEAD", check=False)
        base = cur if cur and cur != "HEAD" and not cur.startswith("tw/") else "main"
    if not _BRANCH.match(base) or base == head:
        raise PrError("目标分支不合法")
    merge_base = _git(repo, "merge-base", base, head, check=False) or base
    commits = int(_git(repo, "rev-list", "--count", f"{merge_base}..{head}", check=False) or 0)
    files = [f for f in _git(repo, "diff", "--name-only", f"{merge_base}..{head}", check=False).splitlines() if f]
    body_f = run_dir / "pr.md"
    body = body_f.read_text(encoding="utf-8") if body_f.is_file() else f"TriWitness 运行 `{run_id}` 的改动。"
    prev = run_dir / "pr.json"
    existing = None
    if prev.is_file():
        try:
            existing = json.loads(prev.read_text(encoding="utf-8")).get("url")
        except (OSError, ValueError):
            existing = None
    return PrPlan(
        run_id=run_id, repo_path=str(repo), remote=remote, owner=owner, repo=name, head=head, base=base,
        title=(title or _title(run_dir)).strip()[:200], body=body, commits=commits, files=files[:200],
        auth=detect_auth(env) if auth == "detect" else auth, existing_url=existing,
    )  # fmt: skip


# ---------------------------------------------------------------- 推送 + 开 PR（只在用户确认后）


def _git_env_token(token: str) -> dict[str, str]:
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "credential.helper",
        "GIT_CONFIG_VALUE_0": "",
        "GIT_CONFIG_KEY_1": "http.https://github.com/.extraheader",
        "GIT_CONFIG_VALUE_1": f"AUTHORIZATION: basic {basic}",
    }


_GH_ENV = {
    "GIT_CONFIG_COUNT": "2",
    "GIT_CONFIG_KEY_0": "credential.https://github.com.helper",
    "GIT_CONFIG_VALUE_0": "",
    "GIT_CONFIG_KEY_1": "credential.https://github.com.helper",
    "GIT_CONFIG_VALUE_1": "!gh auth git-credential",
}


def push_branch(plan: PrPlan, *, token: str | None, push_url: str | None = None) -> None:
    """把 head 推到远端同名分支（不强推；远端已有且不同就报错，不覆盖别人的提交）。"""
    url = push_url or f"https://github.com/{plan.full_name}.git"
    env = _git_env_token(token) if token else _GH_ENV
    _git(Path(plan.repo_path), "push", "--porcelain", url, f"refs/heads/{plan.head}:refs/heads/{plan.head}", env=env)


_HINTS = {
    401: "令牌无效或已过期",
    403: "令牌权限不够（需要 Pull requests: Read and write）",
    404: "找不到仓库或令牌没有这个仓库的权限",
    422: "GitHub 拒绝（目标分支不存在或已有相同 PR？）",
}


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "triwitness",
    }


def create_pr_api(plan: PrPlan, token: str, *, draft: bool = False, client: httpx.Client | None = None) -> PrResult:
    base = api_base()
    c = client or httpx.Client(timeout=30)
    try:
        r = c.get(f"{base}/repos/{plan.full_name}/pulls", headers=_headers(token),
                  params={"head": f"{plan.owner}:{plan.head}", "state": "open"})  # fmt: skip
        if r.status_code == 200 and r.json():
            pr = r.json()[0]
            return PrResult(pr["html_url"], int(pr["number"]), created=False, pushed=True)
        payload = {"title": plan.title, "head": plan.head, "base": plan.base, "body": plan.body, "draft": draft}
        r = c.post(f"{base}/repos/{plan.full_name}/pulls", headers=_headers(token), json=payload)
        if r.status_code not in (200, 201):
            msg = ""
            try:
                j = r.json()
                msg = j.get("message", "") + "".join(f"；{e.get('message', e)}" for e in j.get("errors", []) or [])
            except ValueError:
                msg = r.text[:300]
            hint = _HINTS.get(r.status_code, "")
            raise PrError(redact(f"开 PR 失败（HTTP {r.status_code}{'，' + hint if hint else ''}）：{msg}", token))
        pr = r.json()
        return PrResult(pr["html_url"], int(pr["number"]), created=True, pushed=True)
    except httpx.HTTPError as e:
        raise PrError(redact(f"连不上 GitHub：{type(e).__name__}", token)) from None
    finally:
        if client is None:
            c.close()


def create_pr_gh(plan: PrPlan, *, draft: bool = False) -> PrResult:
    args = ["gh", "pr", "create", "--repo", plan.full_name, "--head", plan.head, "--base", plan.base,
            "--title", plan.title, "--body-file", "-"]  # fmt: skip
    if draft:
        args.append("--draft")
    p = subprocess.run(args, input=plan.body, capture_output=True, text=True, encoding="utf-8", timeout=120)
    out = (p.stdout + p.stderr).strip()
    m = re.search(r"https://github\.com/\S+/pull/(\d+)", out)
    if m:  # gh 在已存在时也会打印已有 PR 的链接
        return PrResult(m[0], int(m[1]), created=p.returncode == 0, pushed=True)
    raise PrError(f"gh pr create 失败：{redact(out[-600:])}")


def open_pr(
    plan: PrPlan,
    *,
    env: Mapping[str, str] | None = None,
    draft: bool = False,
    push_url: str | None = None,
    client: httpx.Client | None = None,
) -> PrResult:
    env = os.environ if env is None else env
    token = env.get(TOKEN_ENV, "").strip() or None
    if plan.auth == "token" and not token:
        raise PrError("缺少 GitHub 令牌")
    if plan.auth is None:
        raise PrError("没有 GitHub 授权：在设置里填一个令牌，或在本机 `gh auth login`")
    push_branch(plan, token=token if plan.auth == "token" else None, push_url=push_url)
    if plan.auth == "token" and token:
        return create_pr_api(plan, token, draft=draft, client=client)
    return create_pr_gh(plan, draft=draft)


def record_pr(home: Path, plan: PrPlan, res: PrResult) -> Path:
    f = home / "runs" / plan.run_id / "pr.json"
    f.write_text(json.dumps({"url": res.url, "number": res.number, "repo": plan.full_name, "head": plan.head,
                             "base": plan.base, "title": plan.title, "created": res.created,
                             "at": datetime.now(UTC).isoformat(timespec="seconds")}, ensure_ascii=False, indent=2),
                 encoding="utf-8")  # fmt: skip
    return f


__all__ = [
    "API_OVERRIDE_ENV",
    "TOKEN_ENV",
    "TOKEN_GUIDANCE",
    "TOKEN_URL",
    "PrError",
    "PrPlan",
    "PrResult",
    "create_pr_api",
    "create_pr_gh",
    "detect_auth",
    "open_pr",
    "parse_remote",
    "plan_pr",
    "push_branch",
    "record_pr",
    "redact",
]
